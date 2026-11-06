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

Cuerpo de error: `{"error": "<Excepcion>", "detalle": "<mensaje>"}`.
