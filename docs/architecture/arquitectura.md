# Arquitectura y decisiones técnicas — AulaPlus

## 1. Capas (arquitectura hexagonal / DDD)

```mermaid
flowchart LR
  subgraph api["src/api (FastAPI)"]
    R[rutas_*.py] --> E[esquemas.py Pydantic]
    R --> X[errores.py → HTTP]
  end
  subgraph app["src/application"]
    S[ServicioSesiones<br/>ServicioInscripciones<br/>ServicioReportes<br/>ServicioPoliticas]
    P[[puertos.py<br/>Repositorios, UnidadDeTrabajo,<br/>PasarelaPago, Reloj]]
  end
  subgraph dom["src/domain"]
    D1[sesiones: Sesion, Tutor,<br/>Specifications de asignación]
    D2[inscripciones: Inscripcion, Curso,<br/>Specifications del paquete]
    D3[comun: Dinero, EventoDominio,<br/>Especificacion, MaquinaEstados]
  end
  subgraph inf["src/infrastructure"]
    I1[repositorios_sql.py + db.py<br/>SQLAlchemy]
    I2[memoria.py]
    I3[externos.py<br/>PasarelaSimulada, Reloj]
    I4[cargador_csv.py<br/>ejecutor_casos.py]
  end
  R --> S
  S --> D1 & D2
  S --> P
  I1 & I2 & I3 -. implementan .-> P
  I1 --> DB[(PostgreSQL / SQLite)]
```

Las dependencias apuntan hacia el dominio: `domain` no importa nada de las otras capas; `application` solo conoce el dominio y los puertos; `infrastructure` y `api` son adaptadores intercambiables.

## 2. Modelo de dominio

```mermaid
classDiagram
  class Sesion {
    <<Aggregate Root>>
    id; estudiante_id; tutor_id
    materia; tema; modalidad; inicio
    estado: EstadoSesion
    precio: Dinero; monto_reembolso: Dinero
    reservar() registrar_grabacion() liquidar()
    cancelar() calificar() solicitar_cambio() aplicar_cambio()
  }
  class Tutor {
    <<Aggregate Root>>
    materias; modalidades; zona
    cancelaciones; penalizaciones
    actualizar_disponibilidad() registrar_cancelacion()
  }
  class Grabacion { <<Value Object>> url; inicio; fin; cubre_porcentaje_minimo() }
  class Liquidacion { <<Value Object>> precio; comision; monto_tutor }
  class PoliticaTarifas { <<Value Object>> precio; porcentaje_comision; liquidar() }
  class BloqueDisponibilidad { <<Value Object>> dia_semana; hora_inicio; hora_fin }
  class SolicitudReserva { <<Value Object>> }
  class Dinero { <<Value Object>> monto: Decimal; moneda }
  class Inscripcion {
    <<Aggregate Root>>
    estado: EstadoInscripcion; autorizada; promocion_activa
    validar() inscribir() finalizar() cancelar() evaluar_beneficio()
  }
  class LineaInscripcion { <<Value Object>> curso_id; precio_unitario; cantidad; subtotal }
  class Curso { <<Entity>> precio; cupo; habilitado; reservar_cupo() }
  class Estudiante { <<Entity>> activo; preferente }
  Sesion "1" *-- "0..1" Grabacion
  Sesion "1" *-- "0..1" Liquidacion
  Sesion --> Tutor : tutor_id
  Tutor "1" *-- "*" BloqueDisponibilidad
  Inscripcion "1" *-- "*" LineaInscripcion
  LineaInscripcion --> Curso : curso_id
  Inscripcion --> Estudiante : estudiante_id
```

## 3. Máquinas de estados

```mermaid
stateDiagram-v2
  direction LR
  state "Sesion" as S {
    [*] --> CONFIRMADA : reservar (48 h + tutor + pago)
    CONFIRMADA --> COMPLETADA : completar (grabación ≥ 70 %)
    CONFIRMADA --> REEMBOLSADA : reembolsar (grabación < 70 %)
    CONFIRMADA --> CANCELADA : cancelar (solo Soporte)
    COMPLETADA --> LIQUIDADA : liquidar ($160 / $40)
  }
```

```mermaid
stateDiagram-v2
  direction LR
  [*] --> PREINSCRITA
  PREINSCRITA --> VALIDADA : validar (activo ∧ detalle ∧ autorizada)
  VALIDADA --> INSCRITA : inscribir (cursos habilitados ∧ cupo)
  INSCRITA --> FINALIZADA : finalizar
  PREINSCRITA --> CANCELADA : cancelar (motivo)
  VALIDADA --> CANCELADA : cancelar (motivo)
```

## 4. Secuencia: reservar sesión (US-01, US-02, US-03)

```mermaid
sequenceDiagram
  actor E as Estudiante
  participant API as POST /sesiones
  participant SS as ServicioSesiones
  participant SP as regla_asignacion()
  participant PG as PasarelaPago
  participant DB as UnidadDeTrabajo
  E->>API: materia, tema, modalidad, inicio (X-Rol: ESTUDIANTE)
  API->>SS: reservar(rol, solicitud)
  SS->>SS: AnticipacionMinima(48 h)
  SS->>DB: tutores y sesiones activas
  SS->>SP: seleccionar_tutor()
  alt sin tutor
    SS-->>API: RecursoNoDisponible → 409
  end
  SS->>PG: cobrar($200)
  alt pago rechazado
    PG-->>API: PagoRechazado → 402 (no se crea sesión)
  end
  SS->>DB: guardar(Sesion CONFIRMADA) + evento SesionReservada
  SS->>DB: commit
  API-->>E: 201 Created
```

## 5. Patrones de diseño

| Patrón | Dónde | Por qué |
|---|---|---|
| Aggregate Root (DDD) | `Sesion`, `Tutor`, `Inscripcion` | Protegen sus invariantes; solo se modifican mediante sus métodos. |
| Value Object | `Dinero`, `Grabacion`, `Liquidacion`, `PoliticaTarifas`, `BloqueDisponibilidad`, `LineaInscripcion` | Inmutables y comparados por valor; validan en el constructor. |
| Specification | `src/domain/*/especificaciones.py` | Reglas con nombre de negocio combinables con AND/OR/NOT (ADR-004). |
| State Machine | `MaquinaEstados` | Transiciones explícitas y auditables (ADR-003). |
| Domain Events | `EventoDominio`, `AgregadoRaiz._registrar` | Registro de hechos ocurridos; se guardan en `eventos_dominio`. |
| Repository + Unit of Work | `puertos.py`, `repositorios_sql.py`, `memoria.py` | Aíslan la persistencia; una transacción por caso de uso. |
| Service Layer | `src/application/servicios_*.py` | Orquesta casos de uso sin lógica de negocio propia. |
| Adapter / Ports & Adapters | `PasarelaPago`, `Reloj` | Permite simular pagos y tiempo en pruebas y demo. |
| Factory | `create_app()`, `Sesion.reservar()` | Construcción controlada de la app y del agregado. |

## 6. Principios SOLID

| Principio | Evidencia |
|---|---|
| **S** — Responsabilidad única | Cada Specification evalúa una sola condición; `errores.py` solo traduce excepciones; `cargador_csv.py` solo lee CSV. |
| **O** — Abierto/cerrado | Se agregan reglas componiendo Specifications nuevas sin modificar las existentes; nuevas transiciones se agregan a la tabla. |
| **L** — Sustitución de Liskov | `UnidadDeTrabajoMemoria` y `UnidadDeTrabajoSQL` son intercambiables: las mismas pruebas de servicios funcionan con ambas. |
| **I** — Segregación de interfaces | Puertos pequeños y separados: `RepositorioTutores`, `RepositorioSesiones`, `PasarelaPago`, `Reloj`. |
| **D** — Inversión de dependencias | Los servicios reciben `UnidadDeTrabajo`, `PasarelaPago` y `Reloj` por constructor; FastAPI los inyecta con `Depends`. |

## 7. Decisiones técnicas (resumen)
- **Dinero:** `Decimal` construido desde texto; nunca `float` (umbral `>= 1500` y 80/20 exactos).
- **Tiempo:** todo se guarda en UTC; la disponibilidad se evalúa en hora de Monterrey (UTC-6 fijo). El 70 % se compara con `timedelta` exacto (63 min = 70 %).
- **Errores → HTTP:** 402 pago rechazado · 403 rol sin permiso · 404 no existe · 409 transición inválida o sin tutor/cupo · 422 datos inválidos o regla violada.
- **Eventos:** se registran solo después de una transición válida y se persisten al guardar el agregado.
- **Configuración:** variables de entorno (`DATABASE_URL`, `SEED_DATOS`, `PASARELA_RECHAZAR`, `APP_ENV`); ver `.env.example`.
- ADRs completos en [`adr/`](adr/).
