"""Specifications de asignación automática de tutor (NB-01, US-02, US-10, RN-04, RN-07)."""

from datetime import timedelta

from src.domain.sesiones.especificaciones import (
    AnticipacionMinima,
    BajoLimiteDiario,
    CandidatoTutor,
    DentroDeDisponibilidad,
    ImparteMateria,
    MismaZona,
    OfreceModalidad,
    SinTraslape,
    regla_asignacion,
    seleccionar_tutor,
)
from src.domain.sesiones.modelo import Modalidad
from tests.conftest import AHORA, JUEVES_10, solicitud


def test_anticipacion_minima():
    assert AnticipacionMinima(AHORA).es_satisfecha_por(solicitud())
    assert not AnticipacionMinima(AHORA).es_satisfecha_por(solicitud(AHORA + timedelta(hours=10)))


def test_specs_individuales(tutores):
    ana = tutores["AUL-T01"]  # Python y Bases de datos, en línea y presencial, Monterrey, L-V 8-20
    c = CandidatoTutor(ana, solicitud())
    assert ImparteMateria().es_satisfecha_por(c)
    assert OfreceModalidad().es_satisfecha_por(c)
    assert DentroDeDisponibilidad().es_satisfecha_por(c)
    assert not ImparteMateria().es_satisfecha_por(CandidatoTutor(ana, solicitud(materia="Redes")))
    temprano = solicitud(JUEVES_10.replace(hour=7))
    assert not DentroDeDisponibilidad().es_satisfecha_por(CandidatoTutor(ana, temprano))


def test_zona_solo_importa_si_es_presencial(tutores):
    ana = tutores["AUL-T01"]
    regla = regla_asignacion()
    en_linea = CandidatoTutor(ana, solicitud())
    presencial_mty = CandidatoTutor(ana, solicitud(modalidad=Modalidad.PRESENCIAL, zona="monterrey"))
    presencial_apo = CandidatoTutor(ana, solicitud(modalidad=Modalidad.PRESENCIAL, zona="Apodaca"))
    assert regla.es_satisfecha_por(en_linea)
    assert regla.es_satisfecha_por(presencial_mty)
    assert not regla.es_satisfecha_por(presencial_apo)
    assert MismaZona().es_satisfecha_por(presencial_mty)
    assert "(NOT sesión presencial OR atiende la zona)" in regla.incumplidas(presencial_apo)


def test_limite_de_5_sesiones_por_dia(tutores):
    ana = tutores["AUL-T01"]
    mismo_dia = tuple(JUEVES_10.replace(hour=13) + timedelta(hours=2 * i) for i in range(4))
    assert BajoLimiteDiario().es_satisfecha_por(CandidatoTutor(ana, solicitud(), mismo_dia))
    cinco = mismo_dia + (JUEVES_10.replace(hour=8),)
    assert not BajoLimiteDiario().es_satisfecha_por(CandidatoTutor(ana, solicitud(), cinco))
    otro_dia = tuple(i + timedelta(days=1) for i in cinco)
    assert BajoLimiteDiario().es_satisfecha_por(CandidatoTutor(ana, solicitud(), otro_dia))


def test_sin_traslape(tutores):
    ana = tutores["AUL-T01"]
    traslapa = (JUEVES_10 + timedelta(minutes=60),)
    contigua = (JUEVES_10 + timedelta(minutes=90),)
    assert not SinTraslape().es_satisfecha_por(CandidatoTutor(ana, solicitud(), traslapa))
    assert SinTraslape().es_satisfecha_por(CandidatoTutor(ana, solicitud(), contigua))


def test_seleccion_prefiere_menor_carga(tutores):
    # Jueves 10:00 en línea, Python: cumplen Ana (T01) y Elena (T05).
    elegido = seleccionar_tutor(tutores.values(), solicitud(), {})
    assert elegido.id == "AUL-T01"
    elegido = seleccionar_tutor(tutores.values(), solicitud(), {"AUL-T01": [JUEVES_10.replace(hour=14)]})
    assert elegido.id == "AUL-T05"


def test_seleccion_sin_candidatos(tutores):
    assert seleccionar_tutor(tutores.values(), solicitud(materia="Química"), {}) is None
