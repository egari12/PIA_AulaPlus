"""Endpoints del contexto Inscripciones (paquete de pruebas del docente)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencias import servicio_inscripciones
from src.api.errores import RESPUESTAS_ERROR
from src.api.esquemas import (
    BeneficioSalida,
    CursoSalida,
    EstudianteSalida,
    EventoSalida,
    InscripcionEntrada,
    InscripcionSalida,
    MotivoEntrada,
)
from src.application.servicios_inscripciones import LineaSolicitada, ServicioInscripciones
from src.domain.inscripciones.especificaciones import BENEFICIO_REFERENCIA

router = APIRouter(tags=["Inscripciones (paquete CSV)"], responses=RESPUESTAS_ERROR)


@router.get("/estudiantes", response_model=list[EstudianteSalida], summary="Listar estudiantes (actores.csv)")
def listar_estudiantes(servicio: ServicioInscripciones = Depends(servicio_inscripciones)):
    return [EstudianteSalida.de(e) for e in servicio.uow.estudiantes.listar()]


@router.get("/cursos", response_model=list[CursoSalida], summary="Catálogo de cursos (catalogo.csv)")
def listar_cursos(servicio: ServicioInscripciones = Depends(servicio_inscripciones)):
    return [CursoSalida.de(c) for c in servicio.uow.cursos.listar()]


@router.get("/inscripciones", response_model=list[InscripcionSalida], summary="Listar inscripciones")
def listar(servicio: ServicioInscripciones = Depends(servicio_inscripciones)):
    return [InscripcionSalida.de(i) for i in servicio.listar()]


@router.post("/inscripciones", status_code=status.HTTP_201_CREATED, response_model=InscripcionSalida,
             summary="Crear inscripción en PREINSCRITA")
def crear(datos: InscripcionEntrada, servicio: ServicioInscripciones = Depends(servicio_inscripciones)):
    lineas = [LineaSolicitada(l.curso_id, l.cantidad) for l in datos.lineas]
    return InscripcionSalida.de(
        servicio.crear(datos.estudiante_id, lineas, datos.autorizada, datos.promocion_activa, datos.referencia)
    )


@router.get("/inscripciones/{inscripcion_id}", response_model=InscripcionSalida, summary="Consultar inscripción")
def obtener(inscripcion_id: str, servicio: ServicioInscripciones = Depends(servicio_inscripciones)):
    return InscripcionSalida.de(servicio.obtener(inscripcion_id))


@router.get("/inscripciones/{inscripcion_id}/eventos", response_model=list[EventoSalida],
            summary="Domain Events de la inscripción")
def eventos(inscripcion_id: str, servicio: ServicioInscripciones = Depends(servicio_inscripciones)):
    servicio.obtener(inscripcion_id)
    return [EventoSalida.de(e) for e in servicio.uow.inscripciones.eventos_de(inscripcion_id)]


@router.get("/inscripciones/{inscripcion_id}/beneficio", response_model=BeneficioSalida,
            summary="Evaluar beneficio: preferente AND total >= 1500 AND NOT promoción")
def beneficio(inscripcion_id: str, servicio: ServicioInscripciones = Depends(servicio_inscripciones)):
    r = servicio.evaluar_beneficio(inscripcion_id)
    return BeneficioSalida(inscripcion_id=inscripcion_id, aplica=r.aplica,
                           regla=BENEFICIO_REFERENCIA.describir(), incumplidas=list(r.incumplidas))


@router.post("/inscripciones/{inscripcion_id}/validar", response_model=InscripcionSalida,
             summary="PREINSCRITA -> VALIDADA (activo AND detalle AND autorización)")
def validar(inscripcion_id: str, servicio: ServicioInscripciones = Depends(servicio_inscripciones)):
    return InscripcionSalida.de(servicio.validar(inscripcion_id))


@router.post("/inscripciones/{inscripcion_id}/inscribir", response_model=InscripcionSalida,
             summary="VALIDADA -> INSCRITA (cursos habilitados AND cupo)")
def inscribir(inscripcion_id: str, servicio: ServicioInscripciones = Depends(servicio_inscripciones)):
    return InscripcionSalida.de(servicio.inscribir(inscripcion_id))


@router.post("/inscripciones/{inscripcion_id}/finalizar", response_model=InscripcionSalida,
             summary="INSCRITA -> FINALIZADA")
def finalizar(inscripcion_id: str, servicio: ServicioInscripciones = Depends(servicio_inscripciones)):
    return InscripcionSalida.de(servicio.finalizar(inscripcion_id))


@router.post("/inscripciones/{inscripcion_id}/cancelar", response_model=InscripcionSalida,
             summary="PREINSCRITA/VALIDADA -> CANCELADA")
def cancelar(inscripcion_id: str, datos: MotivoEntrada,
             servicio: ServicioInscripciones = Depends(servicio_inscripciones)):
    return InscripcionSalida.de(servicio.cancelar(inscripcion_id, datos.motivo))
