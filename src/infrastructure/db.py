"""Modelo relacional con SQLAlchemy 2.x. Funciona con PostgreSQL (Compose / despliegue) y SQLite (pruebas).

La URL se toma de la variable de entorno DATABASE_URL (12-Factor).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

DINERO = Numeric(12, 2)


class Base(DeclarativeBase):
    pass


class TutorRow(Base):
    __tablename__ = "tutores"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    materias: Mapped[list] = mapped_column(JSON)
    modalidades: Mapped[list] = mapped_column(JSON)
    zona: Mapped[str] = mapped_column(String(80))
    bloques: Mapped[list] = mapped_column(JSON)
    cancelaciones: Mapped[int] = mapped_column(Integer, default=0)
    penalizaciones: Mapped[int] = mapped_column(Integer, default=0)


class SesionRow(Base):
    __tablename__ = "sesiones"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    estudiante_id: Mapped[str] = mapped_column(String(40), index=True)
    tutor_id: Mapped[str] = mapped_column(ForeignKey("tutores.id"), index=True)
    materia: Mapped[str] = mapped_column(String(80))
    tema: Mapped[str] = mapped_column(String(160))
    modalidad: Mapped[str] = mapped_column(String(20))
    zona: Mapped[str | None] = mapped_column(String(80), nullable=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    precio: Mapped[Decimal] = mapped_column(DINERO)
    referencia_pago: Mapped[str] = mapped_column(String(60))
    estado: Mapped[str] = mapped_column(String(20), index=True)
    grabacion_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    grabacion_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grabacion_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    liquidacion_comision: Mapped[Decimal | None] = mapped_column(DINERO, nullable=True)
    liquidacion_tutor: Mapped[Decimal | None] = mapped_column(DINERO, nullable=True)
    monto_reembolso: Mapped[Decimal] = mapped_column(DINERO)
    tutor_penalizado: Mapped[bool] = mapped_column(Boolean, default=False)
    calificacion_tutor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calificacion_estudiante: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cambio_tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cambio_valor: Mapped[str | None] = mapped_column(String(60), nullable=True)


class PoliticaRow(Base):
    __tablename__ = "politicas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    precio: Mapped[Decimal] = mapped_column(DINERO)
    porcentaje_comision: Mapped[Decimal] = mapped_column(Numeric(5, 2))


class EstudianteRow(Base):
    __tablename__ = "estudiantes"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    preferente: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    ciudad: Mapped[str] = mapped_column(String(80), default="")


class CuentaRow(Base):
    """Tabla nueva (US-19, US-20): create_all la crea sola, también en una base que ya existía."""

    __tablename__ = "cuentas"
    correo: Mapped[str] = mapped_column(String(254), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(String(40), index=True)
    tipo: Mapped[str] = mapped_column(String(20))


class CursoRow(Base):
    __tablename__ = "cursos"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    descripcion: Mapped[str] = mapped_column(String(160))
    precio: Mapped[Decimal] = mapped_column(DINERO)
    cupo: Mapped[int] = mapped_column(Integer)
    habilitado: Mapped[bool] = mapped_column(Boolean, default=True)


class InscripcionRow(Base):
    __tablename__ = "inscripciones"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    estudiante_id: Mapped[str] = mapped_column(ForeignKey("estudiantes.id"), index=True)
    fecha_solicitud: Mapped[date] = mapped_column(Date)
    promocion_activa: Mapped[bool] = mapped_column(Boolean, default=False)
    autorizada: Mapped[bool] = mapped_column(Boolean, default=False)
    referencia: Mapped[str] = mapped_column(String(60), default="")
    estado: Mapped[str] = mapped_column(String(20), index=True)
    motivo_cancelacion: Mapped[str | None] = mapped_column(Text, nullable=True)


class LineaInscripcionRow(Base):
    __tablename__ = "lineas_inscripcion"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inscripcion_id: Mapped[str] = mapped_column(ForeignKey("inscripciones.id"), index=True)
    orden: Mapped[int] = mapped_column(Integer)
    curso_id: Mapped[str] = mapped_column(ForeignKey("cursos.id"))
    precio_unitario: Mapped[Decimal] = mapped_column(DINERO)
    cantidad: Mapped[int] = mapped_column(Integer)


class EventoRow(Base):
    __tablename__ = "eventos_dominio"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agregado_id: Mapped[str] = mapped_column(String(40), index=True)
    nombre: Mapped[str] = mapped_column(String(60))
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    datos: Mapped[dict] = mapped_column(JSON)


def crear_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        argumentos: dict = {"connect_args": {"check_same_thread": False}}
        if make_url(url).database in (None, "", ":memory:"):
            argumentos["poolclass"] = StaticPool  # una sola conexión compartida en memoria
        engine = create_engine(url, **argumentos)

        @event.listens_for(engine, "connect")
        def _activar_llaves_foraneas(conexion, _registro):  # SQLite no las valida por defecto
            cursor = conexion.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    else:
        engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine


def crear_fabrica_sesiones(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
