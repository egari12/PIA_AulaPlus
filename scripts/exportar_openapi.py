"""Genera docs/api/openapi.json a partir de la API (sin levantar el servidor).

Uso: python -m scripts.exportar_openapi
"""

from __future__ import annotations

import json
from pathlib import Path

from src.api.main import create_app
from src.config import Configuracion

DESTINO = Path(__file__).resolve().parents[1] / "docs" / "api" / "openapi.json"


def main() -> None:
    app = create_app(Configuracion(database_url="sqlite+pysqlite:///:memory:", sembrar_datos=False))
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OpenAPI escrito en {DESTINO}")


if __name__ == "__main__":
    main()
