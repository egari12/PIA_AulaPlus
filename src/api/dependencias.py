"""Inyección de dependencias de FastAPI: una Unidad de Trabajo por petición y servicios armados."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Header, Request

from src.application.reportes import ServicioReportes
from src.application.servicios_estudiantes import ServicioEstudiantes
from src.application.servicios_inscripciones import ServicioInscripciones
from src.application.servicios_sesiones import ServicioPoliticas, ServicioSesiones
from src.domain.comun import Rol
from src.infrastructure.repositorios_sql import UnidadDeTrabajoSQL


def obtener_uow(request: Request) -> Iterator[UnidadDeTrabajoSQL]:
    uow = UnidadDeTrabajoSQL(request.app.state.fabrica_sesiones)
    try:
        yield uow
    except Exception:
        uow.rollback()
        raise
    finally:
        uow.cerrar()


def obtener_rol(
    x_rol: Rol = Header(
        ...,
        alias="X-Rol",
        description="Rol de quien llama: ESTUDIANTE, TUTOR, SOPORTE, ADMINISTRADOR o SISTEMA",
    ),
) -> Rol:
    return x_rol


def servicio_sesiones(request: Request, uow: UnidadDeTrabajoSQL = Depends(obtener_uow)) -> ServicioSesiones:
    return ServicioSesiones(uow, request.app.state.pasarela, request.app.state.reloj)


def servicio_politicas(uow: UnidadDeTrabajoSQL = Depends(obtener_uow)) -> ServicioPoliticas:
    return ServicioPoliticas(uow)


def servicio_reportes(uow: UnidadDeTrabajoSQL = Depends(obtener_uow)) -> ServicioReportes:
    return ServicioReportes(uow)


def servicio_inscripciones(
    request: Request, uow: UnidadDeTrabajoSQL = Depends(obtener_uow)
) -> ServicioInscripciones:
    return ServicioInscripciones(uow, request.app.state.reloj)


def servicio_estudiantes(uow: UnidadDeTrabajoSQL = Depends(obtener_uow)) -> ServicioEstudiantes:
    return ServicioEstudiantes(uow)
