# BRD — AulaPlus (Caso 08) · Equipo 8

**Equipo:** Esther Garza Cano (2143077), Luis Ángel David Cavazos Reyes (2142838), Emilio Garza Arizpe (2143702)
**Curso:** Componentes de Lógica de Negocio · **Profesor:** Miguel Ángel Gómez Marroquín
**Versión:** 2.0 (refinada para el PIA a partir de la Actividad 2, 03/09/2026)

## 1. Contexto
AulaPlus conecta estudiantes con tutores particulares para clases individuales, presenciales o en línea. La plataforma cobra un precio fijo por sesión y debe gestionar de forma eficiente las reservas, el pago, la asignación de tutor y los problemas que surjan.

## 2. Área de oportunidad
- No se sabe con certeza si la sesión ocurrió.
- Las disponibilidades de los tutores están desactualizadas.
- Las cancelaciones se gestionan manualmente.
- Es difícil determinar reembolsos y pagos.

## 3. Stakeholders
| Rol | Responsabilidades |
|---|---|
| Estudiante | Reserva sesiones (materia, tema, modalidad, fecha y horario), paga, solicita cancelaciones o cambios, califica al tutor en las 24 h posteriores. |
| Tutor | Registra y actualiza su disponibilidad (días, horas, materias, modalidad, zona); imparte las sesiones asignadas automáticamente; avisa ausencias; califica al estudiante en 24 h. |
| Soporte | **Único rol** que ejecuta cancelaciones, cambios de horario/modalidad, reembolsos y reasignaciones; resuelve disputas con la evidencia grabada. |
| Administración | Define políticas (porcentaje de comisión, penalizaciones) y consulta reportes. **No** ejecuta cancelaciones ni cambios sobre sesiones individuales. |
| Sistema | Asigna tutor, cobra, evalúa la grabación y liquida automáticamente. |

## 4. Alcance
**Dentro de alcance**
- Asignación automática de tutor según disponibilidad, materia, modalidad, zona (presencial), fecha y horario.
- Cobro al estudiante y cálculo de comisión/liquidación al tutor.
- Control de la ventana de 48 h para cancelaciones y cambios.
- Grabación con marcas de tiempo como evidencia; reembolso automático por umbral del 70 %.
- Flujo solicitud → ejecución de cancelaciones/cambios entre Estudiante/Tutor y Soporte.
- Calificación mutua estudiante–tutor (24 h).
- Penalización automática al tutor por cancelación tardía sin justificación.
- Reportes de operación para Administración.
- **(PIA)** Contexto de *inscripciones a cursos de asesoría* para ejecutar el paquete de pruebas del docente (ver §9).

**Fuera de alcance (fase inicial)**
Tarifas personalizadas por tutor · tutorías grupales en el contexto de sesiones · múltiples monedas · chat en tiempo real · verificación de identidad de tutores · programa de fidelidad o promociones en el contexto de sesiones · app móvil nativa · resolución de disputas (se documenta, no se implementa) · reasignación automática de tutor tras un cambio.

## 5. Necesidades del negocio
| ID | Descripción |
|---|---|
| NB-01 | Asignación automática de tutor según materia, tema, modalidad, fecha y horario. |
| NB-02 | Cobro inmediato al estudiante al confirmar la reserva. |
| NB-03 | Dispersión financiera: retener comisión y transferir liquidación al tutor. |
| NB-04 | Registro de evidencia en video con marcas de tiempo de inicio y fin. |
| NB-05 | Evaluación automática de la duración efectiva para determinar reembolso. |
| NB-06 | Solicitudes de modificación o cancelación sujetas a la ventana de tiempo. |
| NB-07 | Centralización de solicitudes de cambios o disputas en Soporte. |
| NB-08 | Penalizaciones a tutores por inasistencia o cancelación tardía injustificada. |

## 6. Reglas de negocio
| ID | Regla | Dónde vive en el código |
|---|---|---|
| RN-01 | Cada sesión cuesta **$200 MXN** fijos. | `PRECIO_SESION`, `PoliticaTarifas` |
| RN-02 | Comisión **20 % ($40)**, tutor **80 % ($160)** al completar la sesión. | `PoliticaTarifas.liquidar`, `Sesion.liquidar` |
| RN-03 | Duración de **90 minutos**, sin extensión. | `DURACION_SESION` |
| RN-04 | Máximo **5 sesiones por tutor** por día calendario. | `BajoLimiteDiario` |
| RN-05 | Clases uno a uno. | `Sesion` (un estudiante, un tutor) |
| RN-06 | Cambios y cancelaciones ordinarias con **≥ 48 h** de anticipación; la reserva también requiere 48 h (US-01). | `AnticipacionMinima`, `Sesion.tiene_anticipacion` |
| RN-07 | El tutor no rechaza asignaciones que coinciden con su disponibilidad. | `DentroDeDisponibilidad`, `seleccionar_tutor` |
| RN-08 | Si la grabación dura **< 70 %** del tiempo programado, se **reembolsa el total** al estudiante y no se liquida al tutor. *(v1 decía “reembolso de la comisión”; se corrigió para coincidir con US-11, US-14 y el glosario.)* | `Grabacion.cubre_porcentaje_minimo`, `Sesion.registrar_grabacion` |
| RN-09 | Si el tutor cancela con < 48 h sin justificación válida: reembolso 100 % al estudiante y penalización al tutor. | `Sesion.cancelar`, `Tutor.registrar_cancelacion` |
| RN-10 | Estudiante y tutor tienen **24 h** después de la sesión para calificarse (1 a 5). | `Sesion.calificar` |
| RN-11 | **Solo Soporte** procesa cancelaciones y cambios. *(v1 incluía a Administración; se corrigió para coincidir con stakeholders, US-13 y US-16.)* | `exigir_rol(..., SOPORTE)` en `Sesion.cancelar` y `Sesion.aplicar_cambio` |

## 7. Supuestos y decisiones del equipo
- **S-1** Cancelación solicitada por el estudiante con < 48 h: **sin reembolso**, sin penalización al tutor (US-05 remitía a “reglas de negocio” sin definirlas).
- **S-2** Cuando el tutor avisa con ≥ 48 h o justifica, se reembolsa el 100 % al estudiante; las opciones de reasignar o reprogramar (US-08) se atienden con un cambio de horario ejecutado por Soporte.
- **S-3** La penalización del tutor es un contador visible (`PENALIZADO (n)`) en el reporte de US-15.
- **S-4** El orden de la reserva es: validar 48 h → asignar tutor → **cobrar** → confirmar. Si el cobro falla no se crea la sesión; si falla el guardado después de cobrar, se reembolsa (compensación).
- **S-5** La disponibilidad se expresa en hora de Monterrey (UTC-6, sin horario de verano); internamente todo se guarda en UTC.
- **S-6** La autenticación se simula con el encabezado `X-Rol` (fuera de alcance un sistema de usuarios).
- Estudiantes y tutores cuentan con conexión, cámara y micrófono; la sesión pasa a “Completada” cuando el sistema registra la grabación.

## 8. Criterios de éxito
- La asignación respeta disponibilidad, límite diario y no genera traslapes.
- Solo Soporte puede ejecutar cancelaciones o cambios (403 para otros roles).
- Los reembolsos por umbral del 70 % se calculan automáticamente.
- Cada regla del BRD tiene al menos una prueba automatizada (ver `docs/architecture/trazabilidad.md`).

## 9. Extensión para el PIA: contexto Inscripciones
El docente entregó un paquete de pruebas (`datos/*.csv`) con un modelo de **inscripciones a cursos**. Para poder ejecutarlo sin alterar el núcleo del BRD, se agregó un *bounded context* separado:

| Paquete del docente | AulaPlus |
|---|---|
| actor (`actores.csv`) | Estudiante (activo, preferente) |
| recurso (`catalogo.csv`) | Curso de asesoría: precio por sesión, cupo, habilitado |
| operación + detalle | Inscripción con líneas (curso × número de sesiones) |
| PREINSCRITA → VALIDADA → INSCRITA → FINALIZADA / CANCELADA | Máquina de estados `MAQUINA_INSCRIPCION` |
| `puede_procesarse` | `EstudianteActivo & TieneDetalle & Autorizada` |
| `beneficio_referencia` | `EstudiantePreferente & TotalMinimo(1500) & ~PromocionActiva` |
| cupo_disponible | `CursosHabilitados & CupoDisponible` (al inscribir) |

**Diferencias con el BRD original** (documentadas como pide el paquete): los cursos tienen precio variable y cupo, existe una bandera de promoción y un beneficio para estudiantes preferentes. Estas reglas **solo aplican al contexto Inscripciones**; el contexto Sesiones mantiene RN-01 ($200 fijo) y la exclusión de promociones. Ver ADR-006.
