# Matriz de trazabilidad BRD → regla → componente → prueba

| Requisito | Regla / criterio | Componente (código) | Endpoint | Prueba |
|---|---|---|---|---|
| US-01, RN-06 | Reserva con ≥ 48 h | `AnticipacionMinima`, `Sesion.reservar` | `POST /sesiones` | `test_reserva_con_menos_de_48_horas_se_rechaza`, `test_reserva_con_exactamente_48_horas_es_valida`, `test_errores_de_reserva` |
| US-02, NB-01, RN-07 | Asignación por materia, modalidad, zona, disponibilidad | `regla_asignacion`, `seleccionar_tutor` | `POST /sesiones` | `test_specs_individuales`, `test_zona_solo_importa_si_es_presencial`, `test_seleccion_prefiere_menor_carga` |
| US-02 | Sin tutor → mensaje | `MSG_SIN_TUTOR`, `RecursoNoDisponible` | 409 | `test_reserva_reparte_carga_entre_tutores`, `test_seleccion_sin_candidatos` |
| US-03, NB-02, ADR-007 | Cobro de $200; si falla no se crea | `ServicioSesiones.reservar`, `PasarelaPago` | 402 | `test_pago_rechazado_no_crea_sesion`, `test_si_falla_el_guardado_se_reembolsa` |
| RN-01 | Tarifa fija $200 | `PRECIO_SESION`, `PoliticaTarifas` | — | `test_reserva_asigna_tutor_cobra_y_guarda` |
| RN-02, US-11, NB-03 | 80 % tutor / 20 % comisión | `PoliticaTarifas.liquidar`, `Sesion.liquidar` | `POST /sesiones/{id}/liquidacion` | `test_liquidacion_160_tutor_40_comision`, `test_flujo_completo_hasta_liquidar` |
| US-11 | Reembolsada no se liquida | `ServicioSesiones.liquidar` | — | `test_reembolsada_no_se_liquida`, `test_no_se_liquida_sesion_reembolsada_ni_confirmada` |
| RN-03 | 90 minutos | `DURACION_SESION` | — | `test_reserva_crea_sesion_confirmada_con_evento` |
| RN-04, US-10 | Máx. 5 sesiones/día | `BajoLimiteDiario` | — | `test_limite_de_5_sesiones_por_dia`, `test_sexta_sesion_del_dia_busca_otro_tutor` |
| RN-05 | Uno a uno | `Sesion` (un estudiante, un tutor), `SinTraslape` | — | `test_sin_traslape` |
| RN-08, US-14, NB-04/05 | Umbral 70 % → reembolso total | `Grabacion`, `Sesion.registrar_grabacion` | `POST /sesiones/{id}/grabacion` | `test_grabacion_de_63_minutos_es_70_por_ciento_y_completa`, `test_grabacion_de_62_minutos_reembolsa_el_total` |
| RN-09, US-08, US-12, NB-08 | Penalización por cancelación tardía del tutor | `Sesion.cancelar`, `Tutor.registrar_cancelacion` | `POST /sesiones/{id}/cancelacion` | `test_tutor_cancela_tarde_sin_justificar_se_penaliza`, `test_tutor_cancela_tarde_justificado_no_se_penaliza` |
| US-05, S-1 | Cancelación del estudiante | `Sesion.cancelar` | idem | `test_estudiante_cancela_con_anticipacion_reembolso_total`, `test_estudiante_cancela_tarde_sin_reembolso` |
| RN-10, US-04, US-17 | Calificación mutua en 24 h | `Sesion.calificar` | `POST /sesiones/{id}/calificaciones` | `test_calificacion_mutua_dentro_de_24_horas`, `test_calificacion_fuera_de_plazo` |
| RN-11, US-13, US-16 | Solo Soporte ejecuta | `exigir_rol(..., SOPORTE)` | 403 | `test_solo_soporte_cancela`, `test_cancelacion_solo_soporte` |
| US-06, US-07 | Cambios con 48 h, aplicados por Soporte | `Sesion.solicitar_cambio`, `aplicar_cambio` | `POST /sesiones/{id}/cambios[/aplicar]` | `test_cambio_de_horario`, `test_cambios_rechazados_sin_48_horas`, `test_cambio_que_el_tutor_no_cubre_se_rechaza` |
| US-09 | No quitar disponibilidad con sesiones | `Tutor.actualizar_disponibilidad` | `PUT /tutores/{id}/disponibilidad` | `test_tutor_no_quita_bloque_con_sesion_confirmada`, `test_actualizar_disponibilidad` |
| US-15 | Reportes | `ServicioReportes` | `GET /reportes/...` | `test_reporte_de_sesiones`, `test_cancelacion_tardia_del_tutor_penaliza_y_aparece_en_reporte` |
| US-16 | Comisión configurable a futuro | `ServicioPoliticas` | `PUT /politicas/comision` | `test_comision_nueva_aplica_a_liquidaciones_futuras` |
| Estados de Sesion | Transiciones inválidas → 409 sin evento | `MAQUINA_SESION` | 409 | `test_no_se_registra_grabacion_dos_veces`, `test_grabacion_liquidacion` |
| Paquete docente: `puede_procesarse` | activo ∧ detalle ∧ autorizada | `PUEDE_PROCESARSE` | `POST /inscripciones/{id}/validar` | `test_casos_coinciden_con_el_oraculo` (60 casos) |
| Paquete docente: `beneficio_referencia` | preferente ∧ total ≥ 1500 ∧ ¬promoción | `BENEFICIO_REFERENCIA` | `GET /inscripciones/{id}/beneficio` | `test_casos_coinciden_con_el_oraculo` (60 casos), `test_beneficio_umbral_inclusivo_y_promocion` |
| Paquete docente: transiciones | 20 casos de `transiciones_prueba.csv` | `MAQUINA_INSCRIPCION`, `ejecutor_casos.py` | `POST /inscripciones/{id}/*` | `test_transiciones`, `test_inscripciones_del_paquete` |
| Paquete docente: cupo | cursos habilitados ∧ cupo | `PUEDE_INSCRIBIRSE`, `Curso.reservar_cupo` | 409 | `test_inscribir_sin_cupo_o_curso_deshabilitado` |
| Paquete docente: total con Decimal | Σ precio × cantidad | `Inscripcion.total` | — | `test_total_calculado_a_mano` |

Evidencia de ejecución del paquete: [`docs/evidencias/resultados_casos_prueba.csv`](../evidencias/resultados_casos_prueba.csv) y [`resultados_transiciones.csv`](../evidencias/resultados_transiciones.csv).
