"""Punto de entrada de la API.

Ejecutar:  uvicorn src.api.main:create_app --factory --reload
Swagger:   http://localhost:8000/docs     OpenAPI: /openapi.json
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from src.api import rutas_admin, rutas_estudiantes, rutas_inscripciones, rutas_sesiones
from src.api.errores import registrar_manejadores
from src.application.puertos import PasarelaPago, Reloj
from src.config import Configuracion
from src.infrastructure.cargador_csv import cargar_paquete, poblar
from src.infrastructure.db import crear_engine, crear_fabrica_sesiones
from src.infrastructure.externos import PasarelaSimulada, RelojSistema
from src.infrastructure.repositorios_sql import UnidadDeTrabajoSQL

INTERFAZ = Path(__file__).resolve().parent / "static" / "index.html"

DESCRIPCION = """
API de AulaPlus (Equipo 8, FIME-UANL): asesorías uno a uno entre estudiantes y tutores.

### Cómo probarla
1. Consulta los tutores en `GET /tutores`.
2. Reserva una sesión en `POST /sesiones` con **X-Rol** = `ESTUDIANTE` y al menos 48 h de anticipación.
3. Consulta tu sesión en `GET /sesiones/{sesion_id}`.

### Qué significa cada respuesta
| Código | Significado |
|---|---|
| 200 | Todo salió bien |
| 201 | Se creó correctamente |
| 402 | El pago fue rechazado |
| 403 | Tu rol (X-Rol) no tiene permiso para esta acción |
| 404 | Lo que buscas no existe |
| 409 | La acción no se puede hacer en este momento |
| 422 | Faltan datos o no se cumple una regla del negocio |

Los errores explican qué pasó en el campo `detalle`.
"""

ETIQUETAS = [
    {
        "name": "Sesiones",
        "description": "Reservar, registrar la clase, pagar al tutor, cancelar, calificar y cambiar sesiones.",
    },
    {"name": "Tutores", "description": "Consultar tutores y actualizar su disponibilidad."},
    {"name": "Estudiantes", "description": "Crear una cuenta de estudiante y volver a entrar con el correo."},
    {"name": "Administración", "description": "Tarifas de la plataforma y reportes (solo ADMINISTRADOR)."},
    {
        "name": "Inscripciones (paquete CSV)",
        "description": "Operaciones del paquete de pruebas del docente (catálogo, operaciones y transiciones).",
    },
    {"name": "Salud", "description": "Verifica que el servicio está en línea."},
]


def create_app(
    config: Configuracion | None = None,
    reloj: Reloj | None = None,
    pasarela: PasarelaPago | None = None,
) -> FastAPI:
    config = config or Configuracion.desde_entorno()
    app = FastAPI(title="AulaPlus API", version="1.0.0", description=DESCRIPCION, openapi_tags=ETIQUETAS)

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
    app.include_router(rutas_estudiantes.router)
    app.include_router(rutas_inscripciones.router)

    @app.get("/", include_in_schema=False)
    def interfaz() -> FileResponse:
        """Interfaz web de demostración; consume la misma API que Swagger (/docs)."""
        return FileResponse(INTERFAZ, media_type="text/html")

    @app.get("/salud", tags=["Salud"], summary="Verificación de vida")
    def salud() -> dict:
        return {"estado": "ok", "entorno": config.entorno}

    return app
