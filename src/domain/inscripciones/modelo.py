"""Contexto Inscripciones a cursos de asesoría.

Se agregó para ejecutar el paquete de pruebas del docente (CSV): un estudiante se
preinscribe a uno o más cursos del catálogo; cada línea indica cuántas sesiones
del curso toma. Flujo: PREINSCRITA -> VALIDADA -> INSCRITA -> FINALIZADA, y
PREINSCRITA/VALIDADA -> CANCELADA. Ver docs/architecture/ADR-006.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from src.domain.comun import (
    AgregadoRaiz,
    DatosInvalidos,
    Dinero,
    RecursoNoDisponible,
    TransicionInvalida,
)
from src.domain.maquina_estados import MaquinaEstados


class EstadoInscripcion(str, Enum):
    PREINSCRITA = "PREINSCRITA"
    VALIDADA = "VALIDADA"
    INSCRITA = "INSCRITA"
    FINALIZADA = "FINALIZADA"
    CANCELADA = "CANCELADA"


MAQUINA_INSCRIPCION: MaquinaEstados[EstadoInscripcion] = MaquinaEstados(
    "Inscripcion",
    {
        (EstadoInscripcion.PREINSCRITA, "validar"): EstadoInscripcion.VALIDADA,
        (EstadoInscripcion.VALIDADA, "inscribir"): EstadoInscripcion.INSCRITA,
        (EstadoInscripcion.INSCRITA, "finalizar"): EstadoInscripcion.FINALIZADA,
        (EstadoInscripcion.PREINSCRITA, "cancelar"): EstadoInscripcion.CANCELADA,
        (EstadoInscripcion.VALIDADA, "cancelar"): EstadoInscripcion.CANCELADA,
    },
)


@dataclass(frozen=True)
class Estudiante:
    id: str
    nombre: str
    preferente: bool = False
    activo: bool = True
    ciudad: str = ""


@dataclass
class Curso:
    """Recurso del catálogo: precio por sesión y cupo (sesiones disponibles)."""

    id: str
    descripcion: str
    precio: Dinero
    cupo: int
    habilitado: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.cupo, bool) or not isinstance(self.cupo, int) or self.cupo < 0:
            raise DatosInvalidos("El cupo debe ser un entero no negativo")

    def reservar_cupo(self, cantidad: int) -> None:
        if not self.habilitado:
            raise RecursoNoDisponible(f"El curso {self.id} no está habilitado")
        if cantidad > self.cupo:
            raise RecursoNoDisponible(
                f"Cupo insuficiente en {self.id}: solicitadas {cantidad}, disponibles {self.cupo}"
            )
        self.cupo -= cantidad


@dataclass(frozen=True)
class LineaInscripcion:
    """Value Object: el subtotal se calcula, no se captura."""

    curso_id: str
    precio_unitario: Dinero
    cantidad: int

    def __post_init__(self) -> None:
        if not isinstance(self.curso_id, str) or not self.curso_id.strip():
            raise DatosInvalidos("La línea requiere un curso")
        if isinstance(self.cantidad, bool) or not isinstance(self.cantidad, int):
            raise DatosInvalidos("La cantidad debe ser un entero")
        if self.cantidad <= 0:
            raise DatosInvalidos("La cantidad debe ser mayor a cero")

    @property
    def subtotal(self) -> Dinero:
        return self.precio_unitario * self.cantidad


@dataclass(frozen=True)
class ResultadoBeneficio:
    aplica: bool
    incumplidas: tuple[str, ...] = ()


@dataclass
class Inscripcion(AgregadoRaiz):
    id: str
    estudiante_id: str
    fecha_solicitud: date
    promocion_activa: bool = False
    autorizada: bool = False
    referencia: str = ""
    estado: EstadoInscripcion = EstadoInscripcion.PREINSCRITA
    lineas: list[LineaInscripcion] = field(default_factory=list)
    motivo_cancelacion: str | None = None

    def __post_init__(self) -> None:
        self.estado = EstadoInscripcion(self.estado)

    # -- consultas ---------------------------------------------------------- #
    @property
    def total(self) -> Dinero:
        total = Dinero.cero()
        for linea in self.lineas:
            total = total + linea.subtotal
        return total

    @property
    def unidades(self) -> int:
        return sum(linea.cantidad for linea in self.lineas)

    def cantidades_por_curso(self) -> Counter[str]:
        conteo: Counter[str] = Counter()
        for linea in self.lineas:
            conteo[linea.curso_id] += linea.cantidad
        return conteo

    def evaluar_beneficio(self, estudiante: Estudiante | None) -> ResultadoBeneficio:
        from src.domain.inscripciones.especificaciones import (
            BENEFICIO_REFERENCIA,
            ContextoInscripcion,
        )

        contexto = ContextoInscripcion(self, estudiante)
        fallas = BENEFICIO_REFERENCIA.incumplidas(contexto)
        return ResultadoBeneficio(not fallas, tuple(fallas))

    # -- comandos ----------------------------------------------------------- #
    def agregar_linea(self, curso: Curso, cantidad: int) -> None:
        if self.estado is not EstadoInscripcion.PREINSCRITA:
            raise TransicionInvalida("Solo una inscripción PREINSCRITA admite cursos")
        self.lineas.append(LineaInscripcion(curso.id, curso.precio, cantidad))

    def validar(self, estudiante: Estudiante | None, ahora: datetime | None = None) -> None:
        from src.domain.inscripciones.especificaciones import (
            PUEDE_PROCESARSE,
            ContextoInscripcion,
        )

        destino = MAQUINA_INSCRIPCION.destino(self.estado, "validar")
        fallas = PUEDE_PROCESARSE.incumplidas(ContextoInscripcion(self, estudiante))
        if fallas:
            raise DatosInvalidos("No puede procesarse: falla " + ", ".join(fallas))
        self.estado = destino
        self._registrar("InscripcionValidada", ahora, total=str(self.total.monto))

    def inscribir(self, cursos: Mapping[str, Curso], ahora: datetime | None = None) -> None:
        from src.domain.inscripciones.especificaciones import (
            PUEDE_INSCRIBIRSE,
            ContextoInscripcion,
        )

        destino = MAQUINA_INSCRIPCION.destino(self.estado, "inscribir")
        fallas = PUEDE_INSCRIBIRSE.incumplidas(ContextoInscripcion(self, None, cursos))
        if fallas:
            raise RecursoNoDisponible("No puede inscribirse: falla " + ", ".join(fallas))
        for curso_id, cantidad in self.cantidades_por_curso().items():
            cursos[curso_id].reservar_cupo(cantidad)
        self.estado = destino
        self._registrar("InscripcionConfirmada", ahora, unidades=self.unidades)

    def finalizar(self, ahora: datetime | None = None) -> None:
        self.estado = MAQUINA_INSCRIPCION.destino(self.estado, "finalizar")
        self._registrar("InscripcionFinalizada", ahora)

    def cancelar(self, motivo: str, ahora: datetime | None = None) -> None:
        destino = MAQUINA_INSCRIPCION.destino(self.estado, "cancelar")
        if not isinstance(motivo, str) or not motivo.strip():
            raise DatosInvalidos("La cancelación requiere un motivo")
        self.estado = destino
        self.motivo_cancelacion = motivo.strip()
        self._registrar("InscripcionCancelada", ahora, motivo=self.motivo_cancelacion)
