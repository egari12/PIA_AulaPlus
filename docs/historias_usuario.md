# Historias de usuario y criterios Gherkin — AulaPlus

Refinadas de la Actividad 2. Las historias **US-17** y **US-18** se agregaron en el PIA (calificación del tutor al estudiante, que RN-10 exigía, y el contexto de inscripciones del paquete del docente). La columna *Prueba* apunta a `tests/`.

| ID | Rol | Historia | NB | Prueba principal |
|---|---|---|---|---|
| US-01 | Estudiante | Reservar sesión con materia, tema, modalidad, fecha y horario con ≥ 48 h | NB-06 | `test_reserva_con_menos_de_48_horas_se_rechaza` |
| US-02 | Estudiante | Asignación automática de tutor | NB-01 | `test_reserva_asigna_tutor_cobra_y_guarda` |
| US-03 | Estudiante | Pagar $200 al confirmar | NB-02 | `test_pago_rechazado_no_crea_sesion` |
| US-04 | Estudiante | Calificar al tutor en 24 h | — | `test_calificacion_fuera_de_plazo` |
| US-05 | Estudiante | Solicitar cancelación con ≥ 48 h | NB-06 | `test_estudiante_cancela_con_anticipacion_reembolso_total` |
| US-06 | Estudiante | Solicitar cambio de horario | NB-06 | `test_cambio_de_horario` |
| US-07 | Estudiante | Solicitar cambio de modalidad | NB-06 | `test_cambio_de_modalidad_pendiente_y_aplicado_por_soporte` |
| US-08 | Estudiante | Opciones cuando el tutor avisa o justifica | NB-06/08 | `test_tutor_cancela_tarde_justificado_no_se_penaliza` |
| US-09 | Tutor | Registrar/actualizar disponibilidad | — | `test_tutor_no_quita_bloque_con_sesion_confirmada` |
| US-10 | Tutor | Recibir asignaciones sin poder rechazarlas | NB-01 | `test_sexta_sesion_del_dia_busca_otro_tutor` |
| US-11 | Tutor | Recibir el 80 % de cada sesión completada | NB-03 | `test_liquidacion_160_tutor_40_comision` |
| US-12 | Tutor | Avisar ausencia con 48 h | NB-06/08 | `test_cancelacion_tardia_del_tutor_penaliza_y_aparece_en_reporte` |
| US-13 | Soporte | Ejecutar cancelaciones | NB-07 | `test_solo_soporte_cancela` |
| US-14 | Sistema | Reembolso automático si la grabación < 70 % | NB-04/05 | `test_grabacion_de_62_minutos_reembolsa_el_total` |
| US-15 | Administrador | Reportes de operación | — | `test_reporte_de_sesiones` |
| US-16 | Administrador | Definir políticas (comisión) | — | `test_comision_nueva_aplica_a_liquidaciones_futuras` |
| US-17 | Tutor | Calificar al estudiante en 24 h | — | `test_calificacion_mutua_dentro_de_24_horas` |
| US-18 | Estudiante | Inscribirse a cursos de asesoría | — | `tests/integracion/test_casos_csv.py` |

---

### US-01 Reservar sesión
```gherkin
Escenario: Reserva válida con anticipación suficiente
  Dado que el estudiante seleccionó materia, tema, modalidad, fecha y horario
  Y la fecha/hora es al menos 48 horas posterior al momento actual
  Cuando el estudiante confirma la reserva
  Entonces el sistema crea la reserva y la envía a asignación automática de tutor

Escenario: Reserva rechazada por falta de anticipación
  Dado que el estudiante seleccionó una fecha/hora con menos de 48 horas de anticipación
  Cuando intenta confirmar la reserva
  Entonces el sistema rechaza la operación con "La reserva debe realizarse con al menos 48 horas de anticipación"
```

### US-02 Asignación automática
```gherkin
Escenario: Asignación automática exitosa
  Dado que existe al menos un tutor que coincide en materia, modalidad, zona (si es presencial), fecha y horario
  Cuando el estudiante confirma la reserva
  Entonces el sistema asigna al tutor con menos sesiones ese día y la reserva queda "Confirmada"

Escenario: No hay tutor disponible
  Dado que ningún tutor coincide con los criterios
  Cuando el estudiante confirma la reserva
  Entonces el sistema no crea la sesión y muestra "No hay tutores disponibles para los criterios seleccionados"
```

### US-03 Pago
```gherkin
Escenario: Pago exitoso al confirmar reserva
  Dado que el estudiante confirmó una reserva válida
  Cuando se procesa el pago de $200 MXN
  Entonces la reserva queda pagada y se registra la referencia de la transacción

Escenario: Pago fallido
  Dado que el estudiante confirmó una reserva válida
  Cuando el procesador rechaza el pago
  Entonces la reserva no se confirma y se muestra "El pago no pudo ser procesado. Intente nuevamente"
```

### US-04 Calificar al tutor
```gherkin
Escenario: Calificación dentro del plazo
  Dado que la sesión está "Completada" y pasaron menos de 24 horas desde su fin
  Cuando el estudiante envía su calificación de 1 a 5
  Entonces el sistema registra la calificación asociada al tutor

Escenario: Calificación fuera de plazo
  Dado que pasaron más de 24 horas desde el fin de la sesión
  Cuando el estudiante intenta calificar
  Entonces el sistema muestra "El periodo de calificación ha finalizado"
```

### US-05 Solicitar cancelación
```gherkin
Escenario: Cancelación sin penalización
  Dado que la sesión es dentro de más de 48 horas
  Cuando el estudiante solicita la cancelación y Soporte la ejecuta
  Entonces se reembolsa el 100 % y no hay penalización

Escenario: Cancelación con menos de 48 horas
  Dado que la sesión es dentro de menos de 48 horas
  Cuando el estudiante solicita la cancelación y Soporte la ejecuta
  Entonces la sesión queda "Cancelada" sin reembolso (supuesto S-1)
```

### US-06 Cambio de horario
```gherkin
Escenario: Solicitud válida
  Dado que la sesión es dentro de más de 48 horas
  Cuando el estudiante solicita un nuevo horario
  Entonces la solicitud queda pendiente de aprobación por Soporte

Escenario: Rechazo por falta de anticipación
  Dado que la sesión es dentro de menos de 48 horas
  Cuando el estudiante solicita un cambio de horario
  Entonces se muestra "Los cambios de horario requieren mínimo 48 horas de anticipación"
```

### US-07 Cambio de modalidad
```gherkin
Escenario: Rechazo por falta de anticipación
  Dado que la sesión es dentro de menos de 48 horas
  Cuando el estudiante solicita cambiar la modalidad
  Entonces el sistema rechaza la solicitud automáticamente

Escenario: Solicitud válida
  Dado que la sesión es dentro de más de 48 horas
  Cuando el estudiante solicita cambiar la modalidad
  Entonces la solicitud queda pendiente y Soporte la aplica
```

### US-08 Tutor avisa o justifica
```gherkin
Escenario: Tutor avisó con anticipación o justificó
  Dado que el tutor notificó su ausencia con ≥ 48 horas o justificó una emergencia
  Cuando Soporte ejecuta la cancelación
  Entonces se reembolsa el 100 % al estudiante y no se penaliza al tutor

Escenario: Tutor cancela sin aviso ni justificación
  Dado que el tutor cancela con menos de 48 horas sin justificación
  Cuando Soporte ejecuta la cancelación
  Entonces se reembolsa el 100 % al estudiante y se penaliza al tutor
```

### US-09 Disponibilidad
```gherkin
Escenario: Actualización exitosa
  Dado que el tutor modifica sus bloques de disponibilidad
  Cuando guarda los cambios
  Entonces las nuevas reservas usan la disponibilidad actualizada

Escenario: Bloque con sesión confirmada
  Dado que el tutor tiene una sesión confirmada en un bloque
  Cuando intenta eliminarlo
  Entonces se muestra "No se puede modificar disponibilidad que contiene sesiones confirmadas"
```

### US-10 Asignaciones sin rechazo
```gherkin
Escenario: Asignación dentro de la disponibilidad
  Dado que una reserva coincide con la disponibilidad del tutor
  Cuando el sistema asigna
  Entonces la sesión se agrega al calendario del tutor sin opción de rechazo

Escenario: Límite diario
  Dado que el tutor ya tiene 5 sesiones ese día
  Cuando el sistema intenta asignarle una sexta
  Entonces la asignación falla para ese tutor y se busca otro
```

### US-11 Liquidación
```gherkin
Escenario: Liquidación tras sesión completada
  Dado que la sesión está "Completada"
  Cuando el sistema liquida
  Entonces se transfieren $160 al tutor y se registran $40 de comisión

Escenario: Sesión reembolsada
  Dado que la sesión generó un reembolso total
  Cuando el sistema intenta liquidar
  Entonces no hay transferencia y el pago queda "No aplicable – reembolso"
```

### US-12 Aviso de ausencia del tutor
```gherkin
Escenario: Aviso con anticipación suficiente
  Dado que el tutor avisa con 48 horas o más
  Cuando Soporte ejecuta la cancelación
  Entonces no se penaliza al tutor

Escenario: Aviso tardío sin justificación
  Dado que el tutor avisa con menos de 48 horas sin justificar
  Cuando Soporte ejecuta la cancelación
  Entonces se penaliza al tutor y se reembolsa el 100 % al estudiante
```

### US-13 Soporte ejecuta cancelaciones
```gherkin
Escenario: Cancelación ejecutada por Soporte
  Dado que existe una solicitud de cancelación
  Cuando Soporte la ejecuta
  Entonces la sesión pasa a "Cancelada" y se aplica la política de reembolso/penalización

Escenario: Intento de otro rol
  Dado que un Estudiante, Tutor o Administrador intenta ejecutar una cancelación
  Cuando envía la operación
  Entonces se responde 403 "Solo Soporte puede ejecutar operaciones sobre sesiones"
```

### US-14 Umbral del 70 %
```gherkin
Escenario: Duración grabada menor al 70 %
  Dado que la grabación duró menos del 70 % de 90 minutos (menos de 63 min)
  Cuando el sistema evalúa la sesión
  Entonces la sesión pasa a "Reembolsada" y se reembolsa el total

Escenario: Duración grabada igual o mayor al 70 %
  Dado que la grabación duró 63 minutos o más
  Cuando el sistema evalúa la sesión
  Entonces la sesión pasa a "Completada" sin reembolso
```

### US-15 Reportes
```gherkin
Escenario: Reporte por periodo
  Dado que el administrador elige un rango de fechas
  Cuando solicita el reporte de sesiones
  Entonces ve sesiones por estado, estado de pago, total cobrado, comisiones y reembolsos

Escenario: Tutores con más cancelaciones
  Dado que existen tutores con cancelaciones
  Cuando solicita el reporte de cancelaciones
  Entonces se listan ordenados de mayor a menor con su estado de penalización
```

### US-16 Políticas
```gherkin
Escenario: Actualización de comisión
  Dado que el administrador cambia el porcentaje de comisión
  Cuando guarda el cambio
  Entonces el nuevo porcentaje se aplica a las liquidaciones futuras

Escenario: Intento de operación sobre una sesión
  Dado que el administrador intenta cancelar una sesión
  Cuando realiza la acción
  Entonces se responde 403 "Solo Soporte puede ejecutar operaciones sobre sesiones"
```

### US-17 Tutor califica al estudiante (nueva)
```gherkin
Escenario: Calificación mutua
  Dado que la sesión está "Completada" y pasaron menos de 24 horas
  Cuando el tutor califica al estudiante
  Entonces se registra la calificación del estudiante, independiente de la que dio el estudiante

Escenario: Calificación repetida
  Dado que el tutor ya calificó esa sesión
  Cuando intenta calificar de nuevo
  Entonces se rechaza la operación
```

### US-18 Inscripción a cursos (nueva, paquete del docente)
```gherkin
Escenario: Validar una inscripción
  Dado una inscripción PREINSCRITA de un estudiante activo, con al menos un curso y autorizada
  Cuando se valida
  Entonces pasa a VALIDADA y se registra InscripcionValidada

Escenario: Saltar un estado
  Dado una inscripción PREINSCRITA
  Cuando se intenta inscribir sin validar
  Entonces se responde 409 y el estado no cambia

Escenario: Beneficio de referencia
  Dado un estudiante preferente con total >= 1500 MXN y sin promoción activa
  Cuando se evalúa el beneficio
  Entonces el beneficio aplica
```
