# Especificación OpenAPI

El contrato se genera desde el código para que nunca quede desactualizado:

```bash
python -m scripts.exportar_openapi   # escribe docs/api/openapi.json
```

La CI también lo genera y lo publica como artefacto (`evidencias`). Con la API corriendo, el mismo contrato está en `/openapi.json` y Swagger UI en `/docs`.

## Contrato de errores

| Código | Excepción de dominio | Ejemplo |
|---|---|---|
| 201 | — | `POST /sesiones`, `POST /inscripciones` |
| 402 | `PagoRechazado` | “El pago no pudo ser procesado. Intente nuevamente” |
| 403 | `PermisoDenegado` | “Solo Soporte puede ejecutar operaciones sobre sesiones” |
| 404 | `NoEncontrado` | sesión, tutor, inscripción o curso inexistente |
| 409 | `TransicionInvalida`, `RecursoNoDisponible` | confirmar dos veces, saltar estado, sin tutor, sin cupo |
| 422 | `DatosInvalidos`, `ReglaNegocioViolada`, validación Pydantic | menos de 48 h, sin detalle, cantidad 0, falta `X-Rol` |

Cuerpo de error (siempre el mismo, también para validación, rutas inexistentes y errores inesperados):

```json
{"error": "<tipo>", "titulo": "<qué significa, en una frase>", "detalle": "<qué pasó y cómo corregirlo>"}
```

| Caso | Código | `error` | Ejemplo de `detalle` |
|---|---|---|---|
| Falta un campo | 422 | `DatosInvalidos` | Falta el campo «tema». |
| Valor fuera de las opciones | 422 | `DatosInvalidos` | «modalidad» no es válido. Opciones: EN_LINEA o PRESENCIAL. |
| Falta el encabezado de rol | 422 | `DatosInvalidos` | Falta el encabezado X-Rol. Indica quién hace la operación: ESTUDIANTE, TUTOR, SOPORTE, ADMINISTRADOR o SISTEMA. |
| Transición no permitida | 409 | `TransicionInvalida` | Sesion: no se permite 'liquidar' desde el estado CONFIRMADA. Desde CONFIRMADA solo se puede: cancelar, completar, reembolsar. |
| Ruta inexistente | 404 | `RutaNoEncontrada` | No existe GET /no-existe. Revisa la lista de endpoints en /docs. |
| Método no permitido | 405 | `MetodoNoPermitido` | /sesiones no acepta DELETE. Revisa en /docs qué métodos tiene. |
| Error no controlado | 500 | `ErrorInterno` | Ocurrió un error inesperado. Intenta de nuevo; si sigue pasando, avisa a Soporte. |
