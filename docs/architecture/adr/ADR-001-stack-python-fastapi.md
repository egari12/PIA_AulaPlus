# ADR-001 · Python 3.12 + FastAPI para la API REST
**Estado:** Aceptada · **Fecha:** 2026-11-06

**Contexto.** El PIA exige API REST con OpenAPI/Swagger activo en producción. El equipo ya implementó en Python el núcleo de AulaPlus (Actividad 5) y una API con FastAPI (Actividad 4, TechStore).

**Decisión.** Python 3.12, FastAPI para los endpoints y Pydantic para los contratos. El dominio no importa FastAPI.

**Alternativas.** Flask + flask-smorest (Swagger requiere más configuración); .NET / Spring (el equipo tendría que reescribir el núcleo ya probado).

**Consecuencias.** Swagger en `/docs` y contrato en `/openapi.json` sin trabajo extra; se reutiliza experiencia previa. La validación de forma (tipos, rangos) la hace Pydantic (422) y la de negocio el dominio.
