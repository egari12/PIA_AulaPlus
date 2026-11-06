# AulaPlus — PIA Componentes de Lógica de Negocio (Equipo 8)

Plataforma de asesorías uno a uno entre estudiantes y tutores. Implementa las reglas del BRD (reserva con 48 h, asignación automática de tutor, cobro de $200, umbral de grabación del 70 %, liquidación 80/20, cancelaciones solo por Soporte, calificación en 24 h) con **DDD, Specification, State Machine, Domain Events y API REST (FastAPI + Swagger)**.

**Equipo:** Esther Garza Cano (2143077) · Luis Ángel David Cavazos Reyes (2142838) · Emilio Garza Arizpe (2143702)
**Profesor:** Miguel Ángel Gómez Marroquín · FIME UANL · Noviembre 2026

| | |
|---|---|
| Repositorio | https://github.com/egari12/PIA_AulaPlus |
| Despliegue (Swagger) | https://aulaplus-api-lcb6.onrender.com/docs |

## Estructura

```
├── datos/                 CSV del docente (sin modificar) + tutores.csv del equipo
├── docs/
│   ├── BRD.md             BRD refinado (v2)
│   ├── historias_usuario.md  18 historias con Gherkin
│   ├── glosario.md        lenguaje ubicuo y su nombre en el código
│   ├── architecture/      arquitectura.md (diagramas, patrones, SOLID), trazabilidad.md, adr/
│   ├── api/               openapi.json (se genera con scripts/exportar_openapi.py)
│   └── evidencias/        resultados de los 120 casos y 20 transiciones del paquete
├── src/
│   ├── domain/            comun, especificacion, maquina_estados, sesiones/, inscripciones/
│   ├── application/       casos de uso y puertos
│   ├── infrastructure/    SQLAlchemy, memoria, pasarela simulada, cargador y ejecutor de CSV
│   └── api/               FastAPI: rutas, esquemas, errores
├── tests/                 unit/ e integracion/
├── scripts/               correr_casos_csv.py, exportar_openapi.py
├── .github/workflows/ci.yml
├── Dockerfile · docker-compose.yml · render.yaml · .env.example
```

## Instalación local (Windows / PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
copy .env.example .env        # opcional; por defecto usa SQLite en ./aulaplus.db
```

En macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`.

## Ejecutar la API

```powershell
uvicorn src.api.main:create_app --factory --reload
```

Abrir **http://localhost:8000/docs**. Al arrancar con la base vacía se cargan los CSV de `datos/` (40 estudiantes, 20 cursos, 60 inscripciones, 5 tutores).

## Pruebas

```powershell
python -m pytest --cov=src --cov-report=term-missing     # unitarias + integración, cobertura >= 80 %
python -m scripts.correr_casos_csv                        # 120 casos + 20 transiciones del docente
python -m scripts.exportar_openapi                        # genera docs/api/openapi.json
```

`tests/integracion/test_repositorios_sql.py` usa SQLite en memoria; con `TEST_DATABASE_URL` apunta a PostgreSQL (así corre en la CI y en Docker).

## Docker Compose (DB + App + Tests)

```powershell
docker compose up --build db app      # API en http://localhost:8000/docs con PostgreSQL
docker compose run --rm tests         # pruebas dentro de contenedor contra PostgreSQL
docker compose down -v                # borrar contenedores y datos
```

## Despliegue (Render)

1. En Render: **New → Blueprint** y elegir este repositorio (usa `render.yaml`: servicio Docker + PostgreSQL gratis).
2. Esperar a que `/salud` responda y abrir `https://<servicio>.onrender.com/docs`.
3. Pegar la URL en la tabla de arriba.

Variables de entorno: ver `.env.example` (`DATABASE_URL`, `SEED_DATOS`, `PASARELA_RECHAZAR`, `APP_ENV`).

## Guion de demostración (Swagger)

Todas las fechas en ISO 8601 con zona, p. ej. `2026-11-19T10:00:00-06:00` (jueves). Usa una fecha al menos 48 h en el futuro.

| # | Qué mostrar | Petición | Resultado |
|---|---|---|---|
| 1 | 48 h (RN-06) | `POST /sesiones` con inicio en 5 h, `X-Rol: ESTUDIANTE` | **422** “La reserva debe realizarse con al menos 48 horas de anticipación” |
| 2 | Asignación + cobro | `POST /sesiones` materia `Python`, en línea, jueves 10:00 | **201**, `tutor_id: AUL-T01`, `estado: CONFIRMADA` |
| 3 | Sin tutor | materia `Química` | **409** |
| 4 | Pago rechazado | `estudiante_id: AUL-C040` | **402**, no se crea sesión |
| 5 | Grabación ≥ 70 % | `POST /sesiones/{id}/grabacion` 63 min, `X-Rol: SISTEMA` | `COMPLETADA`, 70.00 % |
| 6 | Liquidación | `POST /sesiones/{id}/liquidacion` | `monto_tutor 160.00`, `comision 40.00` |
| 7 | Grabación < 70 % | otra sesión, 62 min | `REEMBOLSADA`; liquidar → “No aplicable – reembolso” |
| 8 | Solo Soporte | `POST /sesiones/{id}/cancelacion` con `X-Rol: ADMINISTRADOR` | **403**; con `SOPORTE` → `CANCELADA` |
| 9 | Penalización | cancelar como `TUTOR` sin justificar a < 48 h del inicio; `GET /reportes/cancelaciones-tutores` (`ADMINISTRADOR`) | tutor `PENALIZADO (1)` |

> Para el paso 9 en vivo, la sesión debe reservarse 2 días antes de la presentación (la reserva exige 48 h y la penalización exige cancelar a menos de 48 h). Si no, mostrar la prueba `test_cancelacion_tardia_del_tutor_penaliza_y_aparece_en_reporte`, que usa un reloj controlado.
| 10 | Eventos | `GET /sesiones/{id}/eventos` | `SesionReservada`, `SesionCompletada`, `SesionLiquidada` |
| 11 | Paquete docente | `POST /inscripciones/AUL-O004/inscribir` | **409** (saltar estado) |
| 12 | | `POST /inscripciones/AUL-O013/validar` | **422** (sin detalle) |
| 13 | | `POST /inscripciones/AUL-O001/validar` dos veces | 200 y luego **409** |
| 14 | | `GET /inscripciones/AUL-O001/beneficio` | regla `preferente AND total >= 1500 AND NOT promoción` |

## Reglas implementadas
Ver [`docs/BRD.md`](docs/BRD.md) §6 y la [matriz de trazabilidad](docs/architecture/trazabilidad.md).

## Paquete de pruebas del docente
Los CSV de `datos/` modelan inscripciones a cursos, distinto del BRD. Se implementaron en un contexto separado (`src/domain/inscripciones`, ADR-006) sin modificar las reglas de sesiones. Resultados actuales: 46 operaciones cumplen `puede_procesarse`, 9 aplican al beneficio; detalle en `docs/evidencias/`.
