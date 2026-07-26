# Despliegue de SportFlow

## 1. Objetivo

Este documento describe el proceso utilizado para publicar nuevas versiones de SportFlow en producción.

El despliegue actual utiliza:

- Git y GitHub.
- Docker.
- Docker Compose.
- PostgreSQL.
- Flask-Migrate / Alembic.
- Un script automatizado llamado `deploy.sh`.

La aplicación de producción se encuentra disponible en:

```text
https://sportflow.club
```

## 2. Repositorio y rama de producción

Repositorio:

```text
https://github.com/Souwg/VolleyballSystem
```

Ruta del repositorio en el VPS:

```text
/opt/sportflow/app
```

Rama utilizada actualmente para producción:

```text
develop
```

El servidor debe permanecer en esa rama para que el script de despliegue pueda ejecutarse.

Para comprobar la rama actual:

```bash
cd /opt/sportflow/app
git branch --show-current
```

La salida esperada es:

```text
develop
```

## 3. Flujo de trabajo

El flujo actual de publicación es:

```text
Cambios en desarrollo
        |
        v
git add
        |
        v
git commit
        |
        v
git push origin develop
        |
        v
Conexión al VPS
        |
        v
/opt/sportflow/deploy.sh
        |
        v
SportFlow actualizado
```

Un `git push` solamente actualiza el repositorio de GitHub.

Para actualizar la aplicación que está funcionando en el VPS, también debe ejecutarse:

```bash
/opt/sportflow/deploy.sh
```

## 4. Preparación de los cambios

Antes de desplegar, los cambios deben guardarse en Git.

Ejemplo:

```bash
git add .
git commit -m "Descripción del cambio"
git push origin develop
```

Ejemplo real:

```bash
git add .
git commit -m "Improve player payments interface"
git push origin develop
```

No deben subirse al repositorio:

- Contraseñas.
- API keys.
- Tokens.
- Archivos `.env`.
- Claves SSH.
- Credenciales de base de datos.

## 5. Conexión al servidor

El usuario utilizado para administrar SportFlow es:

```text
sportflowadmin
```

La conexión al VPS se realiza mediante SSH.

Ejemplo:

```bash
ssh sportflowadmin@IP_DEL_SERVIDOR
```

La IP real puede consultarse en el panel del proveedor del VPS.

No se recomienda escribir contraseñas, tokens ni claves privadas dentro de esta documentación.

## 6. Script de despliegue

El script principal se encuentra en:

```text
/opt/sportflow/deploy.sh
```

Para ejecutarlo:

```bash
/opt/sportflow/deploy.sh
```

El archivo debe tener permisos de ejecución.

Para comprobarlos:

```bash
ls -l /opt/sportflow/deploy.sh
```

Para asignarlos nuevamente:

```bash
chmod +x /opt/sportflow/deploy.sh
```

## 7. Etapas del despliegue

El script ejecuta las siguientes etapas.

### 7.1 Verificación de la rama

Comprueba que el repositorio esté en:

```text
develop
```

Si se encuentra en otra rama, el despliegue se cancela.

### 7.2 Verificación de cambios locales

El script ejecuta una comprobación equivalente a:

```bash
git status --porcelain
```

Si existen cambios locales sin guardar, el despliegue se cancela.

Esto evita que un `git pull` sobrescriba o mezcle cambios hechos directamente en el servidor.

### 7.3 Consulta de GitHub

El script consulta la rama remota:

```bash
git fetch origin develop
```

Después compara el commit local con:

```text
origin/develop
```

Si existen cambios remotos, ejecuta:

```bash
git pull --ff-only origin develop
```

La opción `--ff-only` evita crear mezclas automáticas inesperadas en el servidor.

### 7.4 Respaldo previo

Antes de reconstruir la aplicación, se ejecuta:

```bash
/opt/sportflow/backups/backup_postgres.sh
```

Esto crea un respaldo comprimido de PostgreSQL.

Si el respaldo falla, el despliegue se cancela.

### 7.5 Construcción de la imagen

El script cambia al directorio:

```text
/opt/sportflow/docker
```

Y construye la aplicación:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  build app
```

Durante esta etapa se compilan:

- Backend de Flask.
- Dependencias de Python.
- Frontend de React.
- Webpack.
- Archivos de la PWA.
- Recursos estáticos.

### 7.6 Verificación de PostgreSQL

Antes de ejecutar migraciones, se asegura que la base de datos esté activa:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  up -d database
```

El servicio incluye un `healthcheck`.

Las migraciones solamente comienzan cuando PostgreSQL aparece como saludable.

### 7.7 Migraciones

Las migraciones se ejecutan con:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  run --rm app flask db upgrade
```

Esto aplica las migraciones pendientes de Alembic sobre la base de datos de producción.

No debe eliminarse esta etapa, especialmente cuando una nueva versión incluye cambios en los modelos.

### 7.8 Inicio de la aplicación

Después de las migraciones, se levanta la nueva versión:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  up -d app
```

Docker recrea el contenedor cuando detecta una imagen nueva.

### 7.9 Limpieza

El script elimina imágenes Docker que ya no están siendo utilizadas:

```bash
docker image prune -f
```

Esto ayuda a evitar la acumulación innecesaria de espacio en el VPS.

### 7.10 Verificación final

Al finalizar, se ejecuta:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  ps
```

Los servicios esperados son:

```text
sportflow-app
sportflow-database
```

La base de datos debe aparecer como:

```text
healthy
```

## 8. Comprobaciones posteriores

Después de desplegar, debe comprobarse el estado público de SportFlow:

```bash
curl -I https://sportflow.club
```

La respuesta esperada es:

```text
HTTP/2 200
```

También se recomienda abrir en el navegador:

```text
https://sportflow.club/login
```

Y comprobar:

- Que la página cargue.
- Que los estilos estén disponibles.
- Que el inicio de sesión funcione.
- Que no aparezcan errores visibles.
- Que las funciones modificadas respondan correctamente.

## 9. Revisión de contenedores

Para consultar el estado:

```bash
cd /opt/sportflow/docker

docker compose \
  --env-file .env \
  -f compose.yml \
  ps
```

Para revisar logs de la aplicación:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  logs app --tail=100
```

Para seguir los logs en tiempo real:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  logs -f app
```

Para salir de los logs en tiempo real:

```text
Ctrl + C
```

Para revisar PostgreSQL:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  logs database --tail=100
```

## 10. Cambios locales en el VPS

No se recomienda modificar código directamente en producción.

Si por una emergencia se realiza un cambio en:

```text
/opt/sportflow/app
```

debe guardarse posteriormente en GitHub.

Para revisar cambios locales:

```bash
cd /opt/sportflow/app
git status --short
```

Si aparecen archivos modificados, no debe ejecutarse el despliegue hasta revisar esos cambios.

Nunca deben utilizarse comandos destructivos como:

```bash
git reset --hard
git clean -fd
```

sin comprobar previamente qué información eliminarán.

## 11. Variables de entorno

Las variables de producción están en:

```text
/opt/sportflow/docker/.env
```

Ese archivo se encuentra fuera del repositorio principal.

El despliegue utiliza ese archivo mediante:

```bash
--env-file .env
```

Cuando se modifica una variable utilizada durante la compilación del frontend, debe reconstruirse la aplicación.

Ejemplo:

```bash
cd /opt/sportflow/docker

docker compose \
  --env-file .env \
  -f compose.yml \
  build app

docker compose \
  --env-file .env \
  -f compose.yml \
  up -d app
```

## 12. Despliegue sin cambios nuevos

El script puede ejecutarse aunque el servidor ya tenga la última versión.

En ese caso mostrará:

```text
El servidor ya tiene la última versión.
```

Aun así, actualmente realiza:

- Respaldo.
- Construcción.
- Migraciones.
- Recreación de la aplicación.
- Verificación.

Esto permite comprobar que el proceso completo sigue funcionando.

## 13. Fallos durante el despliegue

El script utiliza:

```bash
set -euo pipefail
```

Esto significa que se detiene cuando:

- Un comando devuelve un error.
- Se utiliza una variable no definida.
- Falla un comando dentro de una tubería.

Si el despliegue falla, debe revisarse el último mensaje mostrado.

Después pueden consultarse los contenedores:

```bash
cd /opt/sportflow/docker

docker compose \
  --env-file .env \
  -f compose.yml \
  ps
```

Y los logs:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  logs app --tail=200
```

## 14. GitHub Actions

Existe un workflow en:

```text
.github/workflows/deploy.yml
```

Su objetivo es ejecutar automáticamente:

```bash
/opt/sportflow/deploy.sh
```

después de cada push a:

```text
develop
```

El workflow ya fue creado y subido al repositorio.

Actualmente GitHub no inicia el job debido a un bloqueo de facturación de la cuenta.

Mientras se resuelve, el procedimiento oficial continúa siendo:

```text
git push origin develop
        |
        v
Conectarse al VPS
        |
        v
/opt/sportflow/deploy.sh
```

## 15. Lista de verificación

Antes del despliegue:

- [ ] Los cambios fueron probados.
- [ ] La rama activa es `develop`.
- [ ] No existen contraseñas dentro del código.
- [ ] Los cambios fueron guardados con `git commit`.
- [ ] El push a GitHub terminó correctamente.

Durante el despliegue:

- [ ] El respaldo fue creado.
- [ ] Docker terminó el build.
- [ ] PostgreSQL está saludable.
- [ ] Las migraciones terminaron.
- [ ] `sportflow-app` está activo.

Después del despliegue:

- [ ] `https://sportflow.club` responde.
- [ ] El login funciona.
- [ ] La función modificada fue probada.
- [ ] Los logs no muestran errores nuevos.

## 16. Comando principal

El comando oficial para publicar la versión que ya fue enviada a GitHub es:

```bash
/opt/sportflow/deploy.sh
```
