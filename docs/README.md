# 📚 Documentación de SportFlow

Bienvenido a la documentación técnica de **SportFlow**.

Este directorio reúne toda la información necesaria para comprender, mantener y desplegar la plataforma en un entorno de producción.

La documentación está organizada por áreas para facilitar su consulta.

---

# Infraestructura

Documentación relacionada con la infraestructura de producción.

| Documento | Descripción |
|-----------|-------------|
| [01 - Infraestructura de Producción](01-infraestructura-produccion.md) | Arquitectura general del entorno de producción. |
| [02 - Despliegue](02-despliegue.md) | Procedimiento oficial para desplegar nuevas versiones. |
| [03 - Resend](03-resend.md) | Configuración del servicio de correo electrónico. |
| [04 - Docker](04-docker.md) | Infraestructura basada en contenedores Docker. |
| [05 - Cloudflare](05-cloudflare.md) | Configuración del dominio, DNS y HTTPS. |
| [06 - Base de datos](06-base-de-datos.md) | Arquitectura y funcionamiento de PostgreSQL. |

---

# Desarrollo

Documentación dirigida a desarrolladores.

| Documento | Descripción |
|-----------|-------------|
| [07 - Backend](07-backend.md) | Arquitectura y organización del backend. |
| [08 - Frontend](08-frontend.md) | Arquitectura y organización del frontend. |
| [09 - Autenticación](09-autenticacion.md) | Sistema de autenticación y autorización. |
| [10 - Progressive Web App](10-pwa.md) | Configuración y funcionamiento de la PWA. |

---

# Operación

Documentación para la administración del entorno de producción.

| Documento | Descripción |
|-----------|-------------|
| [11 - VPS](11-vps.md) | Configuración y administración del servidor de producción. |
| [12 - GitHub](12-github.md) | Flujo de trabajo y control de versiones del proyecto. |

---

# Flujo de trabajo recomendado

El ciclo de desarrollo utilizado actualmente es el siguiente:

```text
Desarrollar en local
        │
        ▼
Probar cambios
        │
        ▼
git add
        │
        ▼
git commit
        │
        ▼
git push origin develop
        │
        ▼
Conectarse al VPS
        │
        ▼
/opt/sportflow/deploy.sh
```

---

# Estado de la documentación

| Área | Estado |
|------|--------|
| Infraestructura | ✅ |
| Despliegue | ✅ |
| Correo (Resend) | ✅ |
| Docker | ✅ |
| Cloudflare | ✅ |
| Base de datos | ✅ |
| Backend | ✅ |
| Frontend | ✅ |
| Autenticación | ✅ |
| PWA | ✅ |
| VPS | ✅ |
| GitHub | ✅ |

---

# Próximas actualizaciones

La documentación continuará ampliándose conforme nuevas funcionalidades sean implementadas en SportFlow.

Algunas integraciones previstas para futuras versiones incluyen:

- GitHub Actions (despliegue automático).
- Automatizaciones con n8n.
- Integración con WAHA.
- Notificaciones Push.
- Nuevos módulos del sistema.

Estas funcionalidades serán documentadas una vez formen parte del proyecto.

---

# Información del documento

| Campo | Valor |
|--------|-------|
| Documento | README.md |
| Proyecto | SportFlow |
| Versión | 1.0 |
| Última actualización | 2026-07-26 |
| Autor | Sousan Wong |