# ADR-005 · Roles por encabezado X-Rol
**Estado:** Aceptada · **Fecha:** 2026-11-06

**Contexto.** RN-11, US-13 y US-16 exigen permisos por rol, pero la gestión de usuarios y contraseñas está fuera de alcance.

**Decisión.** Cada petición que cambia sesiones, tutores o políticas envía `X-Rol`. Las reglas de permiso de negocio (solo Soporte cancela o aplica cambios) viven en el dominio; las de acceso (quién reserva, quién liquida, quién ve reportes) en la capa de aplicación.

**Alternativas.** JWT con usuarios reales (más tiempo, no aporta a las reglas del caso); sin roles (incumple RN-11).

**Consecuencias.** La demo en Swagger es simple; para producción real se reemplazaría `obtener_rol` por una dependencia que lea el rol de un token, sin tocar dominio ni servicios.
