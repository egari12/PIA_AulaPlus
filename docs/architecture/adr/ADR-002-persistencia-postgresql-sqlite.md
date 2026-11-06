# ADR-002 · SQLAlchemy 2 con PostgreSQL en producción y SQLite en pruebas
**Estado:** Aceptada · **Fecha:** 2026-11-06

**Contexto.** El equipo pensaba usar SQLite. El PIA pide Docker Compose con un servicio de base de datos y un despliegue funcional; en Render/Railway el disco del contenedor se borra en cada despliegue.

**Decisión.** Repositorios con SQLAlchemy 2; la URL viene de `DATABASE_URL`. PostgreSQL 16 en Compose, CI y despliegue; SQLite en memoria para pruebas rápidas y desarrollo local.

**Alternativas.** Solo SQLite (sin servicio DB en Compose y datos perdidos en cada redeploy); SQL escrito a mano con `sqlite3`/`psycopg` (duplicaría código por motor).

**Consecuencias.** El mismo código corre en ambos motores; la CI tiene un job contra PostgreSQL porque SQLite es permisivo con tipos y llaves foráneas. Fechas guardadas en UTC; dinero en `Numeric(12,2)`.
