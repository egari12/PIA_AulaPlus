"""Punto de entrada de la API.

Ejecutar:  uvicorn src.api.main:create_app --factory --reload
Swagger:   http://localhost:8000/docs     OpenAPI: /openapi.json
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from src.api import rutas_admin, rutas_inscripciones, rutas_sesiones
from src.api.errores import registrar_manejadores
from src.application.puertos import PasarelaPago, Reloj
from src.config import Configuracion
from src.infrastructure.cargador_csv import cargar_paquete, poblar
from src.infrastructure.db import crear_engine, crear_fabrica_sesiones
from src.infrastructure.externos import PasarelaSimulada, RelojSistema
from src.infrastructure.repositorios_sql import UnidadDeTrabajoSQL

INTERFAZ = Path(__file__).resolve().parent / "static" / "index.html"

DESCRIPCION = """
API de **AulaPlus**: asesorías uno a uno entre estudiantes y tutores.

* **Sesiones** (BRD): reserva con 48 h de anticipación, asignación automática de tutor,
  cobro de $200, grabación con umbral de 70 %, liquidación 80/20, cancelaciones por Soporte,
  calificación en 24 h.
* **Inscripciones**: contexto agregado para ejecutar el paquete de pruebas CSV del docente.

Envíe el encabezado **X-Rol** (ESTUDIANTE, TUTOR, SOPORTE, ADMINISTRADOR o SISTEMA)
en las operaciones que cambian datos de sesiones, tutores o políticas.
"""


def create_app(
    config: Configuracion | None = None,
    reloj: Reloj | None = None,
    pasarela: PasarelaPago | None = None,
) -> FastAPI:
    config = config or Configuracion.desde_entorno()
    app = FastAPI(title="AulaPlus API", version="1.0.0", description=DESCRIPCION)

    engine = crear_engine(config.database_url)
    app.state.config = config
    app.state.engine = engine
    app.state.fabrica_sesiones = crear_fabrica_sesiones(engine)
    app.state.reloj = reloj or RelojSistema()
    app.state.pasarela = pasarela or PasarelaSimulada(rechazar=set(config.pasarela_rechazar))

    if config.sembrar_datos:
        uow = UnidadDeTrabajoSQL(app.state.fabrica_sesiones)
        try:
            if uow.esta_vacia():
                poblar(uow, cargar_paquete())
        finally:
            uow.cerrar()

    registrar_manejadores(app)
    app.include_router(rutas_sesiones.router)
    app.include_router(rutas_sesiones.router_tutores)
    app.include_router(rutas_admin.router)
    app.include_router(rutas_inscripciones.router)

    @app.get("/", include_in_schema=False)
    def interfaz() -> FileResponse:
        """Interfaz web de demostración; consume la misma API que Swagger (/docs)."""
        return FileResponse(INTERFAZ, media_type="text/html")

    @app.get("/salud", tags=["Salud"], summary="Verificación de vida")
    def salud() -> dict:
        return {"estado": "ok", "entorno": config.entorno}

    return app
