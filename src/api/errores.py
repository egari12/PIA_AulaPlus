"""Traducción de errores a respuestas HTTP claras (contrato del equipo).

Todas las respuestas de error tienen la misma forma:
    {"error": "<tipo>", "titulo": "<qué significa, en una frase>", "detalle": "<qué pasó exactamente>"}
Así se leen igual en la interfaz y en Swagger, sin importar si el error viene del
dominio, de la validación de FastAPI/Pydantic o de una ruta que no existe.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.domain.comun import (
    DatosInvalidos,
    ErrorDominio,
    NoEncontrado,
    PagoRechazado,
    PermisoDenegado,
    RecursoNoDisponible,
    ReglaNegocioViolada,
    TransicionInvalida,
)

registro = logging.getLogger("aulaplus.api")

CODIGOS: dict[type[ErrorDominio], int] = {
    NoEncontrado: 404,
    PermisoDenegado: 403,
    PagoRechazado: 402,
    TransicionInvalida: 409,
    RecursoNoDisponible: 409,
    DatosInvalidos: 422,
    ReglaNegocioViolada: 422,
}

TITULOS: dict[str, str] = {
    "NoEncontrado": "Lo que buscas no existe",
    "PermisoDenegado": "Tu rol no tiene permiso para esta acción",
    "PagoRechazado": "El pago fue rechazado",
    "TransicionInvalida": "La acción no se puede hacer en el estado actual",
    "RecursoNoDisponible": "No hay disponibilidad para esta acción",
    "DatosInvalidos": "Faltan datos o tienen un formato incorrecto",
    "ReglaNegocioViolada": "No se cumple una regla del negocio",
    "RutaNoEncontrada": "Esa dirección no existe en la API",
    "MetodoNoPermitido": "Esa operación no existe en esta dirección",
    "ErrorInterno": "Algo falló en el servidor",
}


def _ejemplo(error: str, detalle: str) -> dict:
    return {"application/json": {"example": {"error": error, "titulo": TITULOS[error], "detalle": detalle}}}


# Lo que Swagger muestra en cada endpoint como posibles respuestas de error.
RESPUESTAS_ERROR = {
    402: {
        "description": "Pago rechazado",
        "content": _ejemplo("PagoRechazado", "El pago no pudo ser procesado. Intente nuevamente"),
    },
    403: {
        "description": "Rol sin permiso",
        "content": _ejemplo("PermisoDenegado", "Solo Soporte puede ejecutar operaciones sobre sesiones"),
    },
    404: {
        "description": "No encontrado",
        "content": _ejemplo("NoEncontrado", "La sesión SES-123 no existe"),
    },
    409: {
        "description": "Transición inválida o recurso no disponible",
        "content": _ejemplo(
            "TransicionInvalida",
            "Sesion: no se permite 'liquidar' desde el estado CONFIRMADA. "
            "Desde CONFIRMADA solo se puede: cancelar, completar, reembolsar.",
        ),
    },
    422: {
        "description": "Datos inválidos o regla de negocio violada",
        "content": _ejemplo("ReglaNegocioViolada", "La reserva debe realizarse con al menos 48 horas de anticipación"),
    },
}


def codigo_para(error: ErrorDominio) -> int:
    for tipo in type(error).__mro__:
        if tipo in CODIGOS:
            return CODIGOS[tipo]
    return 400


def respuesta_error(codigo: int, error: str, detalle: str) -> JSONResponse:
    titulo = TITULOS.get(error, "No se pudo completar la solicitud")
    return JSONResponse(status_code=codigo, content={"error": error, "titulo": titulo, "detalle": detalle})


# --------------------------------------------------------------------------- #
# Errores de validación de FastAPI/Pydantic, traducidos al español
# --------------------------------------------------------------------------- #
ROLES = "ESTUDIANTE, TUTOR, SOPORTE, ADMINISTRADOR o SISTEMA"
COMPARACIONES = {
    "greater_than_equal": ("≥", "ge"),
    "greater_than": (">", "gt"),
    "less_than_equal": ("≤", "le"),
    "less_than": ("<", "lt"),
}
TIPOS_ESPERADOS = {
    "list_type": "una lista",
    "string_type": "texto",
    "dict_type": "un objeto",
    "model_type": "un objeto",
}


def _campo(loc: tuple) -> str:
    partes = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(partes) or "cuerpo"


def explicar_validacion(e: dict) -> str:
    """Convierte un error de Pydantic en una frase corta."""
    loc, tipo, ctx = tuple(e.get("loc", ())), e.get("type", ""), e.get("ctx") or {}
    campo = _campo(loc)
    es_rol = bool(loc) and loc[0] == "header" and str(loc[-1]).lower() == "x-rol"
    if es_rol:
        if tipo == "missing":
            return f"Falta el encabezado X-Rol. Indica quién hace la operación: {ROLES}."
        return f"El encabezado X-Rol no es válido. Usa {ROLES}."
    if tipo == "missing":
        return f"Falta el campo «{campo}»."
    if tipo == "json_invalid":
        return "El cuerpo de la petición no es un JSON válido. Revisa comas, comillas y llaves."
    if tipo == "enum":
        opciones = str(ctx.get("expected", "")).replace("'", "").replace(" or ", " o ")
        return f"«{campo}» no es válido. Opciones: {opciones}."
    if tipo == "string_too_short":
        return f"«{campo}» es muy corto (mínimo {ctx.get('min_length')} caracteres)."
    if tipo == "string_too_long":
        return f"«{campo}» es muy largo (máximo {ctx.get('max_length')} caracteres)."
    if tipo.startswith("datetime") or tipo.startswith("date"):
        return f"«{campo}» debe ser una fecha y hora, por ejemplo 2026-11-16T10:00:00-06:00."
    if tipo.startswith("time"):
        return f"«{campo}» debe ser una hora, por ejemplo 08:00."
    if tipo.startswith("int"):
        return f"«{campo}» debe ser un número entero."
    if tipo.startswith("decimal") or tipo.startswith("float"):
        return f"«{campo}» debe ser un número."
    if tipo in ("bool_type", "bool_parsing"):
        return f"«{campo}» debe ser true o false."
    if tipo in COMPARACIONES:
        simbolo, clave = COMPARACIONES[tipo]
        return f"«{campo}» debe ser {simbolo} {ctx.get(clave)}."
    if tipo in TIPOS_ESPERADOS:
        return f"«{campo}» debe ser {TIPOS_ESPERADOS[tipo]}."
    return f"«{campo}»: {e.get('msg', 'valor no válido')}."


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorDominio)
    async def _error_dominio(_: Request, error: ErrorDominio) -> JSONResponse:
        return respuesta_error(codigo_para(error), type(error).__name__, str(error))

    @app.exception_handler(RequestValidationError)
    async def _error_validacion(_: Request, error: RequestValidationError) -> JSONResponse:
        frases = list(dict.fromkeys(explicar_validacion(e) for e in error.errors()))
        detalle = " ".join(frases[:3]) + (f" (y {len(frases) - 3} más)" if len(frases) > 3 else "")
        return respuesta_error(422, "DatosInvalidos", detalle)

    @app.exception_handler(StarletteHTTPException)
    async def _error_http(request: Request, error: StarletteHTTPException) -> JSONResponse:
        if error.status_code == 404:
            return respuesta_error(
                404,
                "RutaNoEncontrada",
                f"No existe {request.method} {request.url.path}. Revisa la lista de endpoints en /docs.",
            )
        if error.status_code == 405:
            return respuesta_error(
                405,
                "MetodoNoPermitido",
                f"{request.url.path} no acepta {request.method}. Revisa en /docs qué métodos tiene.",
            )
        return respuesta_error(error.status_code, "ErrorHTTP", str(error.detail))

    @app.exception_handler(Exception)
    async def _error_inesperado(request: Request, error: Exception) -> JSONResponse:
        registro.exception("Error no controlado en %s %s", request.method, request.url.path)
        return respuesta_error(
            500, "ErrorInterno", "Ocurrió un error inesperado. Intenta de nuevo; si sigue pasando, avisa a Soporte."
        )
