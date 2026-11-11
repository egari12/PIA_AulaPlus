"""Caso de uso US-19: un visitante crea su cuenta de estudiante y vuelve a entrar con su correo."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.puertos import UnidadDeTrabajo
from src.domain.comun import NoEncontrado, RecursoNoDisponible
from src.domain.inscripciones.modelo import Estudiante
from src.domain.registro import (
    CuentaEstudiante,
    normalizar_ciudad,
    normalizar_correo,
    normalizar_nombre,
    siguiente_id_estudiante,
)

MSG_CORREO_REGISTRADO = "Ya existe una cuenta con ese correo"
MSG_CUENTA_NO_EXISTE = "No hay ninguna cuenta con ese correo"


@dataclass(frozen=True)
class EstudianteRegistrado:
    estudiante: Estudiante
    correo: str


class ServicioEstudiantes:
    def __init__(self, uow: UnidadDeTrabajo):
        self.uow = uow

    def registrar(self, nombre: str, correo: str, ciudad: str) -> EstudianteRegistrado:
        nombre, correo, ciudad = normalizar_nombre(nombre), normalizar_correo(correo), normalizar_ciudad(ciudad)
        if self.uow.cuentas.obtener(correo) is not None:
            raise RecursoNoDisponible(MSG_CORREO_REGISTRADO)
        nuevo_id = siguiente_id_estudiante(e.id for e in self.uow.estudiantes.listar())
        estudiante = Estudiante(nuevo_id, nombre, preferente=False, activo=True, ciudad=ciudad)
        self.uow.estudiantes.guardar(estudiante)
        self.uow.cuentas.guardar(CuentaEstudiante(correo, nuevo_id))
        self.uow.commit()
        return EstudianteRegistrado(estudiante, correo)

    def acceder(self, correo: str) -> EstudianteRegistrado:
        cuenta = self.uow.cuentas.obtener(normalizar_correo(correo))
        estudiante = self.uow.estudiantes.obtener(cuenta.estudiante_id) if cuenta else None
        if cuenta is None or estudiante is None:
            raise NoEncontrado(MSG_CUENTA_NO_EXISTE)
        return EstudianteRegistrado(estudiante, cuenta.correo)
