"""Registro de estudiantes y tutores (US-19, US-20): una cuenta asocia un correo con un usuario.

No es autenticación: no hay contraseña ni token. Los permisos siguen saliendo del
encabezado X-Rol (ADR-005); esto solo permite que un estudiante nuevo exista en el
sistema y vuelva a entrar con su correo.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from src.domain.comun import DatosInvalidos

PREFIJO_ESTUDIANTE_NUEVO = "AUL-E"  # los del paquete del docente usan AUL-C
PREFIJO_TUTOR = "AUL-T"  # continúa después de los tutores iniciales (AUL-T01 ... AUL-T05)
_PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalizar_correo(correo: str) -> str:
    valor = (correo or "").strip().lower()
    if len(valor) > 254 or not _PATRON_CORREO.match(valor):
        raise DatosInvalidos("El correo no tiene un formato válido")
    return valor


def normalizar_nombre(nombre: str) -> str:
    valor = " ".join((nombre or "").split())
    if not 2 <= len(valor) <= 120:
        raise DatosInvalidos("El nombre debe tener entre 2 y 120 caracteres")
    return valor


def normalizar_ciudad(ciudad: str) -> str:
    valor = " ".join((ciudad or "").split())
    if not 2 <= len(valor) <= 80:
        raise DatosInvalidos("La ciudad debe tener entre 2 y 80 caracteres")
    return valor


class TipoCuenta(str, Enum):
    ESTUDIANTE = "ESTUDIANTE"
    TUTOR = "TUTOR"


@dataclass(frozen=True)
class Cuenta:
    """Value Object: correo (único entre estudiantes y tutores, en minúsculas) → usuario."""

    correo: str
    usuario_id: str
    tipo: TipoCuenta

    def __post_init__(self) -> None:
        object.__setattr__(self, "correo", normalizar_correo(self.correo))
        object.__setattr__(self, "tipo", TipoCuenta(self.tipo))
        if not (self.usuario_id or "").strip():
            raise DatosInvalidos("La cuenta debe pertenecer a un usuario")

    @property
    def id(self) -> str:
        """El correo identifica la cuenta (lo usan los repositorios)."""
        return self.correo


def siguiente_id_estudiante(ids_existentes: Iterable[str]) -> str:
    """AUL-E001, AUL-E002, ...; ignora los ids del paquete del docente."""
    numeros = [
        int(i[len(PREFIJO_ESTUDIANTE_NUEVO) :])
        for i in ids_existentes
        if i.startswith(PREFIJO_ESTUDIANTE_NUEVO) and i[len(PREFIJO_ESTUDIANTE_NUEVO) :].isdigit()
    ]
    return f"{PREFIJO_ESTUDIANTE_NUEVO}{max(numeros, default=0) + 1:03d}"


def siguiente_id_tutor(ids_existentes: Iterable[str]) -> str:
    """AUL-T06, AUL-T07, ... después del último tutor existente."""
    numeros = [
        int(i[len(PREFIJO_TUTOR) :])
        for i in ids_existentes
        if i.startswith(PREFIJO_TUTOR) and i[len(PREFIJO_TUTOR) :].isdigit()
    ]
    return f"{PREFIJO_TUTOR}{max(numeros, default=0) + 1:02d}"
