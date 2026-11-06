"""Specification Pattern: reglas con nombre de negocio combinables con & (AND), | (OR) y ~ (NOT)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Especificacion(ABC, Generic[T]):
    descripcion: str = ""

    @abstractmethod
    def es_satisfecha_por(self, candidato: T) -> bool:
        """Responde verdadero o falso sin modificar al candidato."""

    def describir(self) -> str:
        return self.descripcion or type(self).__name__

    def incumplidas(self, candidato: T) -> list[str]:
        """Nombres de las reglas que fallaron; sirve para mensajes y bitácoras."""
        return [] if self.es_satisfecha_por(candidato) else [self.describir()]

    def __and__(self, otra: Especificacion[T]) -> Especificacion[T]:
        return Y(self, otra)

    def __or__(self, otra: Especificacion[T]) -> Especificacion[T]:
        return O(self, otra)

    def __invert__(self) -> Especificacion[T]:
        return No(self)


class Y(Especificacion[T]):
    def __init__(self, izquierda: Especificacion[T], derecha: Especificacion[T]):
        self.izquierda, self.derecha = izquierda, derecha

    def es_satisfecha_por(self, candidato: T) -> bool:
        return self.izquierda.es_satisfecha_por(candidato) and self.derecha.es_satisfecha_por(
            candidato
        )

    def incumplidas(self, candidato: T) -> list[str]:
        return [*self.izquierda.incumplidas(candidato), *self.derecha.incumplidas(candidato)]

    def describir(self) -> str:
        return f"{self.izquierda.describir()} AND {self.derecha.describir()}"


class O(Especificacion[T]):
    def __init__(self, izquierda: Especificacion[T], derecha: Especificacion[T]):
        self.izquierda, self.derecha = izquierda, derecha

    def es_satisfecha_por(self, candidato: T) -> bool:
        return self.izquierda.es_satisfecha_por(candidato) or self.derecha.es_satisfecha_por(
            candidato
        )

    def describir(self) -> str:
        return f"({self.izquierda.describir()} OR {self.derecha.describir()})"


class No(Especificacion[T]):
    def __init__(self, interna: Especificacion[T]):
        self.interna = interna

    def es_satisfecha_por(self, candidato: T) -> bool:
        return not self.interna.es_satisfecha_por(candidato)

    def describir(self) -> str:
        return f"NOT {self.interna.describir()}"
