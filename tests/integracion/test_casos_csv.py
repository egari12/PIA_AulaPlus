"""Integración: paquete completo del docente (120 casos + 20 transiciones) contra el dominio.

Los oráculos se recalculan aquí leyendo los CSV directamente, sin usar el código del dominio.
"""

import csv
from collections import defaultdict
from decimal import Decimal

import pytest

from src.infrastructure.cargador_csv import DIRECTORIO_DATOS
from src.infrastructure.ejecutor_casos import ejecutar_todo, ejecutar_transicion


def _leer(nombre):
    with (DIRECTORIO_DATOS / nombre).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def oraculo():
    actores = {a["actor_id"]: a for a in _leer("actores.csv")}
    precios = {c["recurso_id"]: Decimal(c["precio_mxn"]) for c in _leer("catalogo.csv")}
    totales, lineas = defaultdict(Decimal), defaultdict(int)
    for d in _leer("detalle_operaciones.csv"):
        totales[d["operacion_id"]] += precios[d["recurso_id"]] * int(d["cantidad"])
        lineas[d["operacion_id"]] += 1
    esperado = {}
    for o in _leer("operaciones.csv"):
        actor = actores[o["actor_id"]]
        procesa = actor["activo"] == "1" and lineas[o["operacion_id"]] > 0 and o["autorizado"] == "1"
        beneficio = (actor["es_preferente"] == "1" and totales[o["operacion_id"]] >= 1500
                     and o["promocion_activa"] == "0")
        esperado[o["operacion_id"]] = (procesa, beneficio)
    return esperado


@pytest.fixture(scope="module")
def resultados(tmp_path_factory):
    salida = tmp_path_factory.mktemp("evidencias")
    casos, transiciones = ejecutar_todo(DIRECTORIO_DATOS, salida)
    return casos, transiciones, salida


def test_se_ejecutan_todos_los_casos(resultados):
    casos, transiciones, salida = resultados
    assert len(casos) == 120 and len(transiciones) == 20
    assert (salida / "resultados_casos_prueba.csv").exists()
    assert all(c["resultado_alumno"] != "PENDIENTE" for c in casos)


def test_casos_coinciden_con_el_oraculo(resultados, oraculo):
    casos, _, _ = resultados
    for caso in casos:
        procesa, beneficio = oraculo[caso["operacion_id"]]
        if caso["tipo_prueba"] == "validar_operacion":
            assert caso["resultado_alumno"] == ("CUMPLE" if procesa else "NO CUMPLE"), caso["caso_id"]
        else:
            assert caso["resultado_alumno"] == ("APLICA" if beneficio else "NO APLICA"), caso["caso_id"]


def test_transiciones(resultados, oraculo):
    _, transiciones, _ = resultados
    for t in transiciones:
        procesa, _ = oraculo[t["operacion_id"]]
        accion = t["accion_sugerida"]
        if accion == "cancelar":
            assert t["estado_final"] == "CANCELADA" and t["eventos"] == "InscripcionCancelada"
        elif accion == "saltar_estado":
            assert t["estado_final"] == "PREINSCRITA" and t["http_equivalente"] == "409"
            assert t["eventos"] == "(ninguno)"
        elif not procesa:
            assert t["estado_final"] == "PREINSCRITA" and t["http_equivalente"] == "422"
        elif accion == "aprobar":
            assert t["estado_final"] == "VALIDADA" and t["resultado_alumno"] == "OK"
        elif accion == "repetir_aprobacion":
            assert t["estado_final"] == "VALIDADA" and t["http_equivalente"] == "409"
            assert t["eventos"] == "InscripcionValidada"  # la segunda no agrega evento
        elif accion == "completar":
            assert t["estado_final"] in {"FINALIZADA", "VALIDADA"}


def test_accion_desconocida():
    fila = {"caso_id": "X", "operacion_id": "AUL-O001", "accion_sugerida": "volar", "estado_inicial": "PREINSCRITA"}
    assert ejecutar_transicion(fila)["resultado_alumno"] == "ACCIÓN DESCONOCIDA"
