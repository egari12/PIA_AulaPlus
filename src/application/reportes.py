"""US-15: reportes de operación para Administración."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from src.application.puertos import UnidadDeTrabajo
from src.domain.comun import DatosInvalidos, Dinero, Rol, a_utc, exigir_rol
from src.domain.sesiones.modelo import EstadoSesion


@dataclass(frozen=True)
class ReporteSesiones:
    desde: datetime
    hasta: datetime
    por_estado: dict[str, int]
    por_estado_pago: dict[str, int]
    total_cobrado: Dinero
    total_comisiones: Dinero
    total_reembolsado: Dinero


@dataclass(frozen=True)
class FilaCancelacionesTutor:
    tutor_id: str
    nombre: str
    cancelaciones: int
    penalizaciones: int
    estado_penalizacion: str


class ServicioReportes:
    def __init__(self, uow: UnidadDeTrabajo):
        self.uow = uow

    def sesiones(self, rol: Rol, desde: datetime, hasta: datetime) -> ReporteSesiones:
        exigir_rol(rol, Rol.ADMINISTRADOR)
        desde, hasta = a_utc(desde, "desde"), a_utc(hasta, "hasta")
        if hasta < desde:
            raise DatosInvalidos("'hasta' debe ser posterior a 'desde'")
        sesiones = [s for s in self.uow.sesiones.listar() if desde <= s.inicio <= hasta]
        por_estado = {estado.value: 0 for estado in EstadoSesion}
        por_estado.update(Counter(s.estado.value for s in sesiones))
        cobrado = comisiones = reembolsado = Dinero.cero()
        for s in sesiones:
            cobrado = cobrado + s.precio
            reembolsado = reembolsado + s.monto_reembolso
            if s.liquidacion:
                comisiones = comisiones + s.liquidacion.comision
        return ReporteSesiones(
            desde,
            hasta,
            por_estado,
            dict(Counter(s.estado_pago for s in sesiones)),
            cobrado,
            comisiones,
            reembolsado,
        )

    def cancelaciones_por_tutor(self, rol: Rol) -> list[FilaCancelacionesTutor]:
        exigir_rol(rol, Rol.ADMINISTRADOR)
        filas = [
            FilaCancelacionesTutor(
                t.id, t.nombre, t.cancelaciones, t.penalizaciones, t.estado_penalizacion
            )
            for t in self.uow.tutores.listar()
        ]
        return sorted(filas, key=lambda f: (-f.cancelaciones, f.tutor_id))
