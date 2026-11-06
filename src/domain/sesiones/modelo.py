"""Contexto Sesiones de asesoría (núcleo del BRD de AulaPlus).

Reglas implementadas: RN-01 tarifa $200, RN-02 comisión 20 % / 80 %, RN-03 90 min,
RN-04 máximo 5 sesiones por día, RN-06 ventana de 48 h, RN-08 umbral 70 %,
RN-09 penalización por cancelación tardía, RN-10 calificación en 24 h,
RN-11 / US-13 solo Soporte ejecuta cancelaciones y cambios.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta
from decimal import Decimal
from enum import Enum

from src.domain.comun import (
    MENSAJE_SOLO_SOPORTE,
    ZONA_NEGOCIO,
    AgregadoRaiz,
    DatosInvalidos,
    Dinero,
    ReglaNegocioViolada,
    Rol,
    TransicionInvalida,
    a_utc,
    exigir_rol,
)
from src.domain.maquina_estados import MaquinaEstados

PRECIO_SESION = Dinero.mxn("200")  # RN-01
PORCENTAJE_COMISION = Decimal("20")  # RN-02
DURACION_SESION = timedelta(minutes=90)  # RN-03
MAX_SESIONES_POR_DIA = 5  # RN-04
ANTICIPACION_MINIMA = timedelta(hours=48)  # RN-06
PORCENTAJE_MINIMO_GRABADO = 70  # RN-08
VENTANA_CALIFICACION = timedelta(hours=24)  # RN-10

MSG_ANTICIPACION_RESERVA = "La reserva debe realizarse con al menos 48 horas de anticipación"
MSG_SIN_TUTOR = "No hay tutores disponibles para los criterios seleccionados"
MSG_PAGO_FALLIDO = "El pago no pudo ser procesado. Intente nuevamente"
MSG_PLAZO_CALIFICACION = "El periodo de calificación ha finalizado"
MSG_DISPONIBILIDAD_OCUPADA = "No se puede modificar disponibilidad que contiene sesiones confirmadas"
PAGO_NO_APLICABLE = "No aplicable – reembolso"


class Modalidad(str, Enum):
    EN_LINEA = "EN_LINEA"
    PRESENCIAL = "PRESENCIAL"


class EstadoSesion(str, Enum):
    CONFIRMADA = "CONFIRMADA"
    COMPLETADA = "COMPLETADA"
    REEMBOLSADA = "REEMBOLSADA"
    LIQUIDADA = "LIQUIDADA"
    CANCELADA = "CANCELADA"


class Solicitante(str, Enum):
    ESTUDIANTE = "ESTUDIANTE"
    TUTOR = "TUTOR"


class TipoCambio(str, Enum):
    HORARIO = "HORARIO"
    MODALIDAD = "MODALIDAD"


MAQUINA_SESION: MaquinaEstados[EstadoSesion] = MaquinaEstados(
    "Sesion",
    {
        (EstadoSesion.CONFIRMADA, "completar"): EstadoSesion.COMPLETADA,
        (EstadoSesion.CONFIRMADA, "reembolsar"): EstadoSesion.REEMBOLSADA,
        (EstadoSesion.CONFIRMADA, "cancelar"): EstadoSesion.CANCELADA,
        (EstadoSesion.COMPLETADA, "liquidar"): EstadoSesion.LIQUIDADA,
    },
)


def _texto(valor: str, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise DatosInvalidos(f"{campo} es obligatorio")
    return valor.strip()


# --------------------------------------------------------------------------- #
# Value Objects
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Liquidacion:
    precio: Dinero
    comision: Dinero
    monto_tutor: Dinero


@dataclass(frozen=True)
class PoliticaTarifas:
    """Política vigente (US-16: Administración puede cambiar la comisión)."""

    precio: Dinero = PRECIO_SESION
    porcentaje_comision: Decimal = PORCENTAJE_COMISION

    def __post_init__(self) -> None:
        if not isinstance(self.porcentaje_comision, Decimal):
            raise DatosInvalidos("El porcentaje de comisión debe ser Decimal")
        if not Decimal(0) <= self.porcentaje_comision <= Decimal(100):
            raise DatosInvalidos("El porcentaje de comisión debe estar entre 0 y 100")

    def liquidar(self, precio: Dinero | None = None) -> Liquidacion:
        base = precio or self.precio
        comision = base.porcentaje(self.porcentaje_comision)
        return Liquidacion(base, comision, base - comision)

    def con_comision(self, porcentaje: Decimal) -> PoliticaTarifas:
        return replace(self, porcentaje_comision=porcentaje)


@dataclass(frozen=True)
class Grabacion:
    """Evidencia con marcas de tiempo (NB-04)."""

    url: str
    inicio: datetime
    fin: datetime

    def __post_init__(self) -> None:
        _texto(self.url, "La URL de la grabación")
        object.__setattr__(self, "inicio", a_utc(self.inicio, "inicio de la grabación"))
        object.__setattr__(self, "fin", a_utc(self.fin, "fin de la grabación"))
        if self.fin <= self.inicio:
            raise DatosInvalidos("El fin de la grabación debe ser posterior al inicio")

    @property
    def duracion(self) -> timedelta:
        return self.fin - self.inicio

    @property
    def porcentaje_grabado(self) -> Decimal:
        segundos = Decimal(int(self.duracion.total_seconds()))
        total = Decimal(int(DURACION_SESION.total_seconds()))
        return (segundos * 100 / total).quantize(Decimal("0.01"))

    def cubre_porcentaje_minimo(self) -> bool:
        # Comparación exacta con timedelta: 63 min de 90 = 70 % exacto, sí cubre.
        return self.duracion * 100 >= DURACION_SESION * PORCENTAJE_MINIMO_GRABADO


@dataclass(frozen=True)
class BloqueDisponibilidad:
    """Bloque semanal en hora local de Monterrey. dia_semana: 0 = lunes ... 6 = domingo."""

    dia_semana: int
    hora_inicio: time
    hora_fin: time

    def __post_init__(self) -> None:
        if isinstance(self.dia_semana, bool) or self.dia_semana not in range(7):
            raise DatosInvalidos("dia_semana debe estar entre 0 (lunes) y 6 (domingo)")
        if self.hora_fin <= self.hora_inicio:
            raise DatosInvalidos("La hora de fin del bloque debe ser posterior a la de inicio")

    def contiene(self, inicio: datetime, fin: datetime) -> bool:
        local_inicio = inicio.astimezone(ZONA_NEGOCIO)
        local_fin = fin.astimezone(ZONA_NEGOCIO)
        return (
            local_inicio.weekday() == self.dia_semana
            and local_inicio.date() == local_fin.date()
            and self.hora_inicio <= local_inicio.time()
            and local_fin.time() <= self.hora_fin
        )


@dataclass(frozen=True)
class SolicitudReserva:
    """Criterios elegidos por el estudiante (US-01)."""

    estudiante_id: str
    materia: str
    tema: str
    modalidad: Modalidad
    inicio: datetime
    zona: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "estudiante_id", _texto(self.estudiante_id, "estudiante_id"))
        object.__setattr__(self, "materia", _texto(self.materia, "La materia"))
        object.__setattr__(self, "tema", _texto(self.tema, "El tema"))
        object.__setattr__(self, "modalidad", Modalidad(self.modalidad))
        object.__setattr__(self, "inicio", a_utc(self.inicio, "inicio"))
        if self.modalidad is Modalidad.PRESENCIAL and not (self.zona and self.zona.strip()):
            raise DatosInvalidos("La modalidad presencial requiere indicar la zona")

    @property
    def fin(self) -> datetime:
        return self.inicio + DURACION_SESION


@dataclass(frozen=True)
class CambioPendiente:
    tipo: TipoCambio
    valor: str  # fecha ISO 8601 (HORARIO) o nombre de modalidad (MODALIDAD)


# --------------------------------------------------------------------------- #
# Entidad / agregado Tutor
# --------------------------------------------------------------------------- #
@dataclass
class Tutor(AgregadoRaiz):
    id: str
    nombre: str
    materias: frozenset[str]
    modalidades: frozenset[Modalidad]
    zona: str
    bloques: tuple[BloqueDisponibilidad, ...] = ()
    cancelaciones: int = 0
    penalizaciones: int = 0

    def __post_init__(self) -> None:
        _texto(self.id, "El id del tutor")
        _texto(self.nombre, "El nombre del tutor")
        self.materias = frozenset(m.strip().lower() for m in self.materias if m.strip())
        self.modalidades = frozenset(Modalidad(m) for m in self.modalidades)
        if not self.materias:
            raise DatosInvalidos("El tutor debe impartir al menos una materia")
        if not self.modalidades:
            raise DatosInvalidos("El tutor debe ofrecer al menos una modalidad")
        self.bloques = tuple(self.bloques)

    def imparte(self, materia: str) -> bool:
        return materia.strip().lower() in self.materias

    def disponible_en(self, inicio: datetime, fin: datetime) -> bool:
        return any(bloque.contiene(inicio, fin) for bloque in self.bloques)

    @property
    def estado_penalizacion(self) -> str:
        if self.penalizaciones == 0:
            return "SIN PENALIZACIÓN"
        return f"PENALIZADO ({self.penalizaciones})"

    def actualizar_disponibilidad(
        self, bloques: list[BloqueDisponibilidad], sesiones_confirmadas: list[datetime]
    ) -> None:
        """US-09: no se puede quitar un bloque que contiene una sesión confirmada."""
        nuevos = tuple(bloques)
        for inicio in sesiones_confirmadas:
            fin = inicio + DURACION_SESION
            if not any(b.contiene(inicio, fin) for b in nuevos):
                raise ReglaNegocioViolada(MSG_DISPONIBILIDAD_OCUPADA)
        self.bloques = nuevos
        self._registrar("DisponibilidadActualizada", bloques=len(nuevos))

    def registrar_cancelacion(self, penalizar: bool, ocurrido_en: datetime) -> None:
        """RN-09 / NB-08: cuenta cancelaciones y aplica penalización si fue tardía."""
        self.cancelaciones += 1
        if penalizar:
            self.penalizaciones += 1
            self._registrar("TutorPenalizado", ocurrido_en, penalizaciones=self.penalizaciones)


# --------------------------------------------------------------------------- #
# Agregado Sesion
# --------------------------------------------------------------------------- #
@dataclass
class Sesion(AgregadoRaiz):
    id: str
    estudiante_id: str
    tutor_id: str
    materia: str
    tema: str
    modalidad: Modalidad
    inicio: datetime
    precio: Dinero
    referencia_pago: str
    zona: str | None = None
    estado: EstadoSesion = EstadoSesion.CONFIRMADA
    grabacion: Grabacion | None = None
    liquidacion: Liquidacion | None = None
    monto_reembolso: Dinero = field(default_factory=Dinero.cero)
    tutor_penalizado: bool = False
    calificacion_tutor: int | None = None  # la da el estudiante (US-04)
    calificacion_estudiante: int | None = None  # la da el tutor (RN-10)
    cambio_pendiente: CambioPendiente | None = None

    def __post_init__(self) -> None:
        self.inicio = a_utc(self.inicio, "inicio")
        self.modalidad = Modalidad(self.modalidad)
        self.estado = EstadoSesion(self.estado)

    @property
    def fin(self) -> datetime:
        return self.inicio + DURACION_SESION

    @property
    def estado_pago(self) -> str:
        if self.estado is EstadoSesion.CONFIRMADA:
            return "Pagado"
        if self.estado is EstadoSesion.COMPLETADA:
            return "Pendiente de liquidar"
        if self.estado is EstadoSesion.LIQUIDADA:
            return "Liquidado"
        if self.estado is EstadoSesion.REEMBOLSADA:
            return PAGO_NO_APLICABLE
        return "Reembolsado" if self.monto_reembolso.monto > 0 else "Sin reembolso"

    @staticmethod
    def tiene_anticipacion(inicio: datetime, ahora: datetime) -> bool:
        return inicio - a_utc(ahora, "ahora") >= ANTICIPACION_MINIMA

    # -- creación (US-01, US-02, US-03) ------------------------------------- #
    @classmethod
    def reservar(
        cls,
        sesion_id: str,
        solicitud: SolicitudReserva,
        tutor_id: str,
        precio: Dinero,
        referencia_pago: str,
        ahora: datetime,
    ) -> Sesion:
        if not cls.tiene_anticipacion(solicitud.inicio, ahora):
            raise ReglaNegocioViolada(MSG_ANTICIPACION_RESERVA)
        sesion = cls(
            id=sesion_id,
            estudiante_id=solicitud.estudiante_id,
            tutor_id=_texto(tutor_id, "tutor_id"),
            materia=solicitud.materia,
            tema=solicitud.tema,
            modalidad=solicitud.modalidad,
            inicio=solicitud.inicio,
            precio=precio,
            referencia_pago=_texto(referencia_pago, "La referencia de pago"),
            zona=solicitud.zona,
        )
        sesion._registrar(
            "SesionReservada", ahora, tutor_id=tutor_id, precio=str(precio.monto)
        )
        return sesion

    # -- cierre con grabación (US-14, RN-08) -------------------------------- #
    def registrar_grabacion(self, grabacion: Grabacion) -> None:
        accion = "completar" if grabacion.cubre_porcentaje_minimo() else "reembolsar"
        destino = MAQUINA_SESION.destino(self.estado, accion)  # valida antes de cambiar
        self.grabacion = grabacion
        self.estado = destino
        if destino is EstadoSesion.REEMBOLSADA:
            self.monto_reembolso = self.precio
            self._registrar(
                "SesionReembolsada",
                grabacion.fin,
                porcentaje_grabado=str(grabacion.porcentaje_grabado),
                reembolso=str(self.precio.monto),
            )
        else:
            self._registrar(
                "SesionCompletada",
                grabacion.fin,
                porcentaje_grabado=str(grabacion.porcentaje_grabado),
            )

    # -- liquidación (US-11, RN-02) ----------------------------------------- #
    def liquidar(self, politica: PoliticaTarifas, ahora: datetime) -> Liquidacion:
        destino = MAQUINA_SESION.destino(self.estado, "liquidar")
        liquidacion = politica.liquidar(self.precio)
        self.liquidacion = liquidacion
        self.estado = destino
        self._registrar(
            "SesionLiquidada",
            ahora,
            monto_tutor=str(liquidacion.monto_tutor.monto),
            comision=str(liquidacion.comision.monto),
        )
        return liquidacion

    # -- cancelación (US-05, US-08, US-12, US-13, RN-09, RN-11) ------------- #
    def cancelar(
        self,
        rol: Rol,
        solicitante: Solicitante,
        motivo: str,
        ahora: datetime,
        justificada: bool = False,
    ) -> None:
        exigir_rol(rol, Rol.SOPORTE, mensaje=MENSAJE_SOLO_SOPORTE)
        destino = MAQUINA_SESION.destino(self.estado, "cancelar")
        motivo = _texto(motivo, "El motivo de la cancelación")
        solicitante = Solicitante(solicitante)
        con_anticipacion = self.tiene_anticipacion(self.inicio, ahora)

        if solicitante is Solicitante.ESTUDIANTE:
            # Supuesto del equipo: con < 48 h el estudiante no recibe reembolso.
            reembolso = self.precio if con_anticipacion else Dinero.cero()
            penalizar_tutor = False
        else:
            # Ausencia del tutor: el estudiante siempre recibe el 100 %.
            reembolso = self.precio
            penalizar_tutor = not con_anticipacion and not justificada

        self.estado = destino
        self.monto_reembolso = reembolso
        self.tutor_penalizado = penalizar_tutor
        self._registrar(
            "SesionCancelada",
            ahora,
            solicitante=solicitante.value,
            motivo=motivo,
            con_anticipacion=con_anticipacion,
            reembolso=str(reembolso.monto),
            tutor_penalizado=penalizar_tutor,
        )

    # -- calificación mutua (US-04, RN-10) ---------------------------------- #
    def calificar(self, rol: Rol, puntuacion: int, ahora: datetime) -> None:
        exigir_rol(rol, Rol.ESTUDIANTE, Rol.TUTOR)
        if self.estado not in (EstadoSesion.COMPLETADA, EstadoSesion.LIQUIDADA):
            raise TransicionInvalida("Solo una sesión completada puede calificarse")
        if isinstance(puntuacion, bool) or not isinstance(puntuacion, int):
            raise DatosInvalidos("La calificación debe ser un entero de 1 a 5")
        if not 1 <= puntuacion <= 5:
            raise DatosInvalidos("La calificación debe ser un entero de 1 a 5")
        campo = "calificacion_tutor" if rol is Rol.ESTUDIANTE else "calificacion_estudiante"
        if getattr(self, campo) is not None:
            raise TransicionInvalida("Esta parte ya registró su calificación")
        fin_real = self.grabacion.fin if self.grabacion else self.fin
        if a_utc(ahora, "ahora") - fin_real > VENTANA_CALIFICACION:
            raise ReglaNegocioViolada(MSG_PLAZO_CALIFICACION)
        setattr(self, campo, puntuacion)
        self._registrar("SesionCalificada", ahora, por=rol.value, puntuacion=puntuacion)

    # -- cambios de horario / modalidad (US-06, US-07) ---------------------- #
    def solicitar_cambio(self, tipo: TipoCambio, valor: str, ahora: datetime) -> None:
        tipo = TipoCambio(tipo)
        if self.estado is not EstadoSesion.CONFIRMADA:
            raise TransicionInvalida("Solo una sesión confirmada admite cambios")
        if not self.tiene_anticipacion(self.inicio, ahora):
            nombre = "horario" if tipo is TipoCambio.HORARIO else "modalidad"
            raise ReglaNegocioViolada(
                f"Los cambios de {nombre} requieren mínimo 48 horas de anticipación"
            )
        valor = _texto(valor, "El nuevo valor")
        if tipo is TipoCambio.HORARIO:
            nuevo_inicio = _parsear_fecha(valor)
            if not self.tiene_anticipacion(nuevo_inicio, ahora):
                raise ReglaNegocioViolada(MSG_ANTICIPACION_RESERVA)
            valor = nuevo_inicio.isoformat()
        else:
            try:
                nueva = Modalidad(valor)
            except ValueError:
                raise DatosInvalidos("Modalidad inválida: use EN_LINEA o PRESENCIAL") from None
            if nueva is Modalidad.PRESENCIAL and not self.zona:
                raise DatosInvalidos("La modalidad presencial requiere zona registrada")
            valor = nueva.value
        self.cambio_pendiente = CambioPendiente(tipo, valor)
        self._registrar("CambioSolicitado", ahora, tipo=tipo.value, valor=valor)

    def aplicar_cambio(self, rol: Rol, ahora: datetime) -> CambioPendiente:
        exigir_rol(rol, Rol.SOPORTE, mensaje=MENSAJE_SOLO_SOPORTE)
        if self.estado is not EstadoSesion.CONFIRMADA or self.cambio_pendiente is None:
            raise TransicionInvalida("No hay un cambio pendiente que aplicar")
        if not self.tiene_anticipacion(self.inicio, ahora):
            raise ReglaNegocioViolada("El cambio ya no cumple las 48 horas de anticipación")
        cambio = self.cambio_pendiente
        if cambio.tipo is TipoCambio.HORARIO:
            self.inicio = _parsear_fecha(cambio.valor)
        else:
            self.modalidad = Modalidad(cambio.valor)
        self.cambio_pendiente = None
        self._registrar("CambioAplicado", ahora, tipo=cambio.tipo.value, valor=cambio.valor)
        return cambio


def _parsear_fecha(valor: str) -> datetime:
    try:
        fecha = datetime.fromisoformat(valor)
    except ValueError:
        raise DatosInvalidos("La fecha debe estar en formato ISO 8601") from None
    return a_utc(fecha, "nuevo horario")
