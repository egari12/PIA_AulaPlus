"""Endpoints del contexto Sesiones (núcleo del BRD)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencias import obtener_rol, servicio_sesiones
from src.api.errores import RESPUESTAS_ERROR
from src.api.esquemas import (
    BloqueEntrada,
    CalificacionEntrada,
    CambioEntrada,
    CancelacionEntrada,
    DisponibilidadEntrada,
    EventoSalida,
    GrabacionEntrada,
    LiquidacionSalida,
    ReservaEntrada,
    SesionSalida,
    TutorSalida,
)
from src.application.servicios_sesiones import ServicioSesiones
from src.domain.comun import Rol
from src.domain.sesiones.modelo import BloqueDisponibilidad, EstadoSesion, SolicitudReserva

router = APIRouter(tags=["Sesiones"], responses=RESPUESTAS_ERROR)
router_tutores = APIRouter(prefix="/tutores", tags=["Tutores"], responses=RESPUESTAS_ERROR)


@router.post("/sesiones", status_code=status.HTTP_201_CREATED, response_model=SesionSalida,
             summary="US-01/02/03: reservar sesión (asigna tutor y cobra $200)")
def reservar(datos: ReservaEntrada, rol: Rol = Depends(obtener_rol),
             servicio: ServicioSesiones = Depends(servicio_sesiones)):
    solicitud = SolicitudReserva(
        datos.estudiante_id, datos.materia, datos.tema, datos.modalidad, datos.inicio, datos.zona
    )
    return SesionSalida.de(servicio.reservar(rol, solicitud))


@router.get("/sesiones", response_model=list[SesionSalida], summary="Listar sesiones")
def listar(estado: EstadoSesion | None = None, servicio: ServicioSesiones = Depends(servicio_sesiones)):
    return [SesionSalida.de(s) for s in servicio.listar(estado)]


@router.get("/sesiones/{sesion_id}", response_model=SesionSalida, summary="Consultar sesión")
def obtener(sesion_id: str, servicio: ServicioSesiones = Depends(servicio_sesiones)):
    return SesionSalida.de(servicio.obtener(sesion_id))


@router.get("/sesiones/{sesion_id}/eventos", response_model=list[EventoSalida],
            summary="Domain Events registrados de la sesión")
def eventos(sesion_id: str, servicio: ServicioSesiones = Depends(servicio_sesiones)):
    servicio.obtener(sesion_id)
    return [EventoSalida.de(e) for e in servicio.uow.sesiones.eventos_de(sesion_id)]


@router.post("/sesiones/{sesion_id}/grabacion", response_model=SesionSalida,
             summary="US-14: registrar grabación (>= 70 % completa, < 70 % reembolsa)")
def registrar_grabacion(sesion_id: str, datos: GrabacionEntrada, rol: Rol = Depends(obtener_rol),
                        servicio: ServicioSesiones = Depends(servicio_sesiones)):
    return SesionSalida.de(servicio.registrar_grabacion(rol, sesion_id, datos.url, datos.inicio, datos.fin))


@router.post("/sesiones/{sesion_id}/liquidacion", response_model=LiquidacionSalida,
             summary="US-11: liquidar $160 al tutor y $40 de comisión")
def liquidar(sesion_id: str, rol: Rol = Depends(obtener_rol),
             servicio: ServicioSesiones = Depends(servicio_sesiones)):
    r = servicio.liquidar(rol, sesion_id)
    return LiquidacionSalida(
        sesion_id=r.sesion_id, estado_pago=r.estado_pago, monto_tutor=r.monto_tutor.monto,
        comision=r.comision.monto, referencia=r.referencia, mensaje=r.mensaje,
    )


@router.post("/sesiones/{sesion_id}/cancelacion", response_model=SesionSalida,
             summary="US-13: Soporte ejecuta la cancelación (aplica reembolso/penalización)")
def cancelar(sesion_id: str, datos: CancelacionEntrada, rol: Rol = Depends(obtener_rol),
             servicio: ServicioSesiones = Depends(servicio_sesiones)):
    return SesionSalida.de(
        servicio.cancelar(rol, sesion_id, datos.solicitante, datos.motivo, datos.justificada)
    )


@router.post("/sesiones/{sesion_id}/calificaciones", response_model=SesionSalida,
             summary="US-04 / RN-10: calificar dentro de 24 h")
def calificar(sesion_id: str, datos: CalificacionEntrada, rol: Rol = Depends(obtener_rol),
              servicio: ServicioSesiones = Depends(servicio_sesiones)):
    return SesionSalida.de(servicio.calificar(rol, sesion_id, datos.puntuacion))


@router.post("/sesiones/{sesion_id}/cambios", response_model=SesionSalida,
             summary="US-06/07: solicitar cambio de horario o modalidad")
def solicitar_cambio(sesion_id: str, datos: CambioEntrada, rol: Rol = Depends(obtener_rol),
                     servicio: ServicioSesiones = Depends(servicio_sesiones)):
    return SesionSalida.de(servicio.solicitar_cambio(rol, sesion_id, datos.tipo, datos.valor))


@router.post("/sesiones/{sesion_id}/cambios/aplicar", response_model=SesionSalida,
             summary="Soporte aplica el cambio pendiente")
def aplicar_cambio(sesion_id: str, rol: Rol = Depends(obtener_rol),
                   servicio: ServicioSesiones = Depends(servicio_sesiones)):
    return SesionSalida.de(servicio.aplicar_cambio(rol, sesion_id))


# --------------------------------------------------------------------------- #
@router_tutores.get("", response_model=list[TutorSalida], summary="Listar tutores")
def listar_tutores(servicio: ServicioSesiones = Depends(servicio_sesiones)):
    return [TutorSalida.de(t) for t in servicio.uow.tutores.listar()]


@router_tutores.get("/{tutor_id}", response_model=TutorSalida, summary="Consultar tutor")
def obtener_tutor(tutor_id: str, servicio: ServicioSesiones = Depends(servicio_sesiones)):
    return TutorSalida.de(servicio.obtener_tutor(tutor_id))


@router_tutores.put("/{tutor_id}/disponibilidad", response_model=TutorSalida,
                    summary="US-09: actualizar disponibilidad del tutor")
def actualizar_disponibilidad(tutor_id: str, datos: DisponibilidadEntrada, rol: Rol = Depends(obtener_rol),
                              servicio: ServicioSesiones = Depends(servicio_sesiones)):
    bloques = [_bloque(b) for b in datos.bloques]
    return TutorSalida.de(servicio.actualizar_disponibilidad(rol, tutor_id, bloques))


def _bloque(b: BloqueEntrada) -> BloqueDisponibilidad:
    return BloqueDisponibilidad(b.dia_semana, b.hora_inicio, b.hora_fin)
