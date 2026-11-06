"""Fixtures compartidas. AHORA es un lunes; la sesión de referencia es el jueves siguiente."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.application.servicios_inscripciones import ServicioInscripciones
from src.application.servicios_sesiones import ServicioSesiones
from src.domain.comun import ZONA_NEGOCIO
from src.domain.sesiones.modelo import Modalidad, SolicitudReserva
from src.infrastructure.cargador_csv import DIRECTORIO_DATOS, cargar_paquete, cargar_tutores, poblar
from src.infrastructure.externos import PasarelaSimulada, RelojFijo
from src.infrastructure.memoria import UnidadDeTrabajoMemoria

AHORA = datetime(2026, 11, 9, 9, 0, tzinfo=ZONA_NEGOCIO)  # lunes 9:00 Monterrey
JUEVES_10 = datetime(2026, 11, 12, 10, 0, tzinfo=ZONA_NEGOCIO)  # 73 h después


def solicitud(inicio: datetime = JUEVES_10, materia: str = "Python", modalidad=Modalidad.EN_LINEA,
              zona: str | None = None, estudiante: str = "AUL-C001") -> SolicitudReserva:
    return SolicitudReserva(estudiante, materia, "Listas y diccionarios", modalidad, inicio, zona)


@pytest.fixture
def reloj() -> RelojFijo:
    return RelojFijo(AHORA)


@pytest.fixture
def pasarela() -> PasarelaSimulada:
    return PasarelaSimulada(rechazar={"AUL-C040"})


@pytest.fixture
def uow() -> UnidadDeTrabajoMemoria:
    unidad = UnidadDeTrabajoMemoria()
    poblar(unidad, cargar_paquete())
    return unidad


@pytest.fixture
def tutores():
    return cargar_tutores(DIRECTORIO_DATOS / "tutores.csv")


@pytest.fixture
def servicio(uow, pasarela, reloj) -> ServicioSesiones:
    contador = iter(range(1, 10_000))
    return ServicioSesiones(uow, pasarela, reloj, generar_id=lambda: f"SES-{next(contador):03d}")


@pytest.fixture
def servicio_insc(uow, reloj) -> ServicioInscripciones:
    contador = iter(range(1, 10_000))
    return ServicioInscripciones(uow, reloj, generar_id=lambda: f"INS-{next(contador):03d}")


@pytest.fixture
def horas():
    return lambda n: timedelta(hours=n)
