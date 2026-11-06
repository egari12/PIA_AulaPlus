"""Puertos (interfaces) que la capa de aplicación necesita; infraestructura los implementa.

Principio de inversión de dependencias (SOLID-D): los servicios dependen de estos
protocolos, no de SQLAlchemy ni de una pasarela concreta.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from src.domain.comun import Dinero, EventoDominio
from src.domain.inscripciones.modelo import Curso, Estudiante, Inscripcion
from src.domain.sesiones.modelo import PoliticaTarifas, Sesion, Tutor


class Reloj(Protocol):
    def ahora(self) -> datetime: ...


class PasarelaPago(Protocol):
    def cobrar(self, estudiante_id: str, monto: Dinero, concepto: str) -> str: ...
    def transferir(self, tutor_id: str, monto: Dinero, concepto: str) -> str: ...
    def reembolsar(self, referencia: str, monto: Dinero) -> str: ...


class RepositorioTutores(Protocol):
    def obtener(self, tutor_id: str) -> Tutor | None: ...
    def listar(self) -> list[Tutor]: ...
    def guardar(self, tutor: Tutor) -> None: ...


class RepositorioSesiones(Protocol):
    def obtener(self, sesion_id: str) -> Sesion | None: ...
    def listar(self) -> list[Sesion]: ...
    def guardar(self, sesion: Sesion) -> None: ...
    def eventos_de(self, agregado_id: str) -> list[EventoDominio]: ...


class RepositorioPoliticas(Protocol):
    def obtener(self) -> PoliticaTarifas: ...
    def guardar(self, politica: PoliticaTarifas) -> None: ...


class RepositorioEstudiantes(Protocol):
    def obtener(self, estudiante_id: str) -> Estudiante | None: ...
    def listar(self) -> list[Estudiante]: ...
    def guardar(self, estudiante: Estudiante) -> None: ...


class RepositorioCursos(Protocol):
    def obtener(self, curso_id: str) -> Curso | None: ...
    def listar(self) -> list[Curso]: ...
    def guardar(self, curso: Curso) -> None: ...


class RepositorioInscripciones(Protocol):
    def obtener(self, inscripcion_id: str) -> Inscripcion | None: ...
    def listar(self) -> list[Inscripcion]: ...
    def guardar(self, inscripcion: Inscripcion) -> None: ...
    def eventos_de(self, agregado_id: str) -> list[EventoDominio]: ...


class UnidadDeTrabajo(Protocol):
    """Define el límite de la transacción: todo se confirma junto o nada."""

    tutores: RepositorioTutores
    sesiones: RepositorioSesiones
    politicas: RepositorioPoliticas
    estudiantes: RepositorioEstudiantes
    cursos: RepositorioCursos
    inscripciones: RepositorioInscripciones

    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def inicios_activos_por_tutor(sesiones: Iterable[Sesion]) -> dict[str, list[datetime]]:
    """Sesiones que ocupan agenda (todas menos las canceladas)."""
    from src.domain.sesiones.modelo import EstadoSesion

    ocupados: dict[str, list[datetime]] = {}
    for sesion in sesiones:
        if sesion.estado is not EstadoSesion.CANCELADA:
            ocupados.setdefault(sesion.tutor_id, []).append(sesion.inicio)
    return ocupados
