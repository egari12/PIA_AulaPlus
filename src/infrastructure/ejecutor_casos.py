"""Ejecuta casos_prueba.csv y transiciones_prueba.csv del paquete del docente contra el dominio.

Cada caso parte de datos recién cargados, para que un caso no afecte a otro. Los CSV
originales no se modifican: se genera una copia con resultado_alumno y evidencia.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from src.application.servicios_inscripciones import ServicioInscripciones
from src.domain.comun import ErrorDominio, ahora_utc
from src.domain.inscripciones.especificaciones import PUEDE_PROCESARSE, ContextoInscripcion
from src.infrastructure.cargador_csv import DIRECTORIO_DATOS, cargar_paquete, leer_csv, poblar
from src.infrastructure.externos import RelojFijo
from src.infrastructure.memoria import UnidadDeTrabajoMemoria

MOTIVO_PRUEBA = "Cancelación solicitada en caso de prueba"

# Acción del CSV -> pasos que se ejecutan en el dominio
PASOS_POR_ACCION: dict[str, list[str]] = {
    "aprobar": ["validar"],
    "cancelar": ["cancelar"],
    "repetir_aprobacion": ["validar", "validar"],
    "saltar_estado": ["inscribir"],  # PREINSCRITA -> INSCRITA sin pasar por VALIDADA
    "completar": ["validar", "inscribir", "finalizar"],
}

HTTP_POR_EXCEPCION = {
    "DatosInvalidos": 422,
    "ReglaNegocioViolada": 422,
    "TransicionInvalida": 409,
    "RecursoNoDisponible": 409,
    "PermisoDenegado": 403,
    "NoEncontrado": 404,
}


@dataclass
class Entorno:
    uow: UnidadDeTrabajoMemoria
    servicio: ServicioInscripciones


def entorno_fresco(directorio: Path = DIRECTORIO_DATOS) -> Entorno:
    uow = UnidadDeTrabajoMemoria()
    poblar(uow, cargar_paquete(directorio))
    return Entorno(uow, ServicioInscripciones(uow, RelojFijo(ahora_utc())))


# --------------------------------------------------------------------------- #
def ejecutar_caso(fila: dict[str, str], directorio: Path = DIRECTORIO_DATOS) -> dict[str, str]:
    entorno = entorno_fresco(directorio)
    inscripcion = entorno.servicio.obtener(fila["operacion_id"])
    estudiante = entorno.uow.estudiantes.obtener(inscripcion.estudiante_id)
    base = f"total={inscripcion.total.monto}; lineas={len(inscripcion.lineas)}"

    if fila["tipo_prueba"] == "validar_operacion":
        fallas = PUEDE_PROCESARSE.incumplidas(ContextoInscripcion(inscripcion, estudiante))
        resultado = "CUMPLE" if not fallas else "NO CUMPLE"
    elif fila["tipo_prueba"] == "evaluar_beneficio":
        fallas = list(inscripcion.evaluar_beneficio(estudiante).incumplidas)
        resultado = "APLICA" if not fallas else "NO APLICA"
    else:
        return {**fila, "resultado_alumno": "TIPO DESCONOCIDO", "evidencia": fila["tipo_prueba"]}

    evidencia = base + ("; falla: " + ", ".join(fallas) if fallas else "; todas las condiciones se cumplen")
    return {**fila, "resultado_alumno": resultado, "evidencia": evidencia}


def ejecutar_transicion(fila: dict[str, str], directorio: Path = DIRECTORIO_DATOS) -> dict[str, str]:
    entorno = entorno_fresco(directorio)
    servicio = entorno.servicio
    operacion = fila["operacion_id"]
    pasos = PASOS_POR_ACCION.get(fila["accion_sugerida"])
    if pasos is None:
        return {**fila, "resultado_alumno": "ACCIÓN DESCONOCIDA", "estado_final": "", "eventos": "",
                "excepcion": "", "http_equivalente": ""}

    excepcion, http = "", "200"
    for paso in pasos:
        try:
            if paso == "cancelar":
                servicio.cancelar(operacion, MOTIVO_PRUEBA)
            else:
                getattr(servicio, paso)(operacion)
        except ErrorDominio as error:
            nombre = type(error).__name__
            excepcion = f"{nombre} en '{paso}': {error}"
            http = str(HTTP_POR_EXCEPCION.get(nombre, 400))
            break

    final = servicio.obtener(operacion)
    eventos = [e.nombre for e in entorno.uow.inscripciones.eventos_de(operacion)]
    resultado = "OK" if not excepcion else "RECHAZADA"
    return {
        **fila,
        "resultado_alumno": resultado,
        "estado_final": final.estado.value,
        "eventos": " > ".join(eventos) or "(ninguno)",
        "excepcion": excepcion,
        "http_equivalente": http,
    }


# --------------------------------------------------------------------------- #
def _escribir(ruta: Path, filas: list[dict[str, str]]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)


def ejecutar_todo(directorio: Path = DIRECTORIO_DATOS, salida: Path | None = None) -> tuple[list, list]:
    casos = [ejecutar_caso(f, directorio) for f in leer_csv(directorio / "casos_prueba.csv")]
    transiciones = [
        ejecutar_transicion(f, directorio) for f in leer_csv(directorio / "transiciones_prueba.csv")
    ]
    if salida is not None:
        _escribir(salida / "resultados_casos_prueba.csv", casos)
        _escribir(salida / "resultados_transiciones.csv", transiciones)
    return casos, transiciones
