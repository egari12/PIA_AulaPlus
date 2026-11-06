"""Casos de uso con repositorios en memoria y pasarela simulada."""

from datetime import timedelta
from decimal import Decimal

import pytest

from src.application.servicios_inscripciones import LineaSolicitada, fecha_iso
from src.application.reportes import ServicioReportes
from src.application.servicios_sesiones import ServicioPoliticas
from src.domain.comun import (
    DatosInvalidos,
    Dinero,
    NoEncontrado,
    PagoRechazado,
    PermisoDenegado,
    RecursoNoDisponible,
    ReglaNegocioViolada,
    Rol,
    TransicionInvalida,
)
from src.domain.inscripciones.modelo import EstadoInscripcion
from src.domain.sesiones.modelo import (
    MSG_SIN_TUTOR,
    PAGO_NO_APLICABLE,
    BloqueDisponibilidad,
    EstadoSesion,
    Modalidad,
    Solicitante,
    TipoCambio,
)
from tests.conftest import AHORA, JUEVES_10, solicitud


def reservar(servicio, **kw):
    return servicio.reservar(Rol.ESTUDIANTE, solicitud(**kw))


# -- Reserva ---------------------------------------------------------------- #
def test_reserva_asigna_tutor_cobra_y_guarda(servicio, uow, pasarela):
    sesion = reservar(servicio)
    assert sesion.tutor_id == "AUL-T01" and sesion.estado is EstadoSesion.CONFIRMADA
    assert pasarela.operaciones[0].tipo == "cobro" and pasarela.operaciones[0].monto == Dinero.mxn("200")
    assert uow.sesiones.obtener(sesion.id).referencia_pago == sesion.referencia_pago
    assert [e.nombre for e in uow.sesiones.eventos_de(sesion.id)] == ["SesionReservada"]


def test_reserva_reparte_carga_entre_tutores(servicio):
    primera = reservar(servicio)
    segunda = reservar(servicio, estudiante="AUL-C002")  # misma hora: Ana ya está ocupada
    assert (primera.tutor_id, segunda.tutor_id) == ("AUL-T01", "AUL-T05")
    with pytest.raises(RecursoNoDisponible, match=MSG_SIN_TUTOR):
        reservar(servicio, estudiante="AUL-C003")


def test_sexta_sesion_del_dia_busca_otro_tutor(servicio):
    tutores = [reservar(servicio, inicio=JUEVES_10.replace(hour=8) + timedelta(hours=2 * i)).tutor_id
               for i in range(6)]
    assert tutores[:5] == ["AUL-T01", "AUL-T05", "AUL-T01", "AUL-T05", "AUL-T01"]
    assert tutores.count("AUL-T01") <= 5


def test_reserva_sin_anticipacion_no_cobra(servicio, pasarela):
    with pytest.raises(ReglaNegocioViolada):
        reservar(servicio, inicio=AHORA + timedelta(hours=3))
    assert pasarela.operaciones == []


def test_pago_rechazado_no_crea_sesion(servicio, uow):
    with pytest.raises(PagoRechazado, match="no pudo ser procesado"):
        reservar(servicio, estudiante="AUL-C040")
    assert uow.sesiones.listar() == []


def test_si_falla_el_guardado_se_reembolsa(servicio, uow, pasarela, monkeypatch):
    def falla(_):
        raise RuntimeError("BD caída")

    monkeypatch.setattr(uow.sesiones, "guardar", falla)
    with pytest.raises(RuntimeError):
        reservar(servicio)
    assert [op.tipo for op in pasarela.operaciones] == ["cobro", "reembolso"]


def test_solo_estudiante_reserva(servicio):
    with pytest.raises(PermisoDenegado):
        servicio.reservar(Rol.SOPORTE, solicitud())


# -- Grabación y liquidación ------------------------------------------------- #
def test_flujo_completo_hasta_liquidar(servicio, pasarela):
    s = reservar(servicio)
    s = servicio.registrar_grabacion(Rol.SISTEMA, s.id, "u", JUEVES_10, JUEVES_10 + timedelta(minutes=88))
    r = servicio.liquidar(Rol.SISTEMA, s.id)
    assert (r.monto_tutor, r.comision, r.estado_pago) == (Dinero.mxn("160"), Dinero.mxn("40"), "Liquidado")
    assert pasarela.operaciones[-1].tipo == "transferencia"
    assert servicio.obtener(s.id).estado is EstadoSesion.LIQUIDADA


def test_reembolsada_no_se_liquida(servicio, pasarela):
    s = reservar(servicio)
    servicio.registrar_grabacion(Rol.SISTEMA, s.id, "u", JUEVES_10, JUEVES_10 + timedelta(minutes=40))
    r = servicio.liquidar(Rol.SISTEMA, s.id)
    assert r.estado_pago == PAGO_NO_APLICABLE and r.monto_tutor == Dinero.cero()
    assert [op.tipo for op in pasarela.operaciones] == ["cobro", "reembolso"]


def test_comision_nueva_aplica_a_liquidaciones_futuras(servicio, uow):
    ServicioPoliticas(uow).actualizar_comision(Rol.ADMINISTRADOR, Decimal("25"))
    s = reservar(servicio)
    servicio.registrar_grabacion(Rol.SISTEMA, s.id, "u", JUEVES_10, JUEVES_10 + timedelta(minutes=90))
    assert servicio.liquidar(Rol.SOPORTE, s.id).monto_tutor == Dinero.mxn("150")
    with pytest.raises(PermisoDenegado):
        ServicioPoliticas(uow).actualizar_comision(Rol.SOPORTE, Decimal("10"))
    assert ServicioPoliticas(uow).obtener().porcentaje_comision == Decimal("25")


def test_roles_de_grabacion_y_liquidacion(servicio):
    s = reservar(servicio)
    with pytest.raises(PermisoDenegado):
        servicio.registrar_grabacion(Rol.ESTUDIANTE, s.id, "u", JUEVES_10, JUEVES_10 + timedelta(minutes=90))
    with pytest.raises(PermisoDenegado):
        servicio.liquidar(Rol.TUTOR, s.id)


def test_sesion_inexistente(servicio):
    with pytest.raises(NoEncontrado):
        servicio.obtener("NO-EXISTE")
    with pytest.raises(NoEncontrado):
        servicio.obtener_tutor("NO-EXISTE")


# -- Cancelación y reportes ------------------------------------------------- #
def test_cancelacion_tardia_del_tutor_penaliza_y_aparece_en_reporte(servicio, uow, reloj, pasarela):
    s = reservar(servicio)
    reloj.avanzar(timedelta(hours=60))  # faltan 13 h
    s = servicio.cancelar(Rol.SOPORTE, s.id, Solicitante.TUTOR, "Se enfermó sin justificante")
    assert s.estado is EstadoSesion.CANCELADA and s.tutor_penalizado
    assert pasarela.operaciones[-1].tipo == "reembolso"
    tutor = uow.tutores.obtener("AUL-T01")
    assert (tutor.cancelaciones, tutor.penalizaciones) == (1, 1)
    filas = ServicioReportes(uow).cancelaciones_por_tutor(Rol.ADMINISTRADOR)
    assert filas[0].tutor_id == "AUL-T01" and filas[0].estado_penalizacion == "PENALIZADO (1)"


def test_cancelacion_por_estudiante_no_toca_al_tutor(servicio, uow):
    s = reservar(servicio)
    servicio.cancelar(Rol.SOPORTE, s.id, Solicitante.ESTUDIANTE, "Examen")
    assert uow.tutores.obtener("AUL-T01").cancelaciones == 0


def test_cancelacion_por_otro_rol_no_cambia_nada(servicio):
    s = reservar(servicio)
    with pytest.raises(PermisoDenegado, match="Solo Soporte"):
        servicio.cancelar(Rol.ADMINISTRADOR, s.id, Solicitante.ESTUDIANTE, "x")
    assert servicio.obtener(s.id).estado is EstadoSesion.CONFIRMADA


def test_reporte_de_sesiones(servicio, uow):
    a = reservar(servicio)
    b = reservar(servicio, estudiante="AUL-C002")
    servicio.cancelar(Rol.SOPORTE, b.id, Solicitante.ESTUDIANTE, "Examen")
    servicio.registrar_grabacion(Rol.SISTEMA, a.id, "u", JUEVES_10, JUEVES_10 + timedelta(minutes=90))
    servicio.liquidar(Rol.SISTEMA, a.id)
    reporte = ServicioReportes(uow).sesiones(Rol.ADMINISTRADOR, AHORA, AHORA + timedelta(days=7))
    assert reporte.por_estado["LIQUIDADA"] == 1 and reporte.por_estado["CANCELADA"] == 1
    assert reporte.total_cobrado == Dinero.mxn("400")
    assert reporte.total_comisiones == Dinero.mxn("40")
    assert reporte.total_reembolsado == Dinero.mxn("200")
    with pytest.raises(DatosInvalidos):
        ServicioReportes(uow).sesiones(Rol.ADMINISTRADOR, AHORA, AHORA - timedelta(days=1))
    with pytest.raises(PermisoDenegado):
        ServicioReportes(uow).sesiones(Rol.SOPORTE, AHORA, AHORA)


# -- Calificación, cambios y disponibilidad --------------------------------- #
def test_calificar(servicio, reloj):
    s = reservar(servicio)
    servicio.registrar_grabacion(Rol.SISTEMA, s.id, "u", JUEVES_10, JUEVES_10 + timedelta(minutes=90))
    reloj.momento = JUEVES_10 + timedelta(hours=5)
    assert servicio.calificar(Rol.ESTUDIANTE, s.id, 5).calificacion_tutor == 5


def test_cambio_de_horario_aplicado(servicio):
    s = reservar(servicio)
    nuevo = JUEVES_10.replace(hour=15)
    servicio.solicitar_cambio(Rol.ESTUDIANTE, s.id, TipoCambio.HORARIO, nuevo.isoformat())
    assert servicio.aplicar_cambio(Rol.SOPORTE, s.id).inicio == nuevo


def test_cambio_que_el_tutor_no_cubre_se_rechaza(servicio):
    s = reservar(servicio)  # Ana: L-V 8-20
    sabado = JUEVES_10 + timedelta(days=2)
    servicio.solicitar_cambio(Rol.ESTUDIANTE, s.id, TipoCambio.HORARIO, sabado.isoformat())
    with pytest.raises(RecursoNoDisponible, match="reasignar"):
        servicio.aplicar_cambio(Rol.SOPORTE, s.id)
    assert servicio.obtener(s.id).inicio == JUEVES_10


def test_solo_estudiante_solicita_cambio(servicio):
    s = reservar(servicio)
    with pytest.raises(PermisoDenegado):
        servicio.solicitar_cambio(Rol.TUTOR, s.id, TipoCambio.MODALIDAD, "PRESENCIAL")


def test_actualizar_disponibilidad(servicio):
    s = reservar(servicio)
    with pytest.raises(ReglaNegocioViolada):
        servicio.actualizar_disponibilidad(Rol.TUTOR, s.tutor_id, [])
    nuevo = [BloqueDisponibilidad(3, JUEVES_10.time(), JUEVES_10.replace(hour=12).time())]
    assert len(servicio.actualizar_disponibilidad(Rol.TUTOR, s.tutor_id, nuevo).bloques) == 1
    with pytest.raises(PermisoDenegado):
        servicio.actualizar_disponibilidad(Rol.ESTUDIANTE, s.tutor_id, nuevo)


def test_listar_por_estado(servicio):
    reservar(servicio)
    assert len(servicio.listar(EstadoSesion.CONFIRMADA)) == 1
    assert servicio.listar(EstadoSesion.CANCELADA) == []


def test_presencial_en_zona(servicio):
    s = reservar(servicio, modalidad=Modalidad.PRESENCIAL, zona="Monterrey")
    assert s.tutor_id == "AUL-T01"


# -- Inscripciones ---------------------------------------------------------- #
def test_inscripcion_nueva_y_flujo(servicio_insc, uow):
    i = servicio_insc.crear("AUL-C005", [LineaSolicitada("AUL-P001", 2)], autorizada=True)
    assert i.estado is EstadoInscripcion.PREINSCRITA and i.total == Dinero.mxn("810")
    servicio_insc.validar(i.id)
    servicio_insc.inscribir(i.id)
    assert uow.cursos.obtener("AUL-P001").cupo == 11
    assert servicio_insc.finalizar(i.id).estado is EstadoInscripcion.FINALIZADA
    assert len(uow.inscripciones.eventos_de(i.id)) == 3


def test_inscripcion_errores(servicio_insc):
    with pytest.raises(NoEncontrado):
        servicio_insc.crear("NADIE", [], autorizada=True)
    with pytest.raises(NoEncontrado):
        servicio_insc.crear("AUL-C005", [LineaSolicitada("NO", 1)], autorizada=True)
    with pytest.raises(NoEncontrado):
        servicio_insc.obtener("NO")
    with pytest.raises(TransicionInvalida):
        servicio_insc.finalizar("AUL-O001")


def test_beneficio_y_cancelacion(servicio_insc):
    assert isinstance(servicio_insc.evaluar_beneficio("AUL-O001").aplica, bool)
    assert servicio_insc.cancelar("AUL-O002", "Baja").estado is EstadoInscripcion.CANCELADA
    assert len(servicio_insc.listar()) == 60


def test_fecha_iso():
    assert fecha_iso("2026-10-01").day == 1
    with pytest.raises(DatosInvalidos):
        fecha_iso("01/10/2026")
