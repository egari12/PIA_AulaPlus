"""Endpoints de Administración: reportes (US-15) y políticas (US-16)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends

from src.api.dependencias import obtener_rol, servicio_politicas, servicio_reportes
from src.api.errores import RESPUESTAS_ERROR
from src.api.esquemas import (
    CancelacionesTutorSalida,
    ComisionEntrada,
    PoliticaSalida,
    ReporteSesionesSalida,
)
from src.application.reportes import ServicioReportes
from src.application.servicios_sesiones import ServicioPoliticas
from src.domain.comun import Rol

router = APIRouter(tags=["Administración"], responses=RESPUESTAS_ERROR)


@router.get("/reportes/sesiones", response_model=ReporteSesionesSalida,
            summary="US-15: sesiones agendadas, completadas y canceladas por periodo")
def reporte_sesiones(desde: datetime, hasta: datetime, rol: Rol = Depends(obtener_rol),
                     servicio: ServicioReportes = Depends(servicio_reportes)):
    r = servicio.sesiones(rol, desde, hasta)
    return ReporteSesionesSalida(
        desde=r.desde, hasta=r.hasta, por_estado=r.por_estado, por_estado_pago=r.por_estado_pago,
        total_cobrado=r.total_cobrado.monto, total_comisiones=r.total_comisiones.monto,
        total_reembolsado=r.total_reembolsado.monto,
    )


@router.get("/reportes/cancelaciones-tutores", response_model=list[CancelacionesTutorSalida],
            summary="US-15: tutores ordenados por cancelaciones con su estado de penalización")
def reporte_cancelaciones(rol: Rol = Depends(obtener_rol),
                          servicio: ServicioReportes = Depends(servicio_reportes)):
    return [CancelacionesTutorSalida(**f.__dict__) for f in servicio.cancelaciones_por_tutor(rol)]


@router.get("/politicas", response_model=PoliticaSalida, summary="Política de tarifas vigente")
def obtener_politica(servicio: ServicioPoliticas = Depends(servicio_politicas)):
    p = servicio.obtener()
    return PoliticaSalida(precio=p.precio.monto, porcentaje_comision=p.porcentaje_comision)


@router.put("/politicas/comision", response_model=PoliticaSalida,
            summary="US-16: Administración cambia el % de comisión (aplica a liquidaciones futuras)")
def actualizar_comision(datos: ComisionEntrada, rol: Rol = Depends(obtener_rol),
                        servicio: ServicioPoliticas = Depends(servicio_politicas)):
    p = servicio.actualizar_comision(rol, datos.porcentaje)
    return PoliticaSalida(precio=p.precio.monto, porcentaje_comision=p.porcentaje_comision)
