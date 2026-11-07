"""Registro con correo de estudiantes (US-19) y tutores (US-20). No piden X-Rol: los usa un visitante.

No es autenticación: no hay contraseña y los permisos siguen saliendo de X-Rol (ADR-005).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencias import servicio_estudiantes
from src.api.errores import RESPUESTAS_ERROR
from src.api.esquemas import (
    AccesoEntrada,
    CuentaSalida,
    CuentaTutorSalida,
    RegistroEntrada,
    RegistroTutorEntrada,
)
from src.application.servicios_estudiantes import ServicioEstudiantes
from src.domain.sesiones.modelo import BloqueDisponibilidad

router_estudiantes = APIRouter(prefix="/estudiantes", tags=["Estudiantes"], responses=RESPUESTAS_ERROR)
router_tutores = APIRouter(prefix="/tutores", tags=["Tutores"], responses=RESPUESTAS_ERROR)


@router_estudiantes.post(
    "",
    response_model=CuentaSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Crear cuenta de estudiante (US-19)",
    description="Registra a un estudiante nuevo con nombre, correo y ciudad. Su número empieza con AUL-E. "
    "Responde 409 si el correo ya tiene cuenta y 422 si un dato no es válido.",
)
def registrar(datos: RegistroEntrada, servicio: ServicioEstudiantes = Depends(servicio_estudiantes)):
    return CuentaSalida.de(servicio.registrar(datos.nombre, datos.correo, datos.ciudad))


@router_estudiantes.post(
    "/acceso",
    response_model=CuentaSalida,
    summary="Estudiante: entrar con el correo (US-19)",
    description="Busca la cuenta de estudiante por correo. Responde 404 si no hay una con ese correo.",
)
def acceder(datos: AccesoEntrada, servicio: ServicioEstudiantes = Depends(servicio_estudiantes)):
    return CuentaSalida.de(servicio.acceder(datos.correo))


@router_tutores.post(
    "",
    response_model=CuentaTutorSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Crear cuenta de tutor (US-20)",
    description="Registra a un tutor nuevo con sus materias, modalidades, zona y horarios. Su número sigue "
    "después del último tutor (AUL-T06, ...) y desde ese momento entra en la asignación automática. "
    "Responde 409 si el correo ya tiene cuenta y 422 si falta una materia, una modalidad o un horario.",
)
def registrar_tutor(datos: RegistroTutorEntrada, servicio: ServicioEstudiantes = Depends(servicio_estudiantes)):
    bloques = [BloqueDisponibilidad(b.dia_semana, b.hora_inicio, b.hora_fin) for b in datos.bloques]
    registro = servicio.registrar_tutor(
        datos.nombre, datos.correo, datos.materias, datos.modalidades, datos.zona, bloques
    )
    return CuentaTutorSalida.de_registro(registro)


@router_tutores.post(
    "/acceso",
    response_model=CuentaTutorSalida,
    summary="Tutor: entrar con el correo (US-20)",
    description="Busca la cuenta de tutor por correo. Responde 404 si no hay una con ese correo.",
)
def acceder_tutor(datos: AccesoEntrada, servicio: ServicioEstudiantes = Depends(servicio_estudiantes)):
    return CuentaTutorSalida.de_registro(servicio.acceder_tutor(datos.correo))
