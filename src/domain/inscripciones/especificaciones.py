"""Specifications del contexto Inscripciones (reglas del paquete de pruebas del docente)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from src.domain.especificacion import Especificacion
from src.domain.inscripciones.modelo import Curso, Estudiante, Inscripcion

UMBRAL_BENEFICIO = Decimal("1500")


@dataclass(frozen=True)
class ContextoInscripcion:
    inscripcion: Inscripcion
    estudiante: Estudiante | None = None
    cursos: Mapping[str, Curso] | None = None


class EstudianteActivo(Especificacion[ContextoInscripcion]):
    descripcion = "estudiante activo"

    def es_satisfecha_por(self, c: ContextoInscripcion) -> bool:
        return c.estudiante is not None and c.estudiante.activo


class TieneDetalle(Especificacion[ContextoInscripcion]):
    descripcion = "detalle no vacío"

    def es_satisfecha_por(self, c: ContextoInscripcion) -> bool:
        return len(c.inscripcion.lineas) > 0


class Autorizada(Especificacion[ContextoInscripcion]):
    descripcion = "autorización"

    def es_satisfecha_por(self, c: ContextoInscripcion) -> bool:
        return c.inscripcion.autorizada


class EstudiantePreferente(Especificacion[ContextoInscripcion]):
    descripcion = "estudiante preferente"

    def es_satisfecha_por(self, c: ContextoInscripcion) -> bool:
        return c.estudiante is not None and c.estudiante.preferente


class TotalMinimo(Especificacion[ContextoInscripcion]):
    def __init__(self, minimo: Decimal):
        self.minimo = minimo
        self.descripcion = f"total >= {minimo}"

    def es_satisfecha_por(self, c: ContextoInscripcion) -> bool:
        return c.inscripcion.total.monto >= self.minimo


class PromocionActiva(Especificacion[ContextoInscripcion]):
    descripcion = "promoción activa"

    def es_satisfecha_por(self, c: ContextoInscripcion) -> bool:
        return c.inscripcion.promocion_activa


class CursosHabilitados(Especificacion[ContextoInscripcion]):
    descripcion = "cursos habilitados"

    def es_satisfecha_por(self, c: ContextoInscripcion) -> bool:
        cursos = c.cursos or {}
        return all(
            linea.curso_id in cursos and cursos[linea.curso_id].habilitado
            for linea in c.inscripcion.lineas
        )


class CupoDisponible(Especificacion[ContextoInscripcion]):
    descripcion = "cupo disponible"

    def es_satisfecha_por(self, c: ContextoInscripcion) -> bool:
        cursos = c.cursos or {}
        return all(
            curso_id in cursos and cantidad <= cursos[curso_id].cupo
            for curso_id, cantidad in c.inscripcion.cantidades_por_curso().items()
        )


# Reglas del paquete (INSTRUCCIONES_ALUMNO.txt)
PUEDE_PROCESARSE = EstudianteActivo() & TieneDetalle() & Autorizada()
BENEFICIO_REFERENCIA = EstudiantePreferente() & TotalMinimo(UMBRAL_BENEFICIO) & ~PromocionActiva()
# Precondiciones de 'inscribir' (cupo_disponible del paquete)
PUEDE_INSCRIBIRSE = CursosHabilitados() & CupoDisponible()
