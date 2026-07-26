# Docker

## 1. Objetivo

Docker es la plataforma utilizada para ejecutar SportFlow en producción mediante contenedores.

Su utilización permite:

- Aislar los servicios.
- Facilitar el despliegue.
- Simplificar las actualizaciones.
- Mantener un entorno consistente entre desarrollo y producción.
- Reducir errores derivados de diferencias entre sistemas operativos.

Toda la infraestructura de producción depende de Docker Compose.

## 2. Arquitectura

Actualmente SportFlow utiliza dos contenedores principales.

```
Internet
      │
      ▼
Cloudflare
      │
      ▼
Nginx
      │
      ▼
Docker
      │
      ├─────────────┐
      ▼             ▼
 Flask App     PostgreSQL
```

La comunicación entre los contenedores se realiza mediante la red interna de Docker.

## 3. Estructura del proyecto

La instalación de producción se encuentra organizada bajo la siguiente estructura:

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

### Descripción de cada directorio

| Ruta | Descripción |
|------|-------------|
| `/opt/sportflow/app` | Código fuente principal de SportFlow. |
| `/opt/sportflow/backups` | Copias de seguridad automáticas de PostgreSQL y scripts de respaldo. |
| `/opt/sportflow/deploy.sh` | Script principal utilizado para desplegar nuevas versiones del sistema. |
| `/opt/sportflow/docker` | Archivos Docker y Docker Compose utilizados en producción. |
| `/opt/sportflow/local-files` | Archivos locales utilizados por la infraestructura del servidor. |
| `/opt/sportflow/logs` | Directorio destinado al almacenamiento de registros del sistema. |
| `/opt/sportflow/scripts` | Scripts auxiliares utilizados por la infraestructura. |
| `/opt/sportflow/uploads` | Archivos cargados por los usuarios durante el uso de la aplicación. |

## 4. Contenedores

Actualmente SportFlow utiliza dos contenedores Docker.

### sportflow-app

Responsabilidades:

- Ejecutar la aplicación Flask.
- Servir la API REST.
- Ejecutar las migraciones de Alembic.
- Procesar el envío de correos mediante Resend.
- Servir los archivos estáticos generados por Webpack.

Tecnologías:

- Python
- Flask
- Gunicorn

---

### sportflow-database

Responsabilidades:

- Almacenar toda la información del sistema.

Motor utilizado:

- PostgreSQL 16 Alpine

La base de datos únicamente es accesible desde la red interna de Docker.

## 5. Imágenes

Actualmente la infraestructura utiliza las siguientes imágenes Docker.

| Imagen | Uso |
|---------|-----|
| docker-app | Aplicación principal de SportFlow. |
| postgres:16-alpine | Base de datos PostgreSQL. |

La imagen de la aplicación se reconstruye automáticamente durante cada despliegue ejecutando el script:

```text
/opt/sportflow/deploy.sh
```

## 6. Variables de entorno

Las variables de entorno utilizadas por Docker se encuentran en:

```text
/opt/sportflow/docker/.env
```

Este archivo no forma parte del repositorio Git y debe permanecer únicamente en el servidor.

Entre las variables configuradas actualmente se encuentran:

- DATABASE_URL
- FLASK_APP_KEY
- RESEND_API_KEY
- MAIL_FROM_EMAIL
- MAIL_FROM_NAME

Nunca deben almacenarse secretos dentro del repositorio.

## 7. Docker Compose

SportFlow utiliza Docker Compose como herramienta para administrar los contenedores de producción.

El archivo principal se encuentra en:

```text
/opt/sportflow/docker/compose.yml
```

Actualmente Docker Compose administra los siguientes servicios:

- app
- database

Las variables de entorno utilizadas por ambos servicios son cargadas desde:

```text
/opt/sportflow/docker/.env
```

Docker Compose es utilizado durante:

- Despliegues.
- Reinicio de servicios.
- Ejecución de migraciones.
- Acceso a los contenedores.
- Verificación del estado de la infraestructura.

## 8. Comandos de uso frecuente

### Ver el estado de los contenedores

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  ps
```

---

### Levantar los servicios

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  up -d
```

---

### Recrear únicamente la aplicación

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  up -d --force-recreate app
```

---

### Detener los servicios

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  down
```

---

### Reconstruir la imagen

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  build app
```

---

### Ver los logs

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  logs -f app
```

## 9. Despliegue

SportFlow no se actualiza ejecutando comandos manuales de Docker.

Todas las actualizaciones de producción deben realizarse mediante el script:

```text
/opt/sportflow/deploy.sh
```

Este script realiza automáticamente las siguientes acciones:

1. Verifica el estado del repositorio Git.
2. Descarga los cambios desde GitHub.
3. Genera un respaldo de PostgreSQL.
4. Reconstruye la imagen Docker.
5. Ejecuta las migraciones de Alembic.
6. Reinicia los contenedores.
7. Comprueba que todos los servicios se encuentren operativos.

No se recomienda ejecutar estos pasos manualmente salvo en tareas de mantenimiento específicas.

## 10. Logs

Los registros de la aplicación pueden consultarse mediante Docker Compose.

### Logs de la aplicación

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  logs -f app
```

### Logs de PostgreSQL

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  logs -f database
```

Los logs permiten diagnosticar errores relacionados con:

- Flask.
- Gunicorn.
- PostgreSQL.
- Alembic.
- Resend.
- Variables de entorno.

## 11. Acceso a los contenedores

Para acceder al contenedor de la aplicación:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  exec app sh
```

Para acceder al contenedor de PostgreSQL:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  exec database sh
```

Este acceso debe utilizarse únicamente para tareas de administración o diagnóstico.

## 12. Reinicio de servicios

### Reiniciar únicamente la aplicación

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  restart app
```

---

### Reiniciar PostgreSQL

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  restart database
```

---

### Reiniciar toda la infraestructura

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  restart
```

## 13. Buenas prácticas

Para mantener un entorno de producción estable se recomienda:

- No modificar archivos directamente dentro de los contenedores.
- Mantener las variables sensibles únicamente en el archivo `.env`.
- Realizar los cambios en el repositorio Git y desplegarlos mediante `deploy.sh`.
- Verificar el estado de los contenedores después de cada despliegue.
- Mantener actualizado Docker y Docker Compose.
- Evitar reconstrucciones innecesarias cuando únicamente cambien variables de entorno.

## 14. Troubleshooting

### El contenedor no inicia

Verificar:

- Variables de entorno.
- Logs del contenedor.
- Estado de PostgreSQL.

---

### Error durante el despliegue

Ejecutar:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  ps
```

y revisar el estado de cada servicio.

---

### La aplicación responde con error 502

Comprobar:

- Estado del contenedor `app`.
- Estado de Gunicorn.
- Estado de Nginx.

## 15. Archivos relacionados

| Archivo | Descripción |
|----------|-------------|
| `/opt/sportflow/docker/compose.yml` | Configuración principal de Docker Compose. |
| `/opt/sportflow/docker/.env` | Variables de entorno utilizadas por los contenedores. |
| `/opt/sportflow/deploy.sh` | Script oficial de despliegue. |
| `Dockerfile` | Construcción de la imagen de la aplicación. |

## 16. Información del documento

| Campo | Valor |
|--------|-------|
| Documento | 04-docker.md |
| Proyecto | SportFlow |
| Versión | 1.0 |
| Última actualización | 2026-07-26 |
| Autor | Sousan Wong |