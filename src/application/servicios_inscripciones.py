"""Casos de uso del contexto Inscripciones (usados por la API y por el ejecutor de casos CSV)."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date

from src.application.puertos import Reloj, UnidadDeTrabajo
from src.domain.comun import DatosInvalidos, NoEncontrado
from src.domain.inscripciones.modelo import Curso, Estudiante, Inscripcion, ResultadoBeneficio


@dataclass(frozen=True)
class LineaSolicitada:
    curso_id: str
    cantidad: int


def _nuevo_id() -> str:
    return "INS-" + uuid.uuid4().hex[:10].upper()


class ServicioInscripciones:
    def __init__(self, uow: UnidadDeTrabajo, reloj: Reloj, generar_id: Callable[[], str] = _nuevo_id):
        self.uow, self.reloj, self.generar_id = uow, reloj, generar_id

    # -- consultas ---------------------------------------------------------- #
    def obtener(self, inscripcion_id: str) -> Inscripcion:
        inscripcion = self.uow.inscripciones.obtener(inscripcion_id)
        if inscripcion is None:
            raise NoEncontrado(f"La inscripción {inscripcion_id} no existe")
        return inscripcion

    def listar(self) -> list[Inscripcion]:
        return self.uow.inscripciones.listar()

    def estudiante(self, estudiante_id: str) -> Estudiante:
        estudiante = self.uow.estudiantes.obtener(estudiante_id)
        if estudiante is None:
            raise NoEncontrado(f"El estudiante {estudiante_id} no existe")
        return estudiante

    def curso(self, curso_id: str) -> Curso:
        curso = self.uow.cursos.obtener(curso_id)
        if curso is None:
            raise NoEncontrado(f"El curso {curso_id} no existe")
        return curso

    def _cursos_de(self, inscripcion: Inscripcion) -> dict[str, Curso]:
        return {cid: self.curso(cid) for cid in inscripcion.cantidades_por_curso()}

    # -- comandos ----------------------------------------------------------- #
    def crear(
        self,
        estudiante_id: str,
        lineas: Iterable[LineaSolicitada],
        autorizada: bool,
        promocion_activa: bool = False,
        referencia: str = "",
    ) -> Inscripcion:
        self.estudiante(estudiante_id)  # 404 si no existe
        inscripcion = Inscripcion(
            id=self.generar_id(),
            estudiante_id=estudiante_id,
            fecha_solicitud=self.reloj.ahora().date(),
            promocion_activa=promocion_activa,
            autorizada=autorizada,
            referencia=referencia,
        )
        for linea in lineas:
            inscripcion.agregar_linea(self.curso(linea.curso_id), linea.cantidad)
        self.uow.inscripciones.guardar(inscripcion)
        self.uow.commit()
        return inscripcion

    def validar(self, inscripcion_id: str) -> Inscripcion:
        inscripcion = self.obtener(inscripcion_id)
        estudiante = self.uow.estudiantes.obtener(inscripcion.estudiante_id)
        inscripcion.validar(estudiante, self.reloj.ahora())
        return self._guardar(inscripcion)

    def inscribir(self, inscripcion_id: str) -> Inscripcion:
        inscripcion = self.obtener(inscripcion_id)
        cursos = self._cursos_de(inscripcion)
        inscripcion.inscribir(cursos, self.reloj.ahora())
        for curso in cursos.values():
            self.uow.cursos.guardar(curso)  # cupo descontado
        return self._guardar(inscripcion)

    def finalizar(self, inscripcion_id: str) -> Inscripcion:
        inscripcion = self.obtener(inscripcion_id)
        inscripcion.finalizar(self.reloj.ahora())
        return self._guardar(inscripcion)

    def cancelar(self, inscripcion_id: str, motivo: str) -> Inscripcion:
        inscripcion = self.obtener(inscripcion_id)
        inscripcion.cancelar(motivo, self.reloj.ahora())
        return self._guardar(inscripcion)

    def evaluar_beneficio(self, inscripcion_id: str) -> ResultadoBeneficio:
        inscripcion = self.obtener(inscripcion_id)
        return inscripcion.evaluar_beneficio(self.uow.estudiantes.obtener(inscripcion.estudiante_id))

    def _guardar(self, inscripcion: Inscripcion) -> Inscripcion:
        self.uow.inscripciones.guardar(inscripcion)
        self.uow.commit()
        return inscripcion


def fecha_iso(valor: str) -> date:
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise DatosInvalidos(f"Fecha inválida: {valor}") from None
