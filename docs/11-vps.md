# VPS

> **Nivel:** Infraestructura
>
> **Audiencia:** Desarrolladores / Administradores del servidor

---

## 1. Objetivo

El VPS (Virtual Private Server) es el servidor principal donde se ejecuta el entorno de producción de SportFlow.

Su función es alojar todos los servicios necesarios para el funcionamiento de la plataforma, incluyendo:

- Sistema operativo.
- Docker.
- PostgreSQL.
- Aplicación Flask.
- Archivos estáticos.
- Dominio.
- HTTPS.
- Backups.
- Despliegues.
- Monitorización.

El VPS constituye el núcleo de toda la infraestructura de producción.

---

## 2. Descripción general

Actualmente SportFlow se ejecuta sobre un servidor Linux configurado exclusivamente para la aplicación.

Toda la infraestructura ha sido diseñada para que el despliegue sea reproducible y sencillo de mantener.

El servidor aloja:

- Código fuente.
- Contenedores Docker.
- Base de datos PostgreSQL.
- Scripts de despliegue.
- Copias de seguridad.
- Archivos subidos por los usuarios.
- Logs del sistema.

---

## 3. Especificaciones del servidor

Proveedor:

```
Vultr
```

Sistema operativo:

```
Ubuntu Server 24.04 LTS
```

Arquitectura:

```
64 bits
```

Acceso remoto:

```
SSH
```

Usuario principal:

```
sportflowadmin
```

La autenticación se realiza mediante credenciales SSH.

---

## 4. Arquitectura

```
Usuario
      │
      ▼
Internet
      │
      ▼
Cloudflare
      │
      ▼
Servidor VPS
      │
      ▼
Docker Compose
      │
      ├──────────────┐
      ▼              ▼
 Flask App      PostgreSQL
```

Toda la infraestructura reside dentro del VPS.

---

## 5. Estructura del servidor

La estructura principal es:

```text
/opt
└── sportflow
    ├── app
    ├── backups
    ├── deploy.sh
    ├── docker
    ├── local-files
    ├── logs
    ├── scripts
    └── uploads
```

Cada directorio cumple una función específica dentro del entorno de producción.

---

## 6. Organización de directorios

### app

Contiene el código fuente completo de SportFlow.

Dentro de este directorio se encuentran:

- Backend.
- Frontend.
- Migraciones.
- Documentación.
- Archivos públicos.
- Configuración de Webpack.

---

### docker

Contiene la infraestructura Docker.

Archivos principales:

- Dockerfile
- compose.yml
- .env

---

### backups

Almacena las copias de seguridad automáticas de PostgreSQL.

Los respaldos se generan antes de cada despliegue.

---

### logs

Directorio reservado para registros del sistema y futuras herramientas de monitorización.

---

### uploads

Almacena archivos cargados por los usuarios.

Este directorio debe preservarse durante actualizaciones y despliegues.

---

### scripts

Contiene scripts auxiliares relacionados con la administración del servidor.

---

### local-files

Contiene archivos utilizados por la infraestructura que no forman parte del código fuente.

---

## 7. Servicios instalados

Actualmente el VPS utiliza:

- Ubuntu Server
- Docker Engine
- Docker Compose
- PostgreSQL
- Gunicorn
- Flask
- Cloudflare
- Resend
- UptimeRobot (monitorización externa)

Todos estos servicios trabajan conjuntamente para mantener SportFlow operativo.

---

## 8. Seguridad

Actualmente el servidor implementa:

- Acceso mediante SSH.
- HTTPS.
- Variables sensibles fuera del repositorio.
- Contenedores Docker aislados.
- PostgreSQL sin acceso público.
- Cloudflare como capa adicional de protección.

Las credenciales nunca deben almacenarse dentro del código fuente.

---

## 9. Flujo de despliegue

El proceso de despliegue sigue el siguiente flujo:

```
Desarrollador

      │

git push

      │

GitHub

      │

SSH

      │

Servidor VPS

      │

deploy.sh

      │

Docker Compose

      │

Migraciones

      │

SportFlow actualizado
```

Actualmente el despliegue se inicia ejecutando manualmente:

```bash
/opt/sportflow/deploy.sh
```

La automatización mediante GitHub Actions está prevista para una fase posterior.

---

## 10. Backups

Antes de cada despliegue se genera automáticamente una copia de seguridad de PostgreSQL.

Ubicación:

```text
/opt/sportflow/backups/postgres
```

Esto permite restaurar la información en caso de cualquier incidencia durante una actualización.

---

## 11. Monitorización

Actualmente la disponibilidad pública de SportFlow es supervisada mediante:

- UptimeRobot

El objetivo es detectar rápidamente cualquier interrupción del servicio.

---

## 12. Mantenimiento

Las tareas habituales de mantenimiento incluyen:

- Actualización del código fuente.
- Ejecución de despliegues.
- Supervisión de los contenedores.
- Revisión de logs.
- Verificación de backups.
- Comprobación del estado de PostgreSQL.

---

## 13. Buenas prácticas

Se recomienda:

- No modificar archivos directamente en producción.
- Realizar todos los cambios desde el entorno local.
- Versionar el código mediante Git.
- Utilizar siempre el script oficial de despliegue.
- Verificar el estado del servidor después de cada actualización.
- Mantener Ubuntu y Docker actualizados.

---

## 14. Troubleshooting

### No es posible acceder por SSH

Verificar:

- Dirección IP del servidor.
- Usuario.
- Credenciales SSH.
- Estado del VPS.

---

### La aplicación no responde

Comprobar:

- Estado de Docker.
- Estado de los contenedores.
- Logs de la aplicación.

---

### Error durante el despliegue

Verificar:

- Estado del repositorio Git.
- Variables de entorno.
- Resultado de las migraciones.
- Estado de PostgreSQL.

---

## 15. Checklist

Antes de considerar operativo el servidor verificar:

- SSH funcionando.
- Docker iniciado.
- PostgreSQL operativo.
- Cloudflare configurado.
- HTTPS activo.
- Resend funcionando.
- Despliegue exitoso.
- Backups automáticos.
- Monitorización activa.

---

## 16. Estado actual

| Componente | Estado |
|------------|--------|
| VPS | ✅ |
| Ubuntu 24.04 LTS | ✅ |
| Docker | ✅ |
| PostgreSQL | ✅ |
| Cloudflare | ✅ |
| HTTPS | ✅ |
| Resend | ✅ |
| UptimeRobot | ✅ |
| Despliegue | ✅ |

---

## 17. Archivos relacionados

| Recurso | Descripción |
|----------|-------------|
| `/opt/sportflow/deploy.sh` | Script oficial de despliegue. |
| `/opt/sportflow/docker/compose.yml` | Configuración de Docker Compose. |
| `/opt/sportflow/docker/.env` | Variables de entorno del servidor. |
| `docs/04-docker.md` | Infraestructura Docker. |
| `docs/05-cloudflare.md` | Configuración del dominio. |
| `docs/06-base-de-datos.md` | Base de datos PostgreSQL. |

---

## 18. Información del documento

| Campo | Valor |
|--------|-------|
| Documento | 11-vps.md |
| Proyecto | SportFlow |
| Versión | 1.0 |
| Última actualización | 2026-07-26 |
| Autor | Sousan Wong |