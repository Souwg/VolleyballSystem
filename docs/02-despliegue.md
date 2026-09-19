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

---

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

---

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

---

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

Antes de enviar los cambios se recomienda comprobar:

```bash
git status
```

y:

```bash
git diff --check
```

No deben subirse al repositorio:

- Contraseñas.
- API keys.
- Tokens.
- Archivos `.env`.
- Claves SSH.
- Credenciales de base de datos.

---

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

---

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

---

## 7. Etapas del despliegue

El script ejecuta las siguientes etapas.

### 7.1 Verificación de la rama

Comprueba que el repositorio esté en:

```text
develop
```

Si se encuentra en otra rama, el despliegue se cancela.

---

### 7.2 Verificación de cambios locales

El script ejecuta una comprobación equivalente a:

```bash
git status --porcelain
```

Si existen cambios locales sin guardar, el despliegue se cancela.

Esto evita que un `git pull` sobrescriba o mezcle cambios hechos directamente en el servidor.

---

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

---

### 7.4 Respaldo previo

Antes de reconstruir la aplicación, se ejecuta:

```bash
/opt/sportflow/backups/backup_postgres.sh
```

Esto crea un respaldo comprimido de PostgreSQL.

Si el respaldo falla, el despliegue se cancela.

Este respaldo protege la información almacenada en PostgreSQL.

Los archivos subidos por los usuarios se almacenan por separado y se explican en la sección de persistencia de archivos.

---

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

La nueva imagen Docker sustituirá a la utilizada por la versión anterior de `sportflow-app`.

---

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

---

### 7.7 Migraciones

Las migraciones se ejecutan con:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  run --rm app flask db upgrade
```

Esto aplica las migraciones pendientes de Alembic sobre la base de datos de producción.

No debe eliminarse esta etapa, especialmente cuando una nueva versión incluye cambios en los modelos o en la estructura de la base de datos.

---

### 7.8 Inicio de la aplicación

Después de las migraciones, se levanta la nueva versión:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  up -d app
```

Docker recrea el contenedor cuando detecta una imagen nueva.

El contenedor principal es:

```text
sportflow-app
```

---

### 7.9 Persistencia de archivos subidos

Los archivos subidos por los usuarios no se almacenan únicamente dentro del contenedor `sportflow-app`.

Entre ellos pueden encontrarse:

- Logos de clubes.
- Fotografías de jugadores.
- Recibos.
- Otros archivos almacenados por SportFlow.

En producción se almacenan físicamente en el VPS en:

```text
/opt/sportflow/uploads
```

Dentro del contenedor están disponibles en:

```text
/app/public/uploads
```

Esto se realiza mediante el volumen configurado en:

```text
/opt/sportflow/docker/compose.yml
```

Configuración:

```yaml
services:
  app:
    volumes:
      - /opt/sportflow/uploads:/app/public/uploads
```

El flujo es:

```text
VPS
/opt/sportflow/uploads
        |
        v
Contenedor sportflow-app
/app/public/uploads
```

Esto permite que los archivos permanezcan disponibles aunque:

- Se reconstruya la imagen Docker.
- Se recree `sportflow-app`.
- Se ejecute un nuevo despliegue.
- Se elimine una versión anterior de la imagen Docker.

Para comprobar que el volumen está montado:

```bash
docker inspect sportflow-app \
  --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

La salida esperada incluye:

```text
/opt/sportflow/uploads -> /app/public/uploads
```

#### Importante

No debe eliminarse manualmente:

```text
/opt/sportflow/uploads
```

durante:

- Despliegues.
- Limpiezas de Docker.
- Mantenimiento del VPS.
- Recreación de contenedores.

El respaldo automático de PostgreSQL no incluye esta carpeta.

Por lo tanto, aunque estos archivos ya sobreviven a los despliegues, debe existir posteriormente un mecanismo de respaldo independiente para:

```text
/opt/sportflow/uploads
```

Para más detalles consultar:

```text
docs/01-infraestructura-produccion.md
```

---

### 7.10 Limpieza

El script elimina imágenes Docker que ya no están siendo utilizadas:

```bash
docker image prune -f
```

Esto ayuda a evitar la acumulación innecesaria de espacio en el VPS.

Este comando elimina imágenes Docker sin uso, pero no elimina:

```text
/opt/sportflow/uploads
```

ni el volumen persistente de PostgreSQL utilizado por SportFlow.

No deben utilizarse comandos como:

```bash
docker compose down -v
```

sin revisar previamente sus consecuencias, ya que la opción `-v` puede eliminar volúmenes administrados por Docker.

---

### 7.11 Verificación final

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

La aplicación debe aparecer en estado:

```text
Up
```

---

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
- Que logos y fotografías subidos anteriormente sigan disponibles.

Cuando el cambio afecte a la PWA, también debe probarse desde la aplicación instalada en el teléfono.

---

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

---

## 10. Verificación de los archivos persistentes

Para comprobar desde el VPS que existen los archivos subidos:

```bash
ls -lah /opt/sportflow/uploads
```

Para consultar el tamaño total:

```bash
du -sh /opt/sportflow/uploads
```

Para comprobar que son visibles dentro del contenedor:

```bash
docker exec sportflow-app \
  ls -lah /app/public/uploads
```

Para comprobar específicamente el montaje:

```bash
docker inspect sportflow-app \
  --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

Debe aparecer:

```text
/opt/sportflow/uploads -> /app/public/uploads
```

Si este montaje no aparece, no deben realizarse nuevos despliegues hasta revisar la configuración de `compose.yml`.

---

## 11. Cambios locales en el VPS

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

Especialmente debe evitarse cualquier comando que pueda afectar:

```text
/opt/sportflow/uploads
```

---

## 12. Variables de entorno

Las variables de producción están en:

```text
/opt/sportflow/docker/.env
```

Este archivo se encuentra fuera del repositorio principal.

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

Nunca deben documentarse los valores reales de:

- Contraseñas.
- API keys.
- Tokens.
- Credenciales de servicios.
- Claves privadas.

---

## 13. Despliegue sin cambios nuevos

El script puede ejecutarse aunque el servidor ya tenga la última versión.

En ese caso puede mostrar:

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

Los archivos almacenados en:

```text
/opt/sportflow/uploads
```

no deben verse afectados por este proceso.

---

## 14. Fallos durante el despliegue

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

Si el problema está relacionado con archivos o imágenes, debe comprobarse también:

```bash
docker inspect sportflow-app \
  --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

y:

```bash
ls -lah /opt/sportflow/uploads
```

---

## 15. GitHub Actions

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

---

## 16. Lista de verificación

### Antes del despliegue

- [ ] Los cambios fueron probados.
- [ ] La rama activa es `develop`.
- [ ] No existen contraseñas dentro del código.
- [ ] Los cambios fueron guardados con `git commit`.
- [ ] El push a GitHub terminó correctamente.
- [ ] No existen cambios locales inesperados en el VPS.

### Durante el despliegue

- [ ] El respaldo de PostgreSQL fue creado.
- [ ] Docker terminó el build.
- [ ] PostgreSQL está saludable.
- [ ] Las migraciones terminaron correctamente.
- [ ] `sportflow-app` está activo.
- [ ] El montaje `/opt/sportflow/uploads -> /app/public/uploads` continúa configurado.

### Después del despliegue

- [ ] `https://sportflow.club` responde.
- [ ] El login funciona.
- [ ] La función modificada fue probada.
- [ ] Los logs no muestran errores nuevos.
- [ ] Los logos de clubes continúan disponibles.
- [ ] Las fotografías de jugadores continúan disponibles.
- [ ] Los archivos subidos anteriormente continúan disponibles.

---

## 17. Comandos rápidos de diagnóstico

Estado de los contenedores:

```bash
cd /opt/sportflow/docker

docker compose \
  --env-file .env \
  -f compose.yml \
  ps
```

Logs de la aplicación:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  logs app --tail=100
```

Verificar volumen de archivos:

```bash
docker inspect sportflow-app \
  --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

Verificar archivos persistentes:

```bash
ls -lah /opt/sportflow/uploads
```

Tamaño de los archivos persistentes:

```bash
du -sh /opt/sportflow/uploads
```

Comprobar estado HTTP:

```bash
curl -I https://sportflow.club
```

---

## 18. Comando principal

El comando oficial para publicar la versión que ya fue enviada a GitHub es:

```bash
/opt/sportflow/deploy.sh
```

El flujo normal de producción es:

```text
Desarrollo
   |
   v
git commit
   |
   v
git push origin develop
   |
   v
SSH al VPS
   |
   v
/opt/sportflow/deploy.sh
   |
   v
Verificación
   |
   v
SportFlow actualizado
```
