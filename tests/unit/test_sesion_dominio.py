"""Agregado Sesion: RN-01..RN-11 y su máquina de estados."""

from datetime import time, timedelta
from decimal import Decimal

import pytest

from src.domain.comun import (
    DatosInvalidos,
    Dinero,
    PermisoDenegado,
    ReglaNegocioViolada,
    Rol,
    TransicionInvalida,
)
from src.domain.sesiones.modelo import (
    MSG_ANTICIPACION_RESERVA,
    MSG_PLAZO_CALIFICACION,
    PAGO_NO_APLICABLE,
    PRECIO_SESION,
    BloqueDisponibilidad,
    EstadoSesion,
    Grabacion,
    Modalidad,
    PoliticaTarifas,
    Sesion,
    Solicitante,
    SolicitudReserva,
    TipoCambio,
    Tutor,
)
from tests.conftest import AHORA, JUEVES_10, solicitud


def nueva_sesion(inicio=JUEVES_10, ahora=AHORA, **kw) -> Sesion:
    return Sesion.reservar("SES-1", solicitud(inicio, **kw), "AUL-T01", PRECIO_SESION, "COB-1", ahora)


def grabacion(minutos: int, inicio=JUEVES_10) -> Grabacion:
    return Grabacion("https://video/1.mp4", inicio, inicio + timedelta(minutes=minutos))


# -- Reserva (US-01, RN-06) ------------------------------------------------- #
def test_reserva_crea_sesion_confirmada_con_evento():
    sesion = nueva_sesion()
    assert sesion.estado is EstadoSesion.CONFIRMADA
    assert sesion.estado_pago == "Pagado"
    assert sesion.fin - sesion.inicio == timedelta(minutes=90)
    assert [e.nombre for e in sesion.eventos] == ["SesionReservada"]


def test_reserva_con_exactamente_48_horas_es_valida():
    assert nueva_sesion(inicio=AHORA + timedelta(hours=48)).estado is EstadoSesion.CONFIRMADA


def test_reserva_con_menos_de_48_horas_se_rechaza():
    with pytest.raises(ReglaNegocioViolada, match=MSG_ANTICIPACION_RESERVA):
        nueva_sesion(inicio=AHORA + timedelta(hours=47, minutes=59))


def test_solicitud_valida_datos():
    with pytest.raises(DatosInvalidos):
        solicitud(materia="  ")
    with pytest.raises(DatosInvalidos, match="zona"):
        solicitud(modalidad=Modalidad.PRESENCIAL)
    with pytest.raises(ValueError):
        solicitud(modalidad="A_DISTANCIA")


# -- Grabación (US-14, RN-08) ----------------------------------------------- #
def test_grabacion_de_63_minutos_es_70_por_ciento_y_completa():
    sesion = nueva_sesion()
    sesion.registrar_grabacion(grabacion(63))
    assert sesion.estado is EstadoSesion.COMPLETADA
    assert sesion.grabacion.porcentaje_grabado == Decimal("70.00")
    assert sesion.eventos[-1].nombre == "SesionCompletada"


def test_grabacion_de_62_minutos_reembolsa_el_total():
    sesion = nueva_sesion()
    sesion.registrar_grabacion(grabacion(62))
    assert sesion.estado is EstadoSesion.REEMBOLSADA
    assert sesion.monto_reembolso == PRECIO_SESION
    assert sesion.estado_pago == PAGO_NO_APLICABLE
    assert sesion.eventos[-1].nombre == "SesionReembolsada"


def test_grabacion_invalida():
    with pytest.raises(DatosInvalidos):
        Grabacion("", JUEVES_10, JUEVES_10 + timedelta(minutes=5))
    with pytest.raises(DatosInvalidos):
        Grabacion("u", JUEVES_10, JUEVES_10)


def test_no_se_registra_grabacion_dos_veces():
    sesion = nueva_sesion()
    sesion.registrar_grabacion(grabacion(90))
    eventos = len(sesion.eventos)
    with pytest.raises(TransicionInvalida):
        sesion.registrar_grabacion(grabacion(90))
    assert len(sesion.eventos) == eventos


# -- Liquidación (US-11, RN-02) --------------------------------------------- #
def test_liquidacion_160_tutor_40_comision():
    sesion = nueva_sesion()
    sesion.registrar_grabacion(grabacion(90))
    assert sesion.estado_pago == "Pendiente de liquidar"
    liq = sesion.liquidar(PoliticaTarifas(), AHORA)
    assert (liq.monto_tutor, liq.comision) == (Dinero.mxn("160"), Dinero.mxn("40"))
    assert sesion.estado is EstadoSesion.LIQUIDADA
    assert sesion.estado_pago == "Liquidado"


def test_no_se_liquida_sesion_reembolsada_ni_confirmada():
    reembolsada = nueva_sesion()
    reembolsada.registrar_grabacion(grabacion(30))
    with pytest.raises(TransicionInvalida):
        reembolsada.liquidar(PoliticaTarifas(), AHORA)
    with pytest.raises(TransicionInvalida):
        nueva_sesion().liquidar(PoliticaTarifas(), AHORA)


def test_politica_valida_porcentaje():
    with pytest.raises(DatosInvalidos):
        PoliticaTarifas(porcentaje_comision=Decimal("120"))
    with pytest.raises(DatosInvalidos):
        PoliticaTarifas(porcentaje_comision=20)  # type: ignore[arg-type]
    liq = PoliticaTarifas().con_comision(Decimal("25")).liquidar()
    assert liq.monto_tutor == Dinero.mxn("150")


# -- Cancelación (US-05, US-08, US-12, US-13, RN-09, RN-11) ----------------- #
@pytest.mark.parametrize("rol", [Rol.ESTUDIANTE, Rol.TUTOR, Rol.ADMINISTRADOR, Rol.SISTEMA])
def test_solo_soporte_cancela(rol):
    sesion = nueva_sesion()
    with pytest.raises(PermisoDenegado, match="Solo Soporte"):
        sesion.cancelar(rol, Solicitante.ESTUDIANTE, "motivo", AHORA)
    assert sesion.estado is EstadoSesion.CONFIRMADA


def test_estudiante_cancela_con_anticipacion_reembolso_total():
    sesion = nueva_sesion()
    sesion.cancelar(Rol.SOPORTE, Solicitante.ESTUDIANTE, "Examen", AHORA)
    assert sesion.estado is EstadoSesion.CANCELADA
    assert sesion.monto_reembolso == PRECIO_SESION
    assert sesion.estado_pago == "Reembolsado"
    assert not sesion.tutor_penalizado


def test_estudiante_cancela_tarde_sin_reembolso():
    sesion = nueva_sesion()
    sesion.cancelar(Rol.SOPORTE, Solicitante.ESTUDIANTE, "Imprevisto", JUEVES_10 - timedelta(hours=10))
    assert sesion.monto_reembolso == Dinero.cero()
    assert sesion.estado_pago == "Sin reembolso"


def test_tutor_cancela_tarde_sin_justificar_se_penaliza():
    sesion = nueva_sesion()
    sesion.cancelar(Rol.SOPORTE, Solicitante.TUTOR, "No puedo", JUEVES_10 - timedelta(hours=5))
    assert sesion.tutor_penalizado
    assert sesion.monto_reembolso == PRECIO_SESION


def test_tutor_cancela_tarde_justificado_no_se_penaliza():
    sesion = nueva_sesion()
    sesion.cancelar(Rol.SOPORTE, Solicitante.TUTOR, "Hospital", JUEVES_10 - timedelta(hours=5), justificada=True)
    assert not sesion.tutor_penalizado


def test_cancelacion_requiere_motivo_y_estado_confirmado():
    sesion = nueva_sesion()
    with pytest.raises(DatosInvalidos):
        sesion.cancelar(Rol.SOPORTE, Solicitante.ESTUDIANTE, " ", AHORA)
    sesion.registrar_grabacion(grabacion(90))
    with pytest.raises(TransicionInvalida):
        sesion.cancelar(Rol.SOPORTE, Solicitante.ESTUDIANTE, "tarde", AHORA)


# -- Calificación (US-04, RN-10) -------------------------------------------- #
def sesion_completada() -> Sesion:
    sesion = nueva_sesion()
    sesion.registrar_grabacion(grabacion(90))
    return sesion


def test_calificacion_mutua_dentro_de_24_horas():
    sesion = sesion_completada()
    despues = JUEVES_10 + timedelta(hours=3)
    sesion.calificar(Rol.ESTUDIANTE, 5, despues)
    sesion.calificar(Rol.TUTOR, 4, despues)
    assert (sesion.calificacion_tutor, sesion.calificacion_estudiante) == (5, 4)


def test_calificacion_fuera_de_plazo():
    sesion = sesion_completada()
    with pytest.raises(ReglaNegocioViolada, match=MSG_PLAZO_CALIFICACION):
        sesion.calificar(Rol.ESTUDIANTE, 5, JUEVES_10 + timedelta(hours=26))


def test_calificacion_reglas():
    with pytest.raises(TransicionInvalida):
        nueva_sesion().calificar(Rol.ESTUDIANTE, 5, JUEVES_10)
    sesion = sesion_completada()
    with pytest.raises(DatosInvalidos):
        sesion.calificar(Rol.ESTUDIANTE, 6, JUEVES_10 + timedelta(hours=2))
    with pytest.raises(DatosInvalidos):
        sesion.calificar(Rol.ESTUDIANTE, True, JUEVES_10 + timedelta(hours=2))
    with pytest.raises(PermisoDenegado):
        sesion.calificar(Rol.SOPORTE, 5, JUEVES_10 + timedelta(hours=2))
    sesion.calificar(Rol.ESTUDIANTE, 3, JUEVES_10 + timedelta(hours=2))
    with pytest.raises(TransicionInvalida):
        sesion.calificar(Rol.ESTUDIANTE, 4, JUEVES_10 + timedelta(hours=2))


# -- Cambios (US-06, US-07) ------------------------------------------------- #
def test_cambio_de_modalidad_pendiente_y_aplicado_por_soporte():
    sesion = nueva_sesion(modalidad=Modalidad.PRESENCIAL, zona="Monterrey")
    sesion.solicitar_cambio(TipoCambio.MODALIDAD, "EN_LINEA", AHORA)
    assert sesion.cambio_pendiente.valor == "EN_LINEA"
    with pytest.raises(PermisoDenegado):
        sesion.aplicar_cambio(Rol.ADMINISTRADOR, AHORA)
    sesion.aplicar_cambio(Rol.SOPORTE, AHORA)
    assert sesion.modalidad is Modalidad.EN_LINEA and sesion.cambio_pendiente is None


def test_cambio_de_horario():
    sesion = nueva_sesion()
    nuevo = JUEVES_10 + timedelta(days=1)
    sesion.solicitar_cambio(TipoCambio.HORARIO, nuevo.isoformat(), AHORA)
    sesion.aplicar_cambio(Rol.SOPORTE, AHORA)
    assert sesion.inicio == nuevo


def test_cambios_rechazados_sin_48_horas():
    sesion = nueva_sesion()
    tarde = JUEVES_10 - timedelta(hours=20)
    with pytest.raises(ReglaNegocioViolada, match="horario requieren mínimo 48 horas"):
        sesion.solicitar_cambio(TipoCambio.HORARIO, JUEVES_10.isoformat(), tarde)
    with pytest.raises(ReglaNegocioViolada, match="modalidad requieren mínimo 48 horas"):
        sesion.solicitar_cambio(TipoCambio.MODALIDAD, "PRESENCIAL", tarde)


def test_cambios_datos_invalidos():
    sesion = nueva_sesion()
    with pytest.raises(DatosInvalidos):
        sesion.solicitar_cambio(TipoCambio.HORARIO, "mañana", AHORA)
    with pytest.raises(ReglaNegocioViolada):
        sesion.solicitar_cambio(TipoCambio.HORARIO, (AHORA + timedelta(hours=5)).isoformat(), AHORA)
    with pytest.raises(DatosInvalidos, match="zona"):
        sesion.solicitar_cambio(TipoCambio.MODALIDAD, "PRESENCIAL", AHORA)
    with pytest.raises(TransicionInvalida):
        sesion.aplicar_cambio(Rol.SOPORTE, AHORA)


# -- Tutor (US-09, RN-09) --------------------------------------------------- #
def tutor() -> Tutor:
    return Tutor("T", "Tutor", frozenset({"Python"}), frozenset({"EN_LINEA"}), "Monterrey",
                 (BloqueDisponibilidad(3, time(8), time(20)),))


def test_tutor_valida_datos():
    with pytest.raises(DatosInvalidos):
        Tutor("T", "Tutor", frozenset(), frozenset({"EN_LINEA"}), "MTY")
    with pytest.raises(DatosInvalidos):
        Tutor("T", "Tutor", frozenset({"x"}), frozenset(), "MTY")
    with pytest.raises(DatosInvalidos):
        BloqueDisponibilidad(7, time(8), time(9))
    with pytest.raises(DatosInvalidos):
        BloqueDisponibilidad(1, time(9), time(8))


def test_tutor_no_quita_bloque_con_sesion_confirmada():
    t = tutor()
    with pytest.raises(ReglaNegocioViolada, match="sesiones confirmadas"):
        t.actualizar_disponibilidad([BloqueDisponibilidad(0, time(8), time(20))], [JUEVES_10])
    t.actualizar_disponibilidad([BloqueDisponibilidad(3, time(9), time(12))], [JUEVES_10])
    assert t.bloques[0].hora_inicio == time(9)


def test_tutor_penalizacion():
    t = tutor()
    assert t.estado_penalizacion == "SIN PENALIZACIÓN"
    t.registrar_cancelacion(False, AHORA)
    t.registrar_cancelacion(True, AHORA)
    assert (t.cancelaciones, t.penalizaciones) == (2, 1)
    assert t.estado_penalizacion == "PENALIZADO (1)"
    assert [e.nombre for e in t.eventos] == ["TutorPenalizado"]


def test_extraer_eventos_vacia_la_lista():
    sesion = nueva_sesion()
    assert len(sesion.extraer_eventos()) == 1
    assert sesion.eventos == ()


def test_solicitud_usa_utc():
    s = SolicitudReserva("E", "Python", "t", Modalidad.EN_LINEA, JUEVES_10)
    assert s.inicio.utcoffset() == timedelta(0)


def test_cambio_a_modalidad_inexistente():
    with pytest.raises(DatosInvalidos, match="Modalidad inválida"):
        nueva_sesion().solicitar_cambio(TipoCambio.MODALIDAD, "A_DISTANCIA", AHORA)
