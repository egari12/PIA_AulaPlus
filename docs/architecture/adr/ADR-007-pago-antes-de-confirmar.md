# ADR-007 · Cobrar antes de confirmar, con compensación
**Estado:** Aceptada · **Fecha:** 2026-11-06

**Contexto.** En la Actividad 5 se detectó el riesgo de confirmar una sesión antes de cobrar. US-03 indica que si el pago falla la reserva no se confirma.

**Decisión.** Orden en `ServicioSesiones.reservar`: validar 48 h → asignar tutor con la Specification → cobrar en la pasarela → crear `Sesion` CONFIRMADA → guardar y confirmar transacción. Si el guardado falla después de cobrar, se llama a `reembolsar` (compensación).

**Alternativas.** Crear la sesión en estado PENDIENTE_PAGO (agrega un estado que el BRD no tiene).

**Consecuencias.** No existen sesiones confirmadas sin pago ni pagos sin sesión. La pasarela es un puerto (`PasarelaPago`); en la demo se usa `PasarelaSimulada`, que rechaza a los estudiantes listados en `PASARELA_RECHAZAR`.
