"""Ejecuta los 120 casos y las 20 transiciones del paquete del docente.

Uso:  python -m scripts.correr_casos_csv
Salida: docs/evidencias/resultados_casos_prueba.csv y resultados_transiciones.csv
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.infrastructure.cargador_csv import DIRECTORIO_DATOS
from src.infrastructure.ejecutor_casos import ejecutar_todo

SALIDA = Path(__file__).resolve().parents[1] / "docs" / "evidencias"


def main() -> None:
    casos, transiciones = ejecutar_todo(DIRECTORIO_DATOS, SALIDA)

    print(f"Casos ejecutados: {len(casos)}")
    for (tipo, resultado), n in sorted(Counter((c["tipo_prueba"], c["resultado_alumno"]) for c in casos).items()):
        print(f"  {tipo:<18} {resultado:<10} {n}")

    print(f"\nTransiciones ejecutadas: {len(transiciones)}")
    for t in transiciones:
        print(
            f"  {t['caso_id']} {t['operacion_id']} {t['accion_sugerida']:<18} -> "
            f"{t['estado_final']:<11} {t['resultado_alumno']:<9} HTTP {t['http_equivalente']}  {t['excepcion']}"
        )
    print(f"\nResultados en {SALIDA}")


if __name__ == "__main__":
    main()
