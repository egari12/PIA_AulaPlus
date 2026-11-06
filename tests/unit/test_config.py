"""Configuración 12-Factor desde variables de entorno."""

from src.config import Configuracion


def test_valores_por_defecto(monkeypatch):
    for var in ("DATABASE_URL", "SEED_DATOS", "PASARELA_RECHAZAR", "APP_ENV"):
        monkeypatch.delenv(var, raising=False)
    config = Configuracion.desde_entorno()
    assert config.database_url.startswith("sqlite")
    assert config.sembrar_datos and config.pasarela_rechazar == frozenset()


def test_lee_entorno_y_normaliza_postgres(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host:5432/db")
    monkeypatch.setenv("SEED_DATOS", "false")
    monkeypatch.setenv("PASARELA_RECHAZAR", "AUL-C001, AUL-C002")
    monkeypatch.setenv("APP_ENV", "produccion")
    config = Configuracion.desde_entorno()
    assert config.database_url == "postgresql+psycopg://u:p@host:5432/db"
    assert not config.sembrar_datos
    assert config.pasarela_rechazar == {"AUL-C001", "AUL-C002"}
    assert config.entorno == "produccion"


def test_postgresql_sin_driver(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    assert Configuracion.desde_entorno().database_url == "postgresql+psycopg://u:p@h/db"
