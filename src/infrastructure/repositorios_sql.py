"""Repositorios SQLAlchemy: traducen filas <-> agregados del dominio y guardan los Domain Events."""

from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as SessionSQL
from sqlalchemy.orm import sessionmaker

from src.domain.comun import Dinero, EventoDominio
from src.domain.inscripciones.modelo import (
    Curso,
    Estudiante,
    Inscripcion,
    LineaInscripcion,
)
from src.domain.sesiones.modelo import (
    BloqueDisponibilidad,
    CambioPendiente,
    Grabacion,
    Liquidacion,
    PoliticaTarifas,
    Sesion,
    TipoCambio,
    Tutor,
)
from src.infrastructure.db import (
    CursoRow,
    EstudianteRow,
    EventoRow,
    InscripcionRow,
    LineaInscripcionRow,
    PoliticaRow,
    SesionRow,
    TutorRow,
)


def _utc(momento: datetime | None) -> datetime | None:
    """SQLite devuelve fechas sin zona; se asume que se guardaron en UTC."""
    if momento is None:
        return None
    if momento.tzinfo is None:
        return momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


def _dinero(valor) -> Dinero:
    return Dinero(Decimal(str(valor)))


def _guardar_eventos(sesion_sql: SessionSQL, agregado) -> None:
    for evento in agregado.extraer_eventos():
        sesion_sql.add(
            EventoRow(
                agregado_id=evento.agregado_id,
                nombre=evento.nombre,
                ocurrido_en=evento.ocurrido_en.astimezone(timezone.utc),
                datos=evento.datos,
            )
        )


def _eventos_de(sesion_sql: SessionSQL, agregado_id: str) -> list[EventoDominio]:
    filas = sesion_sql.scalars(
        select(EventoRow).where(EventoRow.agregado_id == agregado_id).order_by(EventoRow.id)
    )
    return [EventoDominio(f.nombre, f.agregado_id, _utc(f.ocurrido_en), dict(f.datos)) for f in filas]


# --------------------------------------------------------------------------- #
class RepositorioTutoresSQL:
    def __init__(self, sesion_sql: SessionSQL):
        self.s = sesion_sql

    @staticmethod
    def _a_dominio(f: TutorRow) -> Tutor:
        return Tutor(
            id=f.id,
            nombre=f.nombre,
            materias=frozenset(f.materias),
            modalidades=frozenset(f.modalidades),
            zona=f.zona,
            bloques=tuple(
                BloqueDisponibilidad(b["dia"], time.fromisoformat(b["inicio"]), time.fromisoformat(b["fin"]))
                for b in f.bloques
            ),
            cancelaciones=f.cancelaciones,
            penalizaciones=f.penalizaciones,
        )

    def obtener(self, tutor_id: str) -> Tutor | None:
        fila = self.s.get(TutorRow, tutor_id)
        return self._a_dominio(fila) if fila else None

    def listar(self) -> list[Tutor]:
        return [self._a_dominio(f) for f in self.s.scalars(select(TutorRow).order_by(TutorRow.id))]

    def guardar(self, tutor: Tutor) -> None:
        self.s.merge(
            TutorRow(
                id=tutor.id,
                nombre=tutor.nombre,
                materias=sorted(tutor.materias),
                modalidades=sorted(m.value for m in tutor.modalidades),
                zona=tutor.zona,
                bloques=[
                    {"dia": b.dia_semana, "inicio": b.hora_inicio.isoformat(), "fin": b.hora_fin.isoformat()}
                    for b in tutor.bloques
                ],
                cancelaciones=tutor.cancelaciones,
                penalizaciones=tutor.penalizaciones,
            )
        )
        _guardar_eventos(self.s, tutor)

    def eventos_de(self, agregado_id: str) -> list[EventoDominio]:
        return _eventos_de(self.s, agregado_id)


# --------------------------------------------------------------------------- #
class RepositorioSesionesSQL:
    def __init__(self, sesion_sql: SessionSQL):
        self.s = sesion_sql

    @staticmethod
    def _a_dominio(f: SesionRow) -> Sesion:
        precio = _dinero(f.precio)
        grabacion = None
        if f.grabacion_url:
            grabacion = Grabacion(f.grabacion_url, _utc(f.grabacion_inicio), _utc(f.grabacion_fin))
        liquidacion = None
        if f.liquidacion_tutor is not None:
            liquidacion = Liquidacion(precio, _dinero(f.liquidacion_comision), _dinero(f.liquidacion_tutor))
        cambio = None
        if f.cambio_tipo:
            cambio = CambioPendiente(TipoCambio(f.cambio_tipo), f.cambio_valor or "")
        return Sesion(
            id=f.id,
            estudiante_id=f.estudiante_id,
            tutor_id=f.tutor_id,
            materia=f.materia,
            tema=f.tema,
            modalidad=f.modalidad,
            inicio=_utc(f.inicio),
            precio=precio,
            referencia_pago=f.referencia_pago,
            zona=f.zona,
            estado=f.estado,
            grabacion=grabacion,
            liquidacion=liquidacion,
            monto_reembolso=_dinero(f.monto_reembolso),
            tutor_penalizado=f.tutor_penalizado,
            calificacion_tutor=f.calificacion_tutor,
            calificacion_estudiante=f.calificacion_estudiante,
            cambio_pendiente=cambio,
        )

    def obtener(self, sesion_id: str) -> Sesion | None:
        fila = self.s.get(SesionRow, sesion_id)
        return self._a_dominio(fila) if fila else None

    def listar(self) -> list[Sesion]:
        filas = self.s.scalars(select(SesionRow).order_by(SesionRow.inicio, SesionRow.id))
        return [self._a_dominio(f) for f in filas]

    def guardar(self, s: Sesion) -> None:
        g, liq, cambio = s.grabacion, s.liquidacion, s.cambio_pendiente
        self.s.merge(
            SesionRow(
                id=s.id,
                estudiante_id=s.estudiante_id,
                tutor_id=s.tutor_id,
                materia=s.materia,
                tema=s.tema,
                modalidad=s.modalidad.value,
                zona=s.zona,
                inicio=s.inicio.astimezone(timezone.utc),
                precio=s.precio.monto,
                referencia_pago=s.referencia_pago,
                estado=s.estado.value,
                grabacion_url=g.url if g else None,
                grabacion_inicio=g.inicio.astimezone(timezone.utc) if g else None,
                grabacion_fin=g.fin.astimezone(timezone.utc) if g else None,
                liquidacion_comision=liq.comision.monto if liq else None,
                liquidacion_tutor=liq.monto_tutor.monto if liq else None,
                monto_reembolso=s.monto_reembolso.monto,
                tutor_penalizado=s.tutor_penalizado,
                calificacion_tutor=s.calificacion_tutor,
                calificacion_estudiante=s.calificacion_estudiante,
                cambio_tipo=cambio.tipo.value if cambio else None,
                cambio_valor=cambio.valor if cambio else None,
            )
        )
        _guardar_eventos(self.s, s)

    def eventos_de(self, agregado_id: str) -> list[EventoDominio]:
        return _eventos_de(self.s, agregado_id)


# --------------------------------------------------------------------------- #
class RepositorioPoliticasSQL:
    def __init__(self, sesion_sql: SessionSQL):
        self.s = sesion_sql

    def obtener(self) -> PoliticaTarifas:
        fila = self.s.get(PoliticaRow, 1)
        if fila is None:
            return PoliticaTarifas()
        return PoliticaTarifas(_dinero(fila.precio), Decimal(str(fila.porcentaje_comision)))

    def guardar(self, politica: PoliticaTarifas) -> None:
        self.s.merge(
            PoliticaRow(id=1, precio=politica.precio.monto, porcentaje_comision=politica.porcentaje_comision)
        )


# --------------------------------------------------------------------------- #
class RepositorioEstudiantesSQL:
    def __init__(self, sesion_sql: SessionSQL):
        self.s = sesion_sql

    @staticmethod
    def _a_dominio(f: EstudianteRow) -> Estudiante:
        return Estudiante(f.id, f.nombre, f.preferente, f.activo, f.ciudad)

    def obtener(self, estudiante_id: str) -> Estudiante | None:
        fila = self.s.get(EstudianteRow, estudiante_id)
        return self._a_dominio(fila) if fila else None

    def listar(self) -> list[Estudiante]:
        return [self._a_dominio(f) for f in self.s.scalars(select(EstudianteRow).order_by(EstudianteRow.id))]

    def guardar(self, e: Estudiante) -> None:
        self.s.merge(EstudianteRow(id=e.id, nombre=e.nombre, preferente=e.preferente, activo=e.activo, ciudad=e.ciudad))


class RepositorioCursosSQL:
    def __init__(self, sesion_sql: SessionSQL):
        self.s = sesion_sql

    @staticmethod
    def _a_dominio(f: CursoRow) -> Curso:
        return Curso(f.id, f.descripcion, _dinero(f.precio), f.cupo, f.habilitado)

    def obtener(self, curso_id: str) -> Curso | None:
        fila = self.s.get(CursoRow, curso_id)
        return self._a_dominio(fila) if fila else None

    def listar(self) -> list[Curso]:
        return [self._a_dominio(f) for f in self.s.scalars(select(CursoRow).order_by(CursoRow.id))]

    def guardar(self, c: Curso) -> None:
        self.s.merge(
            CursoRow(id=c.id, descripcion=c.descripcion, precio=c.precio.monto, cupo=c.cupo, habilitado=c.habilitado)
        )


class RepositorioInscripcionesSQL:
    def __init__(self, sesion_sql: SessionSQL):
        self.s = sesion_sql

    def _a_dominio(self, f: InscripcionRow) -> Inscripcion:
        lineas = self.s.scalars(
            select(LineaInscripcionRow)
            .where(LineaInscripcionRow.inscripcion_id == f.id)
            .order_by(LineaInscripcionRow.orden)
        )
        return Inscripcion(
            id=f.id,
            estudiante_id=f.estudiante_id,
            fecha_solicitud=f.fecha_solicitud,
            promocion_activa=f.promocion_activa,
            autorizada=f.autorizada,
            referencia=f.referencia,
            estado=f.estado,
            lineas=[LineaInscripcion(l.curso_id, _dinero(l.precio_unitario), l.cantidad) for l in lineas],
            motivo_cancelacion=f.motivo_cancelacion,
        )

    def obtener(self, inscripcion_id: str) -> Inscripcion | None:
        fila = self.s.get(InscripcionRow, inscripcion_id)
        return self._a_dominio(fila) if fila else None

    def listar(self) -> list[Inscripcion]:
        return [self._a_dominio(f) for f in self.s.scalars(select(InscripcionRow).order_by(InscripcionRow.id))]

    def guardar(self, i: Inscripcion) -> None:
        self.s.merge(
            InscripcionRow(
                id=i.id,
                estudiante_id=i.estudiante_id,
                fecha_solicitud=i.fecha_solicitud,
                promocion_activa=i.promocion_activa,
                autorizada=i.autorizada,
                referencia=i.referencia,
                estado=i.estado.value,
                motivo_cancelacion=i.motivo_cancelacion,
            )
        )
        self.s.flush()  # la fila padre debe existir antes de insertar sus líneas (FK en PostgreSQL)
        self.s.execute(delete(LineaInscripcionRow).where(LineaInscripcionRow.inscripcion_id == i.id))
        for orden, linea in enumerate(i.lineas):
            self.s.add(
                LineaInscripcionRow(
                    inscripcion_id=i.id,
                    orden=orden,
                    curso_id=linea.curso_id,
                    precio_unitario=linea.precio_unitario.monto,
                    cantidad=linea.cantidad,
                )
            )
        _guardar_eventos(self.s, i)

    def eventos_de(self, agregado_id: str) -> list[EventoDominio]:
        return _eventos_de(self.s, agregado_id)


# --------------------------------------------------------------------------- #
class UnidadDeTrabajoSQL:
    """Una sesión de SQLAlchemy por petición; commit/rollback explícitos."""

    def __init__(self, fabrica: sessionmaker):
        self.sesion_sql: SessionSQL = fabrica()
        self.tutores = RepositorioTutoresSQL(self.sesion_sql)
        self.sesiones = RepositorioSesionesSQL(self.sesion_sql)
        self.politicas = RepositorioPoliticasSQL(self.sesion_sql)
        self.estudiantes = RepositorioEstudiantesSQL(self.sesion_sql)
        self.cursos = RepositorioCursosSQL(self.sesion_sql)
        self.inscripciones = RepositorioInscripcionesSQL(self.sesion_sql)

    def commit(self) -> None:
        self.sesion_sql.commit()

    def rollback(self) -> None:
        self.sesion_sql.rollback()

    def cerrar(self) -> None:
        self.sesion_sql.close()

    def esta_vacia(self) -> bool:
        return self.sesion_sql.scalar(select(EstudianteRow.id).limit(1)) is None
