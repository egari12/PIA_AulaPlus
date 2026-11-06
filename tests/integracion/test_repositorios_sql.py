"""Integración con base de datos real (SQLite en memoria por defecto, PostgreSQL si TEST_DATABASE_URL existe)."""

import os
from datetime import timedelta
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

from src.application.servicios_inscripciones import ServicioInscripciones  # noqa: E402
from src.application.servicios_sesiones import ServicioSesiones  # noqa: E402
from src.domain.comun import Dinero, Rol  # noqa: E402
from src.domain.inscripciones.modelo import EstadoInscripcion  # noqa: E402
from src.domain.sesiones.modelo import EstadoSesion, PoliticaTarifas, Solicitante, TipoCambio  # noqa: E402
from src.infrastructure.cargador_csv import cargar_paquete, poblar  # noqa: E402
from src.infrastructure.db import Base, crear_engine, crear_fabrica_sesiones  # noqa: E402
from src.infrastructure.externos import PasarelaSimulada, RelojFijo  # noqa: E402
from src.infrastructure.repositorios_sql import UnidadDeTrabajoSQL  # noqa: E402
from tests.conftest import AHORA, JUEVES_10, solicitud  # noqa: E402


@pytest.fixture
def fabrica():
    url = os.getenv("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    engine = crear_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    fabrica = crear_fabrica_sesiones(engine)
    uow = UnidadDeTrabajoSQL(fabrica)
    poblar(uow, cargar_paquete())
    uow.cerrar()
    yield fabrica
    engine.dispose()


def nueva_uow(fabrica):
    return UnidadDeTrabajoSQL(fabrica)


def test_paquete_persistido(fabrica):
    uow = nueva_uow(fabrica)
    assert len(uow.estudiantes.listar()) == 40
    assert len(uow.cursos.listar()) == 20
    o001 = uow.inscripciones.obtener("AUL-O001")
    assert o001.total == Dinero.mxn("8231.00") and len(o001.lineas) == 2
    assert uow.tutores.obtener("AUL-T01").imparte("python")
    assert not uow.esta_vacia()
    uow.cerrar()


def test_flujo_de_sesion_en_bd(fabrica):
    reloj, pasarela = RelojFijo(AHORA), PasarelaSimulada()
    uow = nueva_uow(fabrica)
    servicio = ServicioSesiones(uow, pasarela, reloj, generar_id=lambda: "SES-SQL-1")
    servicio.reservar(Rol.ESTUDIANTE, solicitud())
    servicio.solicitar_cambio(Rol.ESTUDIANTE, "SES-SQL-1", TipoCambio.MODALIDAD, "EN_LINEA")
    uow.cerrar()

    uow = nueva_uow(fabrica)  # nueva sesión de BD: se lee lo confirmado
    sesion = uow.sesiones.obtener("SES-SQL-1")
    assert sesion.inicio == JUEVES_10 and sesion.cambio_pendiente.valor == "EN_LINEA"
    servicio = ServicioSesiones(uow, pasarela, reloj)
    servicio.registrar_grabacion(Rol.SISTEMA, "SES-SQL-1", "u", JUEVES_10, JUEVES_10 + timedelta(minutes=80))
    servicio.liquidar(Rol.SISTEMA, "SES-SQL-1")
    uow.cerrar()

    uow = nueva_uow(fabrica)
    sesion = uow.sesiones.obtener("SES-SQL-1")
    assert sesion.estado is EstadoSesion.LIQUIDADA
    assert sesion.liquidacion.monto_tutor == Dinero.mxn("160")
    assert sesion.grabacion.duracion == timedelta(minutes=80)
    nombres = [e.nombre for e in uow.sesiones.eventos_de("SES-SQL-1")]
    assert nombres == ["SesionReservada", "CambioSolicitado", "SesionCompletada", "SesionLiquidada"]
    uow.cerrar()


def test_cancelacion_actualiza_tutor_en_bd(fabrica):
    reloj = RelojFijo(AHORA)
    uow = nueva_uow(fabrica)
    servicio = ServicioSesiones(uow, PasarelaSimulada(), reloj, generar_id=lambda: "SES-SQL-2")
    servicio.reservar(Rol.ESTUDIANTE, solicitud())
    reloj.avanzar(timedelta(hours=70))
    servicio.cancelar(Rol.SOPORTE, "SES-SQL-2", Solicitante.TUTOR, "Sin aviso")
    uow.cerrar()
    uow = nueva_uow(fabrica)
    assert uow.tutores.obtener("AUL-T01").penalizaciones == 1
    assert uow.sesiones.obtener("SES-SQL-2").monto_reembolso == Dinero.mxn("200")
    uow.cerrar()


def test_rollback_descarta_cambios(fabrica):
    uow = nueva_uow(fabrica)
    curso = uow.cursos.obtener("AUL-P001")
    curso.cupo = 0
    uow.cursos.guardar(curso)
    uow.rollback()
    assert uow.cursos.obtener("AUL-P001").cupo == 13
    uow.cerrar()


def test_inscripcion_y_politica_en_bd(fabrica):
    uow = nueva_uow(fabrica)
    servicio = ServicioInscripciones(uow, RelojFijo(AHORA))
    servicio.validar("AUL-O001")
    servicio.inscribir("AUL-O001")
    uow.politicas.guardar(PoliticaTarifas().con_comision(Decimal("30")))
    uow.commit()
    uow.cerrar()
    uow = nueva_uow(fabrica)
    assert uow.inscripciones.obtener("AUL-O001").estado is EstadoInscripcion.INSCRITA
    assert uow.cursos.obtener("AUL-P009").cupo == 37 - 3
    assert uow.politicas.obtener().porcentaje_comision == Decimal("30")
    assert len(uow.inscripciones.eventos_de("AUL-O001")) == 2
    uow.cerrar()
