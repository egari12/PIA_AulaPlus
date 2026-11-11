"""Endpoints de registro de estudiantes (US-19). No piden X-Rol: los usa un visitante."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencias import servicio_estudiantes
from src.api.errores import RESPUESTAS_ERROR
from src.api.esquemas import AccesoEntrada, CuentaSalida, RegistroEntrada
from src.application.servicios_estudiantes import ServicioEstudiantes

router = APIRouter(prefix="/estudiantes", tags=["Estudiantes"], responses=RESPUESTAS_ERROR)


@router.post(
    "",
    response_model=CuentaSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Crear cuenta de estudiante (US-19)",
    description="Registra a un estudiante nuevo con nombre, correo y ciudad. Su número empieza con AUL-E. "
    "Responde 409 si el correo ya tiene cuenta y 422 si un dato no es válido.",
)
def registrar(datos: RegistroEntrada, servicio: ServicioEstudiantes = Depends(servicio_estudiantes)):
    return CuentaSalida.de(servicio.registrar(datos.nombre, datos.correo, datos.ciudad))


@router.post(
    "/acceso",
    response_model=CuentaSalida,
    summary="Entrar con el correo (US-19)",
    description="Busca la cuenta por correo. No hay contraseña: es un registro, no autenticación (ADR-005). "
    "Responde 404 si no hay cuenta con ese correo.",
)
def acceder(datos: AccesoEntrada, servicio: ServicioEstudiantes = Depends(servicio_estudiantes)):
    return CuentaSalida.de(servicio.acceder(datos.correo))
