# Infraestructura de producción de SportFlow

## 1. Descripción general

SportFlow es una aplicación web para la gestión de clubes y academias deportivas.

La plataforma permite administrar, entre otros elementos:

- Clubes.
- Categorías.
- Equipos.
- Jugadores.
- Entrenamientos.
- Partidos.
- Pagos.
- Recibos.

La aplicación está desplegada en un VPS y se encuentra disponible en:

````text
https://sportflow.club



## 2. Tecnologías principales

Frontend
-React.
-React Router.
-Webpack.
-CSS.
-PWA.

Backend
-Python.
-Flask.
-SQLAlchemy.
-Flask-Migrate / Alembic.
-Gunicorn.
Base de datos
-PostgreSQL 16.

Infraestructura
-Ubuntu.
-Docker.
-Docker Compose.
-Nginx.
-Cloudflare.
-Let's Encrypt.
-GitHub.


## 3. Arquitectura de producción

El tráfico sigue este recorrido:

Usuario
   |
   | HTTPS
   v
Cloudflare
   |
   v
Nginx
   |
   v
Gunicorn / Flask
   |
   v
PostgreSQL


Cloudflare administra el DNS y actúa como proxy público.

Nginx recibe las solicitudes HTTPS y las envía internamente a la aplicación mediante:


127.0.0.1:3005

PostgreSQL solo está disponible dentro de la red de Docker y no está publicado directamente en Internet.


## 4. Dominio y HTTPS

Dominio principal:

sportflow.club

Dominio alternativo:

www.sportflow.club

El certificado HTTPS fue configurado con Certbot y Let's Encrypt.

Ruta de los certificados:

/etc/letsencrypt/live/sportflow.club/

Certbot administra la renovación automática del certificado.


## 5. Estructura del servidor

La estructura principal se encuentra en:

/opt/sportflow

Distribución:

/opt/sportflow/
├── app/
├── docker/
├── backups/
├── uploads/
└── deploy.sh
app

Contiene el repositorio de SportFlow:

/opt/sportflow/app

Repositorio:

https://github.com/Souwg/VolleyballSystem

Rama de producción utilizada actualmente:

develop
docker

Contiene los archivos del entorno Docker:

/opt/sportflow/docker

Archivos importantes:

compose.yml
Dockerfile
.env

El archivo .env contiene información sensible y no debe subirse a GitHub.

backups

Contiene los conjuntos de respaldo generados fuera de los contenedores:

/opt/sportflow/backups

El script preparado en el repositorio se encuentra en:

/opt/sportflow/app/scripts/backup_sportflow.sh


## 6. Contenedores Docker

La aplicación utiliza dos contenedores principales.

sportflow-app

Contiene:

Aplicación Flask.
Gunicorn.
Frontend compilado.
Archivos estáticos.
PWA.

Puerto interno publicado:

127.0.0.1:3005:3005

El puerto solamente está disponible desde el propio VPS.

sportflow-database

Utiliza:

postgres:16-alpine

La información persiste en el volumen:

sportflow-postgres-data



## 7. Reinicio automático

Los dos servicios tienen configurada la política:

restart: unless-stopped

Esto permite que los contenedores vuelvan a iniciarse cuando:

* El VPS se reinicia.
* Docker se reinicia.
* Un contenedor se detiene inesperadamente.


## 8. Variables de entorno

Las variables privadas se encuentran en:

/opt/sportflow/docker/.env

Entre ellas:

* POSTGRES_DB
* POSTGRES_USER
* POSTGRES_PASSWORD
* DATABASE_URL
* TOKEN_SECRET
* BACKEND_URL
* REACT_APP_BACKEND_URL
* FRONTEND_URL
* ADMIN_EMAIL
* ADMIN_PASSWORD

Nunca deben escribirse valores reales de contraseñas o API keys en esta documentación.

`TOKEN_SECRET` es obligatorio para iniciar en producción. Debe ser una clave
impredecible de al menos 32 caracteres; firma los JWT y los enlaces de recibos.
Antes de desplegar esta versión, configúralo fuera del repositorio y usa
`APP_ENV=production`.



## 9. Usuario administrador

El administrador del sistema utiliza:

admin@sportflow.club

El script de creación se encuentra en:

src/seed_admin.py

La contraseña se obtiene desde la variable:

ADMIN_PASSWORD

No está escrita directamente dentro del código fuente.


## 10. Respaldos

La automatización instalada actualmente respalda PostgreSQL antes de cada
despliegue y mediante cron. Esa automatización anterior no incluye
`/opt/sportflow/uploads`.

La FASE 0.16 deja preparado el script versionado:

```text
/opt/sportflow/app/scripts/backup_sportflow.sh
```

Cada ejecución crea, fuera de los contenedores, un conjunto con una sola marca
de tiempo UTC:

```text
/opt/sportflow/backups/sportflow_YYYY-MM-DD_HH-MM-SSZ/
├── postgres.dump
├── uploads.tar.gz
├── MANIFEST.txt
└── SHA256SUMS
```

`postgres.dump` usa el formato custom de PostgreSQL. `uploads.tar.gz` contiene
todo `/opt/sportflow/uploads`, incluidos `clubs/`, `players/` y `receipts/`
cuando existen. El script valida el dump con `pg_restore --list`, comprueba el
archivo tar y verifica los hashes antes de publicar el conjunto. Un fallo deja
un estado distinto de cero y elimina el conjunto temporal incompleto.

El destino predeterminado es el filesystem del host, no el contenedor ni el
volumen de PostgreSQL. Para resistir la pérdida completa del VPS debe copiarse
además cada conjunto verificado a almacenamiento fuera de ese VPS. También se
puede apuntar `BACKUP_ROOT` a un almacenamiento externo ya montado; el script no
configura ni presupone un proveedor.

La retención predeterminada es de 30 días y puede configurarse con
`BACKUP_RETENTION_DAYS`. La limpieza solo considera directorios completos con
el nombre generado por este script y se ejecuta después de verificar el nuevo
respaldo.

Antes de activarlo en producción hay que sustituir en cron y en
`/opt/sportflow/deploy.sh` la llamada al script anterior. Ejemplo para la tarea
diaria, con el VPS en UTC:

```text
0 2 * * * /opt/sportflow/app/scripts/backup_sportflow.sh >> /opt/sportflow/backups/backup_sportflow.log 2>&1
```

La instalación y esa sustitución son acciones de producción y no se realizaron
durante la FASE 0.16.

Para minimizar diferencias entre la base de datos y los PDF, un respaldo de
recuperación debe ejecutarse en una ventana sin escrituras o con el servicio
`app` detenido. El script toma primero el dump y después archiva `uploads`; si
la aplicación continúa aceptando pagos durante ese intervalo, existe una
ventana pequeña de inconsistencia entre ambos componentes.


## 11. Persistencia de archivos subidos

SportFlow permite subir archivos que deben permanecer disponibles aunque el contenedor de la aplicación sea reconstruido o recreado durante un despliegue.

Entre estos archivos se encuentran:

- Logos de clubes.
- Fotografías de jugadores.
- Recibos.
- Otros archivos almacenados dentro de `public/uploads`.

Inicialmente estos archivos se guardaban únicamente dentro del contenedor:

```text
/app/public/uploads
```

Esto provocaba que pudieran perderse cuando `sportflow-app` era reconstruido o recreado durante un despliegue.

Para evitarlo, los archivos se almacenan de forma persistente en el VPS.

Ruta en el servidor:

```text
/opt/sportflow/uploads
```

Ruta dentro del contenedor:

```text
/app/public/uploads
```

El servicio `app` del archivo:

```text
/opt/sportflow/docker/compose.yml
```

incluye el siguiente volumen:

```yaml
services:
  app:
    volumes:
      - /opt/sportflow/uploads:/app/public/uploads
```

El flujo de almacenamiento es:

```text
VPS
/opt/sportflow/uploads
        |
        v
Contenedor sportflow-app
/app/public/uploads
```

De esta forma, los archivos permanecen almacenados en el VPS aunque el contenedor de la aplicación sea reconstruido o recreado.

Para comprobar que el volumen está montado correctamente:

```bash
docker inspect sportflow-app \
  --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

La salida esperada incluye:

```text
/opt/sportflow/uploads -> /app/public/uploads
```

No debe eliminarse manualmente:

```text
/opt/sportflow/uploads
```

durante despliegues, tareas de limpieza o mantenimiento del servidor.

El comando utilizado durante el despliegue:

```bash
docker image prune -f
```

no elimina esta carpeta.

El respaldo conjunto preparado en la sección anterior incluye este directorio.
Hasta instalarlo en producción, la tarea automática existente continúa
protegiendo únicamente PostgreSQL.


## 12. Despliegue

El script principal se encuentra en:

```text
/opt/sportflow/deploy.sh
```

El script realiza:

1. Verificación de la rama `develop`.
2. Verificación de cambios locales.
3. Consulta de cambios en GitHub.
4. Descarga de la última versión.
5. Respaldo de PostgreSQL.
6. Construcción de la imagen Docker.
7. Inicio y verificación de PostgreSQL.
8. Ejecución de migraciones.
9. Recreación de la aplicación.
10. Limpieza de imágenes sin uso.
11. Verificación final de contenedores.

Para desplegar manualmente:

```bash
/opt/sportflow/deploy.sh
```

Flujo actual:

```text
Cambios en desarrollo
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


## 13. PWA

SportFlow está configurado como Progressive Web App.

Archivos principales:

```text
public/manifest.webmanifest
public/service-worker.js
public/icons/icon-192.png
public/icons/icon-512.png
public/icons/apple-touch-icon-v2.png
```

El service worker no almacena actualmente:

- Información privada.
- Respuestas de la API.
- Tokens.
- Pagos.
- Datos administrativos.

La PWA fue probada correctamente en Safari para iPhone.

En iPhone se instala mediante:

```text
Safari
→ Compartir
→ Agregar a pantalla de inicio
```

En Android:

```text
Chrome
→ Menú
→ Instalar aplicación
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

cuando se realiza un push a:

```text
develop
```

Actualmente el workflow está pendiente debido a un bloqueo de facturación mostrado por GitHub Actions.

Mientras se resuelve, el despliegue continúa siendo manual mediante:

```bash
/opt/sportflow/deploy.sh
```


## 15. Estado actual

| Componente | Estado |
|---|---|
| VPS | Listo |
| Docker | Listo |
| Docker Compose | Listo |
| PostgreSQL | Listo |
| Gunicorn | Listo |
| Nginx | Listo |
| Cloudflare | Listo |
| Dominio | Listo |
| HTTPS | Listo |
| Backups PostgreSQL | Listo |
| Persistencia de archivos subidos | Lista |
| Backup de archivos subidos | Pendiente |
| Deploy manual | Listo |
| PWA | Lista |
| GitHub Actions | Pendiente por GitHub |
| Monitorización | Pendiente |
| Resend en producción | Pendiente |
| Push notifications | Pendiente |
````
