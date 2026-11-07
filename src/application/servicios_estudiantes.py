"""Casos de uso US-19 y US-20: estudiantes y tutores crean su cuenta y vuelven a entrar con su correo.

No es autenticación (no hay contraseña): los permisos siguen saliendo de X-Rol (ADR-005).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.puertos import UnidadDeTrabajo
from src.domain.comun import DatosInvalidos, NoEncontrado, RecursoNoDisponible
from src.domain.inscripciones.modelo import Estudiante
from src.domain.registro import (
    Cuenta,
    TipoCuenta,
    normalizar_ciudad,
    normalizar_correo,
    normalizar_nombre,
    siguiente_id_estudiante,
    siguiente_id_tutor,
)
from src.domain.sesiones.modelo import BloqueDisponibilidad, Modalidad, Tutor

MSG_CORREO_REGISTRADO = "Ya existe una cuenta con ese correo"
MSG_CUENTA_NO_EXISTE = "No hay ninguna cuenta con ese correo"
MSG_SIN_HORARIO = "Indica al menos un horario disponible"


@dataclass(frozen=True)
class EstudianteRegistrado:
    estudiante: Estudiante
    correo: str


@dataclass(frozen=True)
class TutorRegistrado:
    tutor: Tutor
    correo: str


class ServicioEstudiantes:
    def __init__(self, uow: UnidadDeTrabajo):
        self.uow = uow

    def _correo_libre(self, correo: str) -> str:
        correo = normalizar_correo(correo)
        if self.uow.cuentas.obtener(correo) is not None:
            raise RecursoNoDisponible(MSG_CORREO_REGISTRADO)
        return correo

    def _cuenta(self, correo: str, tipo: TipoCuenta) -> Cuenta:
        cuenta = self.uow.cuentas.obtener(normalizar_correo(correo))
        if cuenta is None or cuenta.tipo is not tipo:
            raise NoEncontrado(MSG_CUENTA_NO_EXISTE)
        return cuenta

    # -- US-19: estudiantes --------------------------------------------------- #
    def registrar(self, nombre: str, correo: str, ciudad: str) -> EstudianteRegistrado:
        nombre, ciudad = normalizar_nombre(nombre), normalizar_ciudad(ciudad)
        correo = self._correo_libre(correo)
        nuevo_id = siguiente_id_estudiante(e.id for e in self.uow.estudiantes.listar())
        estudiante = Estudiante(nuevo_id, nombre, preferente=False, activo=True, ciudad=ciudad)
        self.uow.estudiantes.guardar(estudiante)
        self.uow.cuentas.guardar(Cuenta(correo, nuevo_id, TipoCuenta.ESTUDIANTE))
        self.uow.commit()
        return EstudianteRegistrado(estudiante, correo)

    def acceder(self, correo: str) -> EstudianteRegistrado:
        cuenta = self._cuenta(correo, TipoCuenta.ESTUDIANTE)
        estudiante = self.uow.estudiantes.obtener(cuenta.usuario_id)
        if estudiante is None:
            raise NoEncontrado(MSG_CUENTA_NO_EXISTE)
        return EstudianteRegistrado(estudiante, cuenta.correo)

    # -- US-20: tutores ------------------------------------------------------- #
    def registrar_tutor(
        self,
        nombre: str,
        correo: str,
        materias: list[str],
        modalidades: list[Modalidad],
        zona: str,
        bloques: list[BloqueDisponibilidad],
    ) -> TutorRegistrado:
        nombre, zona = normalizar_nombre(nombre), normalizar_ciudad(zona)
        if not bloques:
            raise DatosInvalidos(MSG_SIN_HORARIO)
        correo = self._correo_libre(correo)
        nuevo_id = siguiente_id_tutor(t.id for t in self.uow.tutores.listar())
        # El agregado Tutor valida que haya al menos una materia y una modalidad.
        tutor = Tutor(nuevo_id, nombre, frozenset(materias), frozenset(modalidades), zona, tuple(bloques))
        self.uow.tutores.guardar(tutor)
        self.uow.cuentas.guardar(Cuenta(correo, nuevo_id, TipoCuenta.TUTOR))
        self.uow.commit()
        return TutorRegistrado(tutor, correo)

    def acceder_tutor(self, correo: str) -> TutorRegistrado:
        cuenta = self._cuenta(correo, TipoCuenta.TUTOR)
        tutor = self.uow.tutores.obtener(cuenta.usuario_id)
        if tutor is None:
            raise NoEncontrado(MSG_CUENTA_NO_EXISTE)
        return TutorRegistrado(tutor, cuenta.correo)
