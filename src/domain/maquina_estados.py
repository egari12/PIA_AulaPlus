"""Máquina de estados explícita: una tabla (estado, acción) -> estado destino.

Cualquier par que no esté en la tabla es inválido y lanza TransicionInvalida
antes de modificar el agregado.
"""

from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from src.domain.comun import TransicionInvalida

E = TypeVar("E", bound=Enum)


class MaquinaEstados(Generic[E]):
    def __init__(self, nombre: str, transiciones: dict[tuple[E, str], E]):
        self.nombre = nombre
        self.transiciones = dict(transiciones)

    def destino(self, estado: E, accion: str) -> E:
        try:
            return self.transiciones[(estado, accion)]
        except KeyError:
            raise TransicionInvalida(
                f"{self.nombre}: no se permite '{accion}' desde el estado {estado.value}"
            ) from None

    def acciones_desde(self, estado: E) -> list[str]:
        return sorted(accion for (origen, accion) in self.transiciones if origen == estado)

    def es_final(self, estado: E) -> bool:
        return not self.acciones_desde(estado)
