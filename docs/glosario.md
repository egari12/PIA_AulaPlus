# Glosario del dominio — AulaPlus

Refinado de la Actividad 2 (10/09/2026). La columna *En el código* muestra el nombre usado en `src/` (lenguaje ubicuo).

| Concepto | Definición | En el código |
|---|---|---|
| Administrador | Consulta reportes y define políticas generales (porcentaje de comisión). No ejecuta operaciones sobre sesiones. | `Rol.ADMINISTRADOR`, `ServicioReportes`, `ServicioPoliticas` |
| Asignación automática | El sistema otorga al estudiante un tutor disponible que cumple materia, modalidad, zona (presencial) y horario, con menos de 5 sesiones ese día. | `regla_asignacion()`, `seleccionar_tutor()` |
| Calificación | Evaluación de 1 a 5 que se dan estudiante y tutor dentro de las 24 h posteriores a la sesión. | `Sesion.calificar`, `calificacion_tutor`, `calificacion_estudiante` |
| Cambio de horario | Solicitud del estudiante para mover la sesión; requiere 48 h y queda pendiente hasta que Soporte la aplica. | `TipoCambio.HORARIO`, `CambioPendiente` |
| Cambio de modalidad | Solicitud para pasar de presencial a en línea o viceversa; requiere 48 h. | `TipoCambio.MODALIDAD` |
| Comisión | Porcentaje retenido por la plataforma: 20 % ($40 MXN) por sesión completada. | `PoliticaTarifas.porcentaje_comision`, `Liquidacion.comision` |
| Comprobante de transacción | Referencia generada al cobrar exitosamente. | `Sesion.referencia_pago` |
| Disponibilidad | Bloques semanales (día, hora inicio, hora fin) más materias, modalidades y zona del tutor. | `BloqueDisponibilidad`, `Tutor` |
| Disputa | Reporte de que una sesión no ocurrió. Fuera del alcance implementado; se resolvería con la grabación. | — |
| Duración grabada | Tiempo entre inicio y fin de la grabación; si es menor al 70 % de 90 min (63 min) hay reembolso. | `Grabacion.duracion`, `cubre_porcentaje_minimo()` |
| Estudiante | Usuario que reserva, paga $200 y califica al tutor. | `estudiante_id`, `Rol.ESTUDIANTE`, `Estudiante` |
| Liquidación de pago | Transferencia del 80 % ($160 MXN) al tutor tras una sesión completada. | `Sesion.liquidar`, `Liquidacion` |
| Modalidad | Presencial o en línea. | `Modalidad` |
| Pago | Cobro de $200 MXN al confirmar la reserva. | `PasarelaPago.cobrar` |
| Penalización | Sanción al tutor que cancela con menos de 48 h sin justificante válido. | `Tutor.penalizaciones`, evento `TutorPenalizado` |
| Reasignación / Reprogramación | Opciones del estudiante cuando el tutor avisa a tiempo; se atienden como cambio de horario aplicado por Soporte. | `Sesion.solicitar_cambio`, `aplicar_cambio` |
| Reembolso | Devolución completa del costo al estudiante (tutor cancela, grabación < 70 % o estudiante cancela con ≥ 48 h). | `Sesion.monto_reembolso`, `PasarelaPago.reembolsar` |
| Reporte | Consulta por rango de fechas: sesiones por estado, pagos, comisiones, reembolsos y tutores con más cancelaciones. | `ReporteSesiones`, `FilaCancelacionesTutor` |
| Reserva | Solicitud del estudiante que, tras asignación y cobro, crea la sesión en estado Confirmada. | `SolicitudReserva`, `Sesion.reservar` |
| Sesión | Clase uno a uno de 90 min. Estados: Confirmada, Completada, Reembolsada, Liquidada, Cancelada. | `Sesion`, `EstadoSesion`, `MAQUINA_SESION` |
| Sesión completada | Grabación ≥ 70 %; abre la ventana de 24 h para calificar y permite liquidar. | `EstadoSesion.COMPLETADA` |
| Soporte | Único rol que ejecuta cancelaciones y cambios sobre sesiones. | `Rol.SOPORTE` |
| Tutor | Registra disponibilidad y materias; máximo 5 sesiones por día; recibe el 80 %. | `Tutor` |
| **Contexto Inscripciones** (paquete del docente) | | |
| Curso | Recurso del catálogo con precio por sesión, cupo y bandera de habilitado. | `Curso` |
| Inscripción | Operación de un estudiante con una o más líneas de cursos. Estados: Preinscrita, Validada, Inscrita, Finalizada, Cancelada. | `Inscripcion`, `MAQUINA_INSCRIPCION` |
| Estudiante preferente | Estudiante con derecho al beneficio de referencia. | `Estudiante.preferente` |
| Beneficio de referencia | Aplica si el estudiante es preferente, el total es ≥ 1500 MXN y no hay promoción activa. | `BENEFICIO_REFERENCIA` |
| Domain Event | Hecho ya ocurrido (en pasado) registrado tras una transición válida. | `EventoDominio`, tabla `eventos_dominio` |
