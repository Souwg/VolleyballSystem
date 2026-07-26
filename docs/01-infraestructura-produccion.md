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

```text
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
├── deploy.sh
└── local-files/
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

Contiene el script y los respaldos de PostgreSQL:

/opt/sportflow/backups

Respaldos:

/opt/sportflow/backups/postgres

Script:

/opt/sportflow/backups/backup_postgres.sh


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
* FLASK_APP_KEY
* BACKEND_URL
* REACT_APP_BACKEND_URL
* FRONTEND_URL
* ADMIN_EMAIL
* ADMIN_PASSWORD

Nunca deben escribirse valores reales de contraseñas o API keys en esta documentación.



## 9. Usuario administrador

El administrador del sistema utiliza:

admin@sportflow.club

El script de creación se encuentra en:

src/seed_admin.py

La contraseña se obtiene desde la variable:

ADMIN_PASSWORD

No está escrita directamente dentro del código fuente.


## 10. Respaldos

Se ejecuta un respaldo automático de PostgreSQL todos los días.

Configuración de cron:

0 2 * * * /opt/sportflow/backups/backup_postgres.sh >> /opt/sportflow/backups/backup_postgres.log 2>&1

El VPS utiliza UTC.

Por lo tanto:

02:00 UTC = 22:00 del día anterior en Venezuela

Los respaldos se generan en formato:

sportflow_YYYY-MM-DD_HH-MM-SS.sql.gz

El script elimina respaldos con más de 30 días.

También se genera un respaldo antes de cada despliegue.


## 11. Despliegue

El script principal se encuentra en:

/opt/sportflow/deploy.sh

El script realiza:

1- Verificación de la rama develop.
2- Verificación de cambios locales.
3- Consulta de cambios en GitHub.
4- Descarga de la última versión.
5- Respaldo de PostgreSQL.
6- Construcción de la imagen Docker.
7- Inicio y verificación de PostgreSQL.
8- Ejecución de migraciones.
9- Recreación de la aplicación.
10- Limpieza de imágenes sin uso.
11- Verificación final de contenedores.

Para desplegar manualmente:

/opt/sportflow/deploy.sh

Flujo actual:

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


## 12. PWA

SportFlow está configurado como Progressive Web App.

Archivos principales:

public/manifest.webmanifest
public/service-worker.js
public/icons/icon-192.png
public/icons/icon-512.png
public/icons/apple-touch-icon.png

El service worker no almacena actualmente:

* Información privada.
* Respuestas de la API.
* Tokens.
* Pagos.
* Datos administrativos.

La PWA fue probada correctamente en Safari para iPhone.

En iPhone se instala mediante:

Safari
→ Compartir
→ Agregar a pantalla de inicio

En Android:

Chrome
→ Menú
→ Instalar aplicación



## 13. GitHub Actions

Existe un workflow en:

.github/workflows/deploy.yml

Su objetivo es ejecutar automáticamente:

/opt/sportflow/deploy.sh

cuando se realiza un push a:

develop

Actualmente el workflow está pendiente debido a un bloqueo de facturación mostrado por GitHub Actions.

Mientras se resuelve, el despliegue continúa siendo manual mediante:

/opt/sportflow/deploy.sh


## 14. Estado actual

Componente
VPS	Listo
Docker	Listo
Docker Compose	Listo
PostgreSQL	Listo
Gunicorn	Listo
Nginx	Listo
Cloudflare	Listo
Dominio	Listo
HTTPS	Listo
Backups automáticos	Listo
Deploy manual	Listo
PWA	Lista
GitHub Actions	Pendiente por GitHub
Monitorización	Pendiente
Resend en producción	Pendiente
Push notifications	Pendiente



