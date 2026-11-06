"""Carga los CSV del paquete del docente (sin modificarlos) y el catálogo de tutores del equipo.

Montos con Decimal desde el texto del CSV; banderas '1'/'0'; codificación UTF-8 con BOM.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path

from src.domain.comun import DatosInvalidos, Dinero
from src.domain.inscripciones.modelo import Curso, Estudiante, Inscripcion
from src.domain.sesiones.modelo import BloqueDisponibilidad, Modalidad, Tutor

DIRECTORIO_DATOS = Path(__file__).resolve().parents[2] / "datos"


@dataclass
class PaqueteDatos:
    estudiantes: dict[str, Estudiante] = field(default_factory=dict)
    cursos: dict[str, Curso] = field(default_factory=dict)
    inscripciones: dict[str, Inscripcion] = field(default_factory=dict)
    tutores: dict[str, Tutor] = field(default_factory=dict)


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return [{k.strip(): (v or "").strip() for k, v in fila.items()} for fila in csv.DictReader(archivo)]


def _bandera(valor: str, campo: str) -> bool:
    if valor not in {"0", "1"}:
        raise DatosInvalidos(f"{campo} debe ser 0 o 1, se recibió '{valor}'")
    return valor == "1"


def _bloques(texto: str) -> tuple[BloqueDisponibilidad, ...]:
    """Formato: '0@08:00-14:00;2@09:00-12:00' (0 = lunes)."""
    bloques = []
    for parte in filter(None, (p.strip() for p in texto.split(";"))):
        dia, horas = parte.split("@")
        inicio, fin = horas.split("-")
        bloques.append(
            BloqueDisponibilidad(int(dia), time.fromisoformat(inicio), time.fromisoformat(fin))
        )
    return tuple(bloques)


def cargar_tutores(ruta: Path) -> dict[str, Tutor]:
    tutores = {}
    for fila in leer_csv(ruta):
        tutor = Tutor(
            id=fila["tutor_id"],
            nombre=fila["nombre"],
            materias=frozenset(fila["materias"].split(";")),
            modalidades=frozenset(Modalidad(m) for m in fila["modalidades"].split(";")),
            zona=fila["zona"],
            bloques=_bloques(fila["disponibilidad"]),
        )
        tutores[tutor.id] = tutor
    return tutores


def cargar_paquete(directorio: Path = DIRECTORIO_DATOS) -> PaqueteDatos:
    paquete = PaqueteDatos()

    for fila in leer_csv(directorio / "actores.csv"):
        paquete.estudiantes[fila["actor_id"]] = Estudiante(
            id=fila["actor_id"],
            nombre=fila["nombre"],
            preferente=_bandera(fila["es_preferente"], "es_preferente"),
            activo=_bandera(fila["activo"], "activo"),
            ciudad=fila["ciudad"],
        )

    for fila in leer_csv(directorio / "catalogo.csv"):
        paquete.cursos[fila["recurso_id"]] = Curso(
            id=fila["recurso_id"],
            descripcion=fila["descripcion"],
            precio=Dinero.mxn(fila["precio_mxn"]),
            cupo=int(fila["capacidad_o_stock"]),
            habilitado=_bandera(fila["habilitado"], "habilitado"),
        )

    for fila in leer_csv(directorio / "operaciones.csv"):
        if fila["actor_id"] not in paquete.estudiantes:
            raise DatosInvalidos(f"{fila['operacion_id']}: actor {fila['actor_id']} inexistente")
        paquete.inscripciones[fila["operacion_id"]] = Inscripcion(
            id=fila["operacion_id"],
            estudiante_id=fila["actor_id"],
            fecha_solicitud=date.fromisoformat(fila["fecha_solicitud"]),
            promocion_activa=_bandera(fila["promocion_activa"], "promocion_activa"),
            autorizada=_bandera(fila["autorizado"], "autorizado"),
            referencia=fila["referencia"],
            estado=fila["estado_inicial"],
        )

    for fila in leer_csv(directorio / "detalle_operaciones.csv"):
        inscripcion = paquete.inscripciones.get(fila["operacion_id"])
        curso = paquete.cursos.get(fila["recurso_id"])
        if inscripcion is None or curso is None:
            raise DatosInvalidos(f"Detalle con llave foránea inválida: {fila}")
        inscripcion.agregar_linea(curso, int(fila["cantidad"]))

    ruta_tutores = directorio / "tutores.csv"
    if ruta_tutores.exists():
        paquete.tutores = cargar_tutores(ruta_tutores)
    return paquete


def poblar(uow, paquete: PaqueteDatos) -> None:
    """Copia el paquete a cualquier Unidad de Trabajo (memoria o SQL)."""
    # Se confirma por etapas para respetar las llaves foráneas en PostgreSQL.
    for estudiante in paquete.estudiantes.values():
        uow.estudiantes.guardar(estudiante)
    for curso in paquete.cursos.values():
        uow.cursos.guardar(curso)
    for tutor in paquete.tutores.values():
        uow.tutores.guardar(tutor)
    uow.commit()
    for inscripcion in paquete.inscripciones.values():
        uow.inscripciones.guardar(inscripcion)
    uow.commit()
