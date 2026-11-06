# ADR-006 · Contexto separado "Inscripciones" para el paquete CSV del docente
**Estado:** Aceptada · **Fecha:** 2026-11-06

**Contexto.** El docente entregó CSV de prueba con un modelo de inscripciones a cursos (precio variable, cupo, promoción, estudiante preferente) que no coincide con el BRD (tarifa fija de $200, sin promociones). Sus instrucciones piden no reemplazar los requerimientos propios y documentar las diferencias.

**Decisión.** Crear un *bounded context* `src/domain/inscripciones` con su propio agregado, Specifications y máquina de estados, sin tocar el contexto `sesiones`. Los CSV se cargan sin modificarlos y `scripts/correr_casos_csv.py` ejecuta los 120 casos y 20 transiciones con datos frescos por caso.

**Alternativas.** Forzar los CSV al modelo de sesiones (perdería columnas y contradiría RN-01); ignorar los CSV (el docente pidió usarlos en la presentación).

**Consecuencias.** Las reglas de promoción/beneficio no contaminan el núcleo. Las acciones del CSV se interpretan así: `aprobar` = validar; `repetir_aprobacion` = validar dos veces; `saltar_estado` = inscribir sin validar; `completar` = validar → inscribir → finalizar; `cancelar` = cancelar.
