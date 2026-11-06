# ADR-003 · Máquina de estados como tabla explícita
**Estado:** Aceptada · **Fecha:** 2026-11-06

**Contexto.** La Actividad 5 dejaba la sesión en "Confirmada" tras un reembolso y no impedía saltos de estado.

**Decisión.** Clase genérica `MaquinaEstados` con un diccionario `(estado, acción) → destino`. `Sesion`: CONFIRMADA → COMPLETADA → LIQUIDADA; CONFIRMADA → REEMBOLSADA; CONFIRMADA → CANCELADA. `Inscripcion`: PREINSCRITA → VALIDADA → INSCRITA → FINALIZADA; PREINSCRITA/VALIDADA → CANCELADA. Todo método valida la transición **antes** de modificar y registra el evento **después**.

**Alternativas.** Patrón State con una clase por estado (más clases para pocas transiciones); `if` dispersos en cada método (difícil de auditar).

**Consecuencias.** Las transiciones se leen en un solo lugar, la API expone `acciones_permitidas`, y una transición inválida nunca deja eventos (HTTP 409).
