"""Casos de uso del contexto Sesiones. Cada método es una transacción."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.application.puertos import (
    PasarelaPago,
    Reloj,
    UnidadDeTrabajo,
    inicios_activos_por_tutor,
)
from src.domain.comun import (
    Dinero,
    NoEncontrado,
    RecursoNoDisponible,
    ReglaNegocioViolada,
    Rol,
    exigir_rol,
)
from src.domain.sesiones.especificaciones import (
    AnticipacionMinima,
    CandidatoTutor,
    regla_asignacion,
    seleccionar_tutor,
)
from src.domain.sesiones.modelo import (
    MSG_ANTICIPACION_RESERVA,
    MSG_SIN_TUTOR,
    PAGO_NO_APLICABLE,
    BloqueDisponibilidad,
    EstadoSesion,
    Grabacion,
    PoliticaTarifas,
    Sesion,
    Solicitante,
    SolicitudReserva,
    TipoCambio,
    Tutor,
)


@dataclass(frozen=True)
class ResultadoLiquidacion:
    sesion_id: str
    estado_pago: str
    monto_tutor: Dinero
    comision: Dinero
    referencia: str | None = None
    mensaje: str = ""


def _nuevo_id() -> str:
    return "SES-" + uuid.uuid4().hex[:10].upper()


class ServicioSesiones:
    def __init__(
        self,
        uow: UnidadDeTrabajo,
        pasarela: PasarelaPago,
        reloj: Reloj,
        generar_id: Callable[[], str] = _nuevo_id,
    ):
        self.uow, self.pasarela, self.reloj, self.generar_id = uow, pasarela, reloj, generar_id

    # -- consultas ---------------------------------------------------------- #
    def obtener(self, sesion_id: str) -> Sesion:
        sesion = self.uow.sesiones.obtener(sesion_id)
        if sesion is None:
            raise NoEncontrado(f"La sesión {sesion_id} no existe")
        return sesion

    def listar(self, estado: EstadoSesion | None = None) -> list[Sesion]:
        sesiones = self.uow.sesiones.listar()
        return [s for s in sesiones if estado is None or s.estado is estado]

    def obtener_tutor(self, tutor_id: str) -> Tutor:
        tutor = self.uow.tutores.obtener(tutor_id)
        if tutor is None:
            raise NoEncontrado(f"El tutor {tutor_id} no existe")
        return tutor

    # -- US-01, US-02, US-03, US-10 ----------------------------------------- #
    def reservar(self, rol: Rol, solicitud: SolicitudReserva) -> Sesion:
        exigir_rol(rol, Rol.ESTUDIANTE)
        if self.uow.estudiantes.obtener(solicitud.estudiante_id) is None:
            raise NoEncontrado(f"El estudiante {solicitud.estudiante_id} no existe")
        ahora = self.reloj.ahora()
        if not AnticipacionMinima(ahora).es_satisfecha_por(solicitud):
            raise ReglaNegocioViolada(MSG_ANTICIPACION_RESERVA)

        ocupados = inicios_activos_por_tutor(self.uow.sesiones.listar())
        tutor = seleccionar_tutor(self.uow.tutores.listar(), solicitud, ocupados)
        if tutor is None:
            raise RecursoNoDisponible(MSG_SIN_TUTOR)

        politica = self.uow.politicas.obtener()
        sesion_id = self.generar_id()
        # Si el cobro falla se lanza PagoRechazado y la sesión no se crea (US-03).
        referencia = self.pasarela.cobrar(
            solicitud.estudiante_id, politica.precio, f"Sesión {sesion_id}"
        )
        try:
            sesion = Sesion.reservar(
                sesion_id, solicitud, tutor.id, politica.precio, referencia, ahora
            )
            self.uow.sesiones.guardar(sesion)
            self.uow.commit()
        except Exception:
            # Compensación: no dejar cobrado un pago sin sesión registrada.
            self.uow.rollback()
            self.pasarela.reembolsar(referencia, politica.precio)
            raise
        return sesion

    # -- US-14 -------------------------------------------------------------- #
    def registrar_grabacion(
        self, rol: Rol, sesion_id: str, url: str, inicio: datetime, fin: datetime
    ) -> Sesion:
        exigir_rol(rol, Rol.SISTEMA, Rol.SOPORTE)
        sesion = self.obtener(sesion_id)
        sesion.registrar_grabacion(Grabacion(url, inicio, fin))
        if sesion.estado is EstadoSesion.REEMBOLSADA:
            self.pasarela.reembolsar(sesion.referencia_pago, sesion.monto_reembolso)
        self.uow.sesiones.guardar(sesion)
        self.uow.commit()
        return sesion

    # -- US-11 -------------------------------------------------------------- #
    def liquidar(self, rol: Rol, sesion_id: str) -> ResultadoLiquidacion:
        exigir_rol(rol, Rol.SISTEMA, Rol.SOPORTE)
        sesion = self.obtener(sesion_id)
        if sesion.estado is EstadoSesion.REEMBOLSADA:
            return ResultadoLiquidacion(
                sesion.id,
                PAGO_NO_APLICABLE,
                Dinero.cero(),
                Dinero.cero(),
                mensaje="La sesión generó un reembolso total; no se transfiere al tutor",
            )
        liquidacion = sesion.liquidar(self.uow.politicas.obtener(), self.reloj.ahora())
        referencia = self.pasarela.transferir(
            sesion.tutor_id, liquidacion.monto_tutor, f"Liquidación {sesion.id}"
        )
        self.uow.sesiones.guardar(sesion)
        self.uow.commit()
        return ResultadoLiquidacion(
            sesion.id, sesion.estado_pago, liquidacion.monto_tutor, liquidacion.comision, referencia
        )

    # -- US-05, US-08, US-12, US-13 ----------------------------------------- #
    def cancelar(
        self,
        rol: Rol,
        sesion_id: str,
        solicitante: Solicitante,
        motivo: str,
        justificada: bool = False,
    ) -> Sesion:
        ahora = self.reloj.ahora()
        sesion = self.obtener(sesion_id)
        sesion.cancelar(rol, solicitante, motivo, ahora, justificada)
        if sesion.monto_reembolso.monto > 0:
            self.pasarela.reembolsar(sesion.referencia_pago, sesion.monto_reembolso)
        if Solicitante(solicitante) is Solicitante.TUTOR:
            tutor = self.obtener_tutor(sesion.tutor_id)
            tutor.registrar_cancelacion(sesion.tutor_penalizado, ahora)
            self.uow.tutores.guardar(tutor)
        self.uow.sesiones.guardar(sesion)
        self.uow.commit()
        return sesion

    # -- US-04, RN-10 ------------------------------------------------------- #
    def calificar(self, rol: Rol, sesion_id: str, puntuacion: int) -> Sesion:
        sesion = self.obtener(sesion_id)
        sesion.calificar(rol, puntuacion, self.reloj.ahora())
        self.uow.sesiones.guardar(sesion)
        self.uow.commit()
        return sesion

    # -- US-06, US-07 ------------------------------------------------------- #
    def solicitar_cambio(self, rol: Rol, sesion_id: str, tipo: TipoCambio, valor: str) -> Sesion:
        exigir_rol(rol, Rol.ESTUDIANTE)
        sesion = self.obtener(sesion_id)
        sesion.solicitar_cambio(tipo, valor, self.reloj.ahora())
        self.uow.sesiones.guardar(sesion)
        self.uow.commit()
        return sesion

    def aplicar_cambio(self, rol: Rol, sesion_id: str) -> Sesion:
        ahora = self.reloj.ahora()
        sesion = self.obtener(sesion_id)
        cambio = sesion.aplicar_cambio(rol, ahora)
        # El tutor asignado debe seguir cumpliendo la regla de asignación.
        solicitud = SolicitudReserva(
            sesion.estudiante_id,
            sesion.materia,
            sesion.tema,
            sesion.modalidad,
            sesion.inicio,
            sesion.zona,
        )
        otras = [s for s in self.uow.sesiones.listar() if s.id != sesion.id]
        ocupados = tuple(inicios_activos_por_tutor(otras).get(sesion.tutor_id, ()))
        candidato = CandidatoTutor(self.obtener_tutor(sesion.tutor_id), solicitud, ocupados)
        fallas = regla_asignacion().incumplidas(candidato)
        if fallas:
            self.uow.rollback()
            raise RecursoNoDisponible(
                f"El tutor asignado no cumple con el cambio de {cambio.tipo.value.lower()} "
                f"({', '.join(fallas)}); Soporte debe reasignar"
            )
        self.uow.sesiones.guardar(sesion)
        self.uow.commit()
        return sesion

    # -- US-09 -------------------------------------------------------------- #
    def actualizar_disponibilidad(
        self, rol: Rol, tutor_id: str, bloques: list[BloqueDisponibilidad]
    ) -> Tutor:
        exigir_rol(rol, Rol.TUTOR)
        tutor = self.obtener_tutor(tutor_id)
        confirmadas = [
            s.inicio
            for s in self.uow.sesiones.listar()
            if s.tutor_id == tutor_id and s.estado is EstadoSesion.CONFIRMADA
        ]
        tutor.actualizar_disponibilidad(bloques, confirmadas)
        self.uow.tutores.guardar(tutor)
        self.uow.commit()
        return tutor


class ServicioPoliticas:
    """US-16: Administración define políticas; aplica solo a liquidaciones futuras."""

    def __init__(self, uow: UnidadDeTrabajo):
        self.uow = uow

    def obtener(self) -> PoliticaTarifas:
        return self.uow.politicas.obtener()

    def actualizar_comision(self, rol: Rol, porcentaje: Decimal) -> PoliticaTarifas:
        exigir_rol(rol, Rol.ADMINISTRADOR)
        politica = self.uow.politicas.obtener().con_comision(porcentaje)
        self.uow.politicas.guardar(politica)
        self.uow.commit()
        return politica
