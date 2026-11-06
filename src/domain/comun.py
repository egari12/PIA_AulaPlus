"""Elementos compartidos del dominio: excepciones, Value Objects, eventos y roles.

Esta capa no conoce FastAPI, SQLAlchemy ni los CSV.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any

CENTAVOS = Decimal("0.01")

# Monterrey usa UTC-6 todo el año (México eliminó el horario de verano en 2022).
# Se usa un desfase fijo para no depender de la base de datos de zonas horarias.
ZONA_NEGOCIO = timezone(timedelta(hours=-6), "America/Monterrey")


# --------------------------------------------------------------------------- #
# Excepciones de negocio (la API las traduce a códigos HTTP)
# --------------------------------------------------------------------------- #
class ErrorDominio(Exception):
    """Base de todas las reglas de negocio violadas."""


class DatosInvalidos(ErrorDominio):
    """Datos de entrada que no cumplen una invariante (HTTP 422)."""


class ReglaNegocioViolada(ErrorDominio):
    """Una regla del BRD impide la operación, p. ej. la anticipación de 48 h (HTTP 422)."""


class TransicionInvalida(ErrorDominio):
    """La máquina de estados no permite la acción desde el estado actual (HTTP 409)."""


class RecursoNoDisponible(ErrorDominio):
    """No hay tutor o cupo disponible (HTTP 409)."""


class PermisoDenegado(ErrorDominio):
    """El rol no puede ejecutar la operación (HTTP 403)."""


class PagoRechazado(ErrorDominio):
    """El procesador de pagos rechazó el cobro (HTTP 402)."""


class NoEncontrado(ErrorDominio):
    """El recurso solicitado no existe (HTTP 404)."""


# --------------------------------------------------------------------------- #
# Roles (RN-11, US-13, US-16)
# --------------------------------------------------------------------------- #
class Rol(str, Enum):
    ESTUDIANTE = "ESTUDIANTE"
    TUTOR = "TUTOR"
    SOPORTE = "SOPORTE"
    ADMINISTRADOR = "ADMINISTRADOR"
    SISTEMA = "SISTEMA"


MENSAJE_SOLO_SOPORTE = "Solo Soporte puede ejecutar operaciones sobre sesiones"


def exigir_rol(rol: Rol, *permitidos: Rol, mensaje: str | None = None) -> None:
    if rol not in permitidos:
        nombres = ", ".join(p.value for p in permitidos)
        raise PermisoDenegado(mensaje or f"Operación permitida solo para: {nombres}")


# --------------------------------------------------------------------------- #
# Tiempo
# --------------------------------------------------------------------------- #
def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def a_utc(momento: datetime, campo: str = "fecha") -> datetime:
    """Exige fecha con zona horaria y la normaliza a UTC."""
    if not isinstance(momento, datetime):
        raise DatosInvalidos(f"{campo} debe ser una fecha y hora")
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise DatosInvalidos(f"{campo} debe incluir zona horaria (ISO 8601 con desfase)")
    return momento.astimezone(timezone.utc)


# --------------------------------------------------------------------------- #
# Value Object: Dinero
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Dinero:
    """Importe en MXN con Decimal: nunca float, nunca negativo."""

    monto: Decimal
    moneda: str = "MXN"

    def __post_init__(self) -> None:
        if isinstance(self.monto, bool) or not isinstance(self.monto, Decimal):
            raise DatosInvalidos("El monto debe ser Decimal (no float)")
        if not self.monto.is_finite() or self.monto < 0:
            raise DatosInvalidos("El monto debe ser finito y no negativo")
        if self.moneda != "MXN":
            raise DatosInvalidos("Solo se admite la moneda MXN")
        object.__setattr__(self, "monto", self.monto.quantize(CENTAVOS, ROUND_HALF_UP))

    @classmethod
    def mxn(cls, valor: str | int | Decimal) -> Dinero:
        if isinstance(valor, float):
            raise DatosInvalidos("El monto debe construirse desde texto, entero o Decimal")
        return cls(Decimal(str(valor)))

    @classmethod
    def cero(cls) -> Dinero:
        return cls(Decimal("0"))

    def _misma_moneda(self, otro: Dinero) -> None:
        if not isinstance(otro, Dinero) or otro.moneda != self.moneda:
            raise DatosInvalidos("No se pueden operar monedas distintas")

    def __add__(self, otro: Dinero) -> Dinero:
        self._misma_moneda(otro)
        return Dinero(self.monto + otro.monto, self.moneda)

    def __sub__(self, otro: Dinero) -> Dinero:
        self._misma_moneda(otro)
        return Dinero(self.monto - otro.monto, self.moneda)

    def __mul__(self, cantidad: int) -> Dinero:
        if isinstance(cantidad, bool) or not isinstance(cantidad, int):
            raise DatosInvalidos("Solo se puede multiplicar por una cantidad entera")
        return Dinero(self.monto * cantidad, self.moneda)

    def porcentaje(self, porcentaje: Decimal) -> Dinero:
        return Dinero(self.monto * porcentaje / Decimal(100), self.moneda)

    def __str__(self) -> str:
        return f"{self.monto} {self.moneda}"


# --------------------------------------------------------------------------- #
# Domain Events
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EventoDominio:
    """Hecho que ya ocurrió; por eso el nombre va en pasado."""

    nombre: str
    agregado_id: str
    ocurrido_en: datetime
    datos: dict[str, Any] = field(default_factory=dict)


class AgregadoRaiz:
    """Acumula eventos; solo se registran después de una transición válida."""

    id: str

    def _registrar(self, nombre: str, ocurrido_en: datetime | None = None, **datos: Any) -> None:
        evento = EventoDominio(nombre, self.id, ocurrido_en or ahora_utc(), datos)
        self.__dict__.setdefault("_eventos", []).append(evento)

    @property
    def eventos(self) -> tuple[EventoDominio, ...]:
        return tuple(self.__dict__.get("_eventos", []))

    def extraer_eventos(self) -> list[EventoDominio]:
        eventos = list(self.eventos)
        self.__dict__["_eventos"] = []
        return eventos
