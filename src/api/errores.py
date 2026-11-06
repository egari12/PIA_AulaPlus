"""Traducción de excepciones de dominio a códigos HTTP (contrato del equipo)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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

CODIGOS: dict[type[ErrorDominio], int] = {
    NoEncontrado: 404,
    PermisoDenegado: 403,
    PagoRechazado: 402,
    TransicionInvalida: 409,
    RecursoNoDisponible: 409,
    DatosInvalidos: 422,
    ReglaNegocioViolada: 422,
}

RESPUESTAS_ERROR = {
    402: {"description": "Pago rechazado"},
    403: {"description": "Rol sin permiso"},
    404: {"description": "No encontrado"},
    409: {"description": "Transición inválida o recurso no disponible"},
    422: {"description": "Datos inválidos o regla de negocio violada"},
}


def codigo_para(error: ErrorDominio) -> int:
    for tipo in type(error).__mro__:
        if tipo in CODIGOS:
            return CODIGOS[tipo]
    return 400


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorDominio)
    async def _error_dominio(_: Request, error: ErrorDominio) -> JSONResponse:
        return JSONResponse(
            status_code=codigo_para(error),
            content={"error": type(error).__name__, "detalle": str(error)},
        )
