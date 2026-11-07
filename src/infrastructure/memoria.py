"""Repositorios en memoria: para pruebas unitarias y para el ejecutor de casos CSV.

Guardan copias profundas, igual que una base de datos: modificar un objeto
cargado no cambia nada hasta llamar a guardar().
"""

from __future__ import annotations

import copy
from typing import Generic, TypeVar

from src.domain.comun import EventoDominio
from src.domain.sesiones.modelo import PoliticaTarifas

T = TypeVar("T")


class _RepositorioMemoria(Generic[T]):
    def __init__(self) -> None:
        self._datos: dict[str, T] = {}
        self._eventos: dict[str, list[EventoDominio]] = {}

    def obtener(self, identificador: str) -> T | None:
        valor = self._datos.get(identificador)
        return copy.deepcopy(valor) if valor is not None else None

    def listar(self) -> list[T]:
        return [copy.deepcopy(v) for _, v in sorted(self._datos.items())]

    def guardar(self, agregado: T) -> None:
        extraer = getattr(agregado, "extraer_eventos", None)
        if extraer is not None:
            self._eventos.setdefault(agregado.id, []).extend(extraer())  # type: ignore[attr-defined]
        self._datos[agregado.id] = copy.deepcopy(agregado)  # type: ignore[attr-defined]

    def eventos_de(self, agregado_id: str) -> list[EventoDominio]:
        return list(self._eventos.get(agregado_id, []))


class RepositorioPoliticasMemoria:
    def __init__(self, politica: PoliticaTarifas | None = None):
        self._politica = politica or PoliticaTarifas()

    def obtener(self) -> PoliticaTarifas:
        return self._politica

    def guardar(self, politica: PoliticaTarifas) -> None:
        self._politica = politica


class UnidadDeTrabajoMemoria:
    def __init__(self) -> None:
        self.tutores = _RepositorioMemoria()
        self.sesiones = _RepositorioMemoria()
        self.estudiantes = _RepositorioMemoria()
        self.cuentas = _RepositorioMemoria()
        self.cursos = _RepositorioMemoria()
        self.inscripciones = _RepositorioMemoria()
        self.politicas = RepositorioPoliticasMemoria()
        self.confirmaciones = 0

    def commit(self) -> None:
        self.confirmaciones += 1

    def rollback(self) -> None:
        """Los cambios no guardados se descartan solos porque se trabaja con copias."""
