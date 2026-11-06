# ADR-004 · Specification Pattern con operadores &, | y ~
**Estado:** Aceptada · **Fecha:** 2026-11-06

**Contexto.** La asignación de tutor combina varias condiciones (materia, modalidad, zona solo si es presencial, disponibilidad, límite diario, traslape) y el paquete del docente pide al menos tres Specifications combinables con AND/OR/NOT.

**Decisión.** Clase base `Especificacion` con `es_satisfecha_por`, `incumplidas` y los operadores `&`, `|`, `~` (clases `Y`, `O`, `No`). Reglas compuestas: `regla_asignacion()`, `PUEDE_PROCESARSE`, `BENEFICIO_REFERENCIA`, `PUEDE_INSCRIBIRSE`.

**Alternativas.** Funciones booleanas sueltas (no explican qué falló); motor de reglas externo (excesivo).

**Consecuencias.** Cada condición se prueba aislada, los mensajes de error dicen qué regla falló (`incumplidas`) y cambiar un umbral toca un solo lugar. La zona presencial usa OR + NOT: `~EsPresencial() | MismaZona()`.
