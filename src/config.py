"""Configuración por variables de entorno (12-Factor). Nada de credenciales en el código."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(valor: str | None, defecto: bool) -> bool:
    if valor is None:
        return defecto
    return valor.strip().lower() in {"1", "true", "si", "sí", "yes"}


@dataclass(frozen=True)
class Configuracion:
    database_url: str = "sqlite+pysqlite:///./aulaplus.db"
    sembrar_datos: bool = True
    pasarela_rechazar: frozenset[str] = field(default_factory=frozenset)
    entorno: str = "desarrollo"

    @classmethod
    def desde_entorno(cls) -> Configuracion:
        url = os.getenv("DATABASE_URL", cls.database_url)
        # Render/Heroku entregan 'postgres://'; SQLAlchemy 2 requiere el driver explícito.
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        rechazar = os.getenv("PASARELA_RECHAZAR", "")
        return cls(
            database_url=url,
            sembrar_datos=_bool(os.getenv("SEED_DATOS"), True),
            pasarela_rechazar=frozenset(x.strip() for x in rechazar.split(",") if x.strip()),
            entorno=os.getenv("APP_ENV", "desarrollo"),
        )
