"""Agregado Inscripcion con los datos del paquete del docente."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.comun import DatosInvalidos, Dinero, RecursoNoDisponible, TransicionInvalida
from src.domain.inscripciones.especificaciones import (
    BENEFICIO_REFERENCIA,
    PUEDE_PROCESARSE,
    ContextoInscripcion,
)
from src.domain.inscripciones.modelo import (
    Curso,
    EstadoInscripcion,
    Estudiante,
    Inscripcion,
    LineaInscripcion,
)
from src.infrastructure.cargador_csv import cargar_paquete


@pytest.fixture
def paquete():
    return cargar_paquete()


def test_carga_completa(paquete):
    assert (len(paquete.estudiantes), len(paquete.cursos), len(paquete.inscripciones)) == (40, 20, 60)
    assert all(i.estado is EstadoInscripcion.PREINSCRITA for i in paquete.inscripciones.values())


def test_total_calculado_a_mano(paquete):
    # O001: P009 973.00 x 3 + P014 1328.00 x 4 = 2919 + 5312 = 8231.00
    o001 = paquete.inscripciones["AUL-O001"]
    assert o001.total == Dinero.mxn("8231.00")
    assert o001.unidades == 7


def test_operaciones_sin_detalle(paquete):
    vacias = sorted(i.id for i in paquete.inscripciones.values() if not i.lineas)
    assert vacias == ["AUL-O013", "AUL-O039"]
    assert paquete.inscripciones["AUL-O013"].total == Dinero.cero()


def test_linea_valida_cantidad():
    with pytest.raises(DatosInvalidos):
        LineaInscripcion("P", Dinero.mxn("1"), 0)
    with pytest.raises(DatosInvalidos):
        LineaInscripcion("P", Dinero.mxn("1"), True)
    with pytest.raises(DatosInvalidos):
        LineaInscripcion("", Dinero.mxn("1"), 1)


def test_curso_valida_cupo():
    with pytest.raises(DatosInvalidos):
        Curso("P", "x", Dinero.mxn("1"), -1)


def inscripcion(autorizada=True, promo=False, cantidad=2) -> tuple[Inscripcion, Curso]:
    curso = Curso("P1", "Python 01", Dinero.mxn("800"), 5)
    i = Inscripcion("I1", "E1", date(2026, 10, 1), promo, autorizada)
    i.agregar_linea(curso, cantidad)
    return i, curso


ACTIVO = Estudiante("E1", "Est", preferente=True, activo=True)
INACTIVO = Estudiante("E1", "Est", activo=False)


def test_puede_procesarse_y_fallas():
    i, _ = inscripcion(autorizada=False)
    assert PUEDE_PROCESARSE.incumplidas(ContextoInscripcion(i, INACTIVO)) == ["estudiante activo", "autorización"]
    assert PUEDE_PROCESARSE.incumplidas(ContextoInscripcion(i, None)) == ["estudiante activo", "autorización"]


def test_beneficio_umbral_inclusivo_y_promocion():
    i, _ = inscripcion()  # 1600
    assert i.evaluar_beneficio(ACTIVO).aplica
    i2, _ = inscripcion(cantidad=1)  # 800
    assert i2.evaluar_beneficio(ACTIVO).incumplidas == ("total >= 1500",)
    con_promo, _ = inscripcion(promo=True)
    assert con_promo.evaluar_beneficio(ACTIVO).incumplidas == ("NOT promoción activa",)
    exacto = Inscripcion("I", "E1", date(2026, 1, 1))
    exacto.agregar_linea(Curso("P", "x", Dinero.mxn("750"), 9), 2)
    assert exacto.total.monto == Decimal("1500.00") and exacto.evaluar_beneficio(ACTIVO).aplica
    assert "estudiante preferente" in BENEFICIO_REFERENCIA.describir()


def test_flujo_completo_con_eventos():
    i, curso = inscripcion()
    i.validar(ACTIVO)
    i.inscribir({"P1": curso})
    i.finalizar()
    assert i.estado is EstadoInscripcion.FINALIZADA
    assert curso.cupo == 3
    assert [e.nombre for e in i.eventos] == ["InscripcionValidada", "InscripcionConfirmada", "InscripcionFinalizada"]


def test_validar_dos_veces_no_duplica_evento():
    i, _ = inscripcion()
    i.validar(ACTIVO)
    with pytest.raises(TransicionInvalida):
        i.validar(ACTIVO)
    assert len(i.eventos) == 1


def test_validar_sin_precondiciones_no_cambia_estado():
    i, _ = inscripcion(autorizada=False)
    with pytest.raises(DatosInvalidos, match="autorización"):
        i.validar(ACTIVO)
    assert i.estado is EstadoInscripcion.PREINSCRITA and i.eventos == ()


def test_saltar_estado_es_invalido():
    i, curso = inscripcion()
    with pytest.raises(TransicionInvalida):
        i.inscribir({"P1": curso})
    with pytest.raises(TransicionInvalida):
        i.finalizar()


def test_inscribir_sin_cupo_o_curso_deshabilitado():
    i, curso = inscripcion(cantidad=6)
    i.validar(ACTIVO)
    with pytest.raises(RecursoNoDisponible, match="cupo"):
        i.inscribir({"P1": curso})
    curso.habilitado = False
    with pytest.raises(RecursoNoDisponible, match="habilitados"):
        i.inscribir({"P1": curso})
    assert i.estado is EstadoInscripcion.VALIDADA and curso.cupo == 5
    with pytest.raises(RecursoNoDisponible):
        curso.reservar_cupo(1)


def test_cancelar():
    i, _ = inscripcion()
    with pytest.raises(DatosInvalidos):
        i.cancelar("")
    i.cancelar("Baja")
    assert i.estado is EstadoInscripcion.CANCELADA and i.motivo_cancelacion == "Baja"
    with pytest.raises(TransicionInvalida):
        i.cancelar("otra vez")


def test_solo_preinscrita_admite_cursos():
    i, curso = inscripcion()
    i.validar(ACTIVO)
    with pytest.raises(TransicionInvalida):
        i.agregar_linea(curso, 1)
