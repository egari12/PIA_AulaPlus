"""Specifications del contexto Sesiones: asignación automática de tutor (NB-01, US-02, US-10)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from src.domain.comun import ZONA_NEGOCIO
from src.domain.especificacion import Especificacion
from src.domain.sesiones.modelo import (
    ANTICIPACION_MINIMA,
    DURACION_SESION,
    MAX_SESIONES_POR_DIA,
    Modalidad,
    SolicitudReserva,
    Tutor,
)


class AnticipacionMinima(Especificacion[SolicitudReserva]):
    """RN-06 / US-01: la sesión inicia al menos 48 h después de 'ahora'."""

    descripcion = "anticipación mínima de 48 h"

    def __init__(self, ahora: datetime):
        self.ahora = ahora

    def es_satisfecha_por(self, candidato: SolicitudReserva) -> bool:
        return candidato.inicio - self.ahora >= ANTICIPACION_MINIMA


@dataclass(frozen=True)
class CandidatoTutor:
    tutor: Tutor
    solicitud: SolicitudReserva
    inicios_ocupados: tuple[datetime, ...] = ()


class ImparteMateria(Especificacion[CandidatoTutor]):
    descripcion = "imparte la materia"

    def es_satisfecha_por(self, c: CandidatoTutor) -> bool:
        return c.tutor.imparte(c.solicitud.materia)


class OfreceModalidad(Especificacion[CandidatoTutor]):
    descripcion = "ofrece la modalidad"

    def es_satisfecha_por(self, c: CandidatoTutor) -> bool:
        return c.solicitud.modalidad in c.tutor.modalidades


class EsPresencial(Especificacion[CandidatoTutor]):
    descripcion = "sesión presencial"

    def es_satisfecha_por(self, c: CandidatoTutor) -> bool:
        return c.solicitud.modalidad is Modalidad.PRESENCIAL


class MismaZona(Especificacion[CandidatoTutor]):
    descripcion = "atiende la zona"

    def es_satisfecha_por(self, c: CandidatoTutor) -> bool:
        zona = (c.solicitud.zona or "").strip().lower()
        return zona == c.tutor.zona.strip().lower()


class DentroDeDisponibilidad(Especificacion[CandidatoTutor]):
    """RN-07: la sesión cae dentro de un bloque registrado por el tutor."""

    descripcion = "dentro de su disponibilidad"

    def es_satisfecha_por(self, c: CandidatoTutor) -> bool:
        return c.tutor.disponible_en(c.solicitud.inicio, c.solicitud.fin)


class BajoLimiteDiario(Especificacion[CandidatoTutor]):
    """RN-04: menos de 5 sesiones ese día calendario (hora local)."""

    descripcion = "menos de 5 sesiones ese día"

    def __init__(self, maximo: int = MAX_SESIONES_POR_DIA):
        self.maximo = maximo

    def es_satisfecha_por(self, c: CandidatoTutor) -> bool:
        dia = c.solicitud.inicio.astimezone(ZONA_NEGOCIO).date()
        del_dia = sum(1 for i in c.inicios_ocupados if i.astimezone(ZONA_NEGOCIO).date() == dia)
        return del_dia < self.maximo


class SinTraslape(Especificacion[CandidatoTutor]):
    descripcion = "sin traslape con otra sesión"

    def es_satisfecha_por(self, c: CandidatoTutor) -> bool:
        inicio, fin = c.solicitud.inicio, c.solicitud.fin
        return all(not (o < fin and inicio < o + DURACION_SESION) for o in c.inicios_ocupados)


def regla_asignacion() -> Especificacion[CandidatoTutor]:
    """Composición AND / OR / NOT: la zona solo importa si la sesión es presencial."""
    return (
        ImparteMateria()
        & OfreceModalidad()
        & (~EsPresencial() | MismaZona())
        & DentroDeDisponibilidad()
        & BajoLimiteDiario()
        & SinTraslape()
    )


def seleccionar_tutor(
    tutores: Iterable[Tutor],
    solicitud: SolicitudReserva,
    ocupados_por_tutor: Mapping[str, Iterable[datetime]],
) -> Tutor | None:
    """Devuelve el tutor elegible con menos sesiones ese día (desempate por id)."""
    regla = regla_asignacion()
    dia = solicitud.inicio.astimezone(ZONA_NEGOCIO).date()
    elegibles: list[tuple[int, str, Tutor]] = []
    for tutor in tutores:
        ocupados = tuple(ocupados_por_tutor.get(tutor.id, ()))
        if regla.es_satisfecha_por(CandidatoTutor(tutor, solicitud, ocupados)):
            carga = sum(1 for i in ocupados if i.astimezone(ZONA_NEGOCIO).date() == dia)
            elegibles.append((carga, tutor.id, tutor))
    if not elegibles:
        return None
    return min(elegibles, key=lambda e: (e[0], e[1]))[2]
