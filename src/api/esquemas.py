"""Contratos de entrada/salida de la API (Pydantic). Aparecen en Swagger / OpenAPI."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field

from src.domain.comun import EventoDominio
from src.domain.inscripciones.modelo import Curso, Estudiante, Inscripcion
from src.domain.sesiones.modelo import Modalidad, Sesion, Solicitante, TipoCambio, Tutor


class ErrorSalida(BaseModel):
    error: str
    detalle: str


class EventoSalida(BaseModel):
    nombre: str
    ocurrido_en: datetime
    datos: dict

    @classmethod
    def de(cls, e: EventoDominio) -> EventoSalida:
        return cls(nombre=e.nombre, ocurrido_en=e.ocurrido_en, datos=e.datos)


# --------------------------------------------------------------------------- #
# Sesiones
# --------------------------------------------------------------------------- #
class ReservaEntrada(BaseModel):
    estudiante_id: str = Field(examples=["AUL-C001"])
    materia: str = Field(examples=["Python"])
    tema: str = Field(examples=["Listas y diccionarios"])
    modalidad: Modalidad = Modalidad.EN_LINEA
    inicio: datetime = Field(description="ISO 8601 con zona horaria", examples=["2026-11-16T10:00:00-06:00"])
    zona: str | None = Field(default=None, examples=["Monterrey"])


class GrabacionEntrada(BaseModel):
    url: str = Field(examples=["https://grabaciones.aulaplus.mx/ses-001.mp4"])
    inicio: datetime
    fin: datetime


class CancelacionEntrada(BaseModel):
    solicitante: Solicitante
    motivo: str = Field(examples=["El estudiante tiene un examen"])
    justificada: bool = Field(default=False, description="Emergencia médica/legal con justificante (RN-09)")


class CalificacionEntrada(BaseModel):
    puntuacion: int = Field(ge=1, le=5)


class CambioEntrada(BaseModel):
    tipo: TipoCambio
    valor: str = Field(description="Nueva fecha ISO 8601 o nueva modalidad", examples=["EN_LINEA"])


class SesionSalida(BaseModel):
    id: str
    estudiante_id: str
    tutor_id: str
    materia: str
    tema: str
    modalidad: Modalidad
    zona: str | None
    inicio: datetime
    fin: datetime
    estado: str
    estado_pago: str
    precio: Decimal
    monto_reembolso: Decimal
    porcentaje_grabado: Decimal | None
    monto_tutor: Decimal | None
    comision: Decimal | None
    tutor_penalizado: bool
    calificacion_tutor: int | None
    calificacion_estudiante: int | None
    cambio_pendiente: dict | None
    acciones_permitidas: list[str]

    @classmethod
    def de(cls, s: Sesion) -> SesionSalida:
        from src.domain.sesiones.modelo import MAQUINA_SESION

        return cls(
            id=s.id,
            estudiante_id=s.estudiante_id,
            tutor_id=s.tutor_id,
            materia=s.materia,
            tema=s.tema,
            modalidad=s.modalidad,
            zona=s.zona,
            inicio=s.inicio,
            fin=s.fin,
            estado=s.estado.value,
            estado_pago=s.estado_pago,
            precio=s.precio.monto,
            monto_reembolso=s.monto_reembolso.monto,
            porcentaje_grabado=s.grabacion.porcentaje_grabado if s.grabacion else None,
            monto_tutor=s.liquidacion.monto_tutor.monto if s.liquidacion else None,
            comision=s.liquidacion.comision.monto if s.liquidacion else None,
            tutor_penalizado=s.tutor_penalizado,
            calificacion_tutor=s.calificacion_tutor,
            calificacion_estudiante=s.calificacion_estudiante,
            cambio_pendiente=(
                {"tipo": s.cambio_pendiente.tipo.value, "valor": s.cambio_pendiente.valor}
                if s.cambio_pendiente
                else None
            ),
            acciones_permitidas=MAQUINA_SESION.acciones_desde(s.estado),
        )


class LiquidacionSalida(BaseModel):
    sesion_id: str
    estado_pago: str
    monto_tutor: Decimal
    comision: Decimal
    referencia: str | None
    mensaje: str


# --------------------------------------------------------------------------- #
# Tutores y administración
# --------------------------------------------------------------------------- #
class BloqueEntrada(BaseModel):
    dia_semana: int = Field(ge=0, le=6, description="0 = lunes ... 6 = domingo")
    hora_inicio: time = Field(examples=["08:00"])
    hora_fin: time = Field(examples=["14:00"])


class DisponibilidadEntrada(BaseModel):
    bloques: list[BloqueEntrada]


class TutorSalida(BaseModel):
    id: str
    nombre: str
    materias: list[str]
    modalidades: list[str]
    zona: str
    bloques: list[BloqueEntrada]
    cancelaciones: int
    penalizaciones: int
    estado_penalizacion: str

    @classmethod
    def de(cls, t: Tutor) -> TutorSalida:
        return cls(
            id=t.id,
            nombre=t.nombre,
            materias=sorted(t.materias),
            modalidades=sorted(m.value for m in t.modalidades),
            zona=t.zona,
            bloques=[
                BloqueEntrada(dia_semana=b.dia_semana, hora_inicio=b.hora_inicio, hora_fin=b.hora_fin)
                for b in t.bloques
            ],
            cancelaciones=t.cancelaciones,
            penalizaciones=t.penalizaciones,
            estado_penalizacion=t.estado_penalizacion,
        )


class ComisionEntrada(BaseModel):
    porcentaje: Decimal = Field(ge=0, le=100, examples=["25"])


class PoliticaSalida(BaseModel):
    precio: Decimal
    porcentaje_comision: Decimal


class ReporteSesionesSalida(BaseModel):
    desde: datetime
    hasta: datetime
    por_estado: dict[str, int]
    por_estado_pago: dict[str, int]
    total_cobrado: Decimal
    total_comisiones: Decimal
    total_reembolsado: Decimal


class CancelacionesTutorSalida(BaseModel):
    tutor_id: str
    nombre: str
    cancelaciones: int
    penalizaciones: int
    estado_penalizacion: str


# --------------------------------------------------------------------------- #
# Inscripciones (paquete del docente)
# --------------------------------------------------------------------------- #
class EstudianteSalida(BaseModel):
    id: str
    nombre: str
    preferente: bool
    activo: bool
    ciudad: str

    @classmethod
    def de(cls, e: Estudiante) -> EstudianteSalida:
        return cls(id=e.id, nombre=e.nombre, preferente=e.preferente, activo=e.activo, ciudad=e.ciudad)


class RegistroEntrada(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120, examples=["Ana López"])
    correo: str = Field(..., max_length=254, examples=["ana@correo.com"])
    ciudad: str = Field(..., min_length=2, max_length=80, examples=["Monterrey"])


class AccesoEntrada(BaseModel):
    correo: str = Field(..., max_length=254, examples=["ana@correo.com"])


class CuentaSalida(BaseModel):
    id: str
    nombre: str
    ciudad: str
    correo: str

    @classmethod
    def de(cls, registro) -> CuentaSalida:
        e = registro.estudiante
        return cls(id=e.id, nombre=e.nombre, ciudad=e.ciudad, correo=registro.correo)


class CursoSalida(BaseModel):
    id: str
    descripcion: str
    precio: Decimal
    cupo: int
    habilitado: bool

    @classmethod
    def de(cls, c: Curso) -> CursoSalida:
        return cls(id=c.id, descripcion=c.descripcion, precio=c.precio.monto, cupo=c.cupo, habilitado=c.habilitado)


class LineaEntrada(BaseModel):
    curso_id: str = Field(examples=["AUL-P001"])
    cantidad: int = Field(gt=0, examples=[2])


class InscripcionEntrada(BaseModel):
    estudiante_id: str = Field(examples=["AUL-C005"])
    lineas: list[LineaEntrada]
    autorizada: bool = True
    promocion_activa: bool = False
    referencia: str = ""


class MotivoEntrada(BaseModel):
    motivo: str = Field(examples=["El estudiante se dio de baja"])


class LineaSalida(BaseModel):
    curso_id: str
    precio_unitario: Decimal
    cantidad: int
    subtotal: Decimal


class InscripcionSalida(BaseModel):
    id: str
    estudiante_id: str
    fecha_solicitud: date
    estado: str
    promocion_activa: bool
    autorizada: bool
    referencia: str
    unidades: int
    total: Decimal
    lineas: list[LineaSalida]
    motivo_cancelacion: str | None
    acciones_permitidas: list[str]

    @classmethod
    def de(cls, i: Inscripcion) -> InscripcionSalida:
        from src.domain.inscripciones.modelo import MAQUINA_INSCRIPCION

        return cls(
            id=i.id,
            estudiante_id=i.estudiante_id,
            fecha_solicitud=i.fecha_solicitud,
            estado=i.estado.value,
            promocion_activa=i.promocion_activa,
            autorizada=i.autorizada,
            referencia=i.referencia,
            unidades=i.unidades,
            total=i.total.monto,
            lineas=[
                LineaSalida(
                    curso_id=l.curso_id,
                    precio_unitario=l.precio_unitario.monto,
                    cantidad=l.cantidad,
                    subtotal=l.subtotal.monto,
                )
                for l in i.lineas
            ],
            motivo_cancelacion=i.motivo_cancelacion,
            acciones_permitidas=MAQUINA_INSCRIPCION.acciones_desde(i.estado),
        )


class BeneficioSalida(BaseModel):
    inscripcion_id: str
    aplica: bool
    regla: str
    incumplidas: list[str]
