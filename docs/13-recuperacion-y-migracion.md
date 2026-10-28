# Recuperación y migración de SportFlow

> **Nivel:** Infraestructura
> **Audiencia:** Desarrolladores / Administradores del servidor

---

## 1. Objetivo

Este documento describe los elementos que deben conservarse para poder recuperar o migrar SportFlow desde un VPS hacia otro servidor.

El procedimiento documentado actualmente cubre:

- Respaldo de PostgreSQL.
- Respaldo de archivos persistentes.
- Respaldo de variables y configuración Docker.
- Respaldo de scripts de despliegue.
- Respaldo de configuración de Nginx.
- Verificación de integridad mediante SHA256.
- Descarga de los respaldos hacia una máquina local.

La restauración completa de SportFlow sobre un VPS nuevo todavía no ha sido ejecutada ni validada.

Por lo tanto, los pasos de restauración se documentarán cuando se realice una migración real.

---

## 2. Alcance

Este procedimiento corresponde únicamente a SportFlow.

No incluye:

- Allcademy.
- n8n.
- Bases de datos de otros proyectos.
- Configuraciones Nginx pertenecientes a otros servicios.

---

## 3. Componentes necesarios para recuperar SportFlow

Para reconstruir SportFlow es necesario conservar los siguientes componentes.

### Código fuente

Repositorio:

```text
https://github.com/Souwg/VolleyballSystem
```

Rama utilizada en producción:

```text
develop
```

Ruta utilizada actualmente en el VPS:

```text
/opt/sportflow/app
```

Antes del respaldo realizado el 23/08/2026 se verificó:

```bash
cd /opt/sportflow/app
git status --short
git branch --show-current
```

Resultado:

```text
develop
```

`git status --short` no mostró archivos modificados.

Por esta razón, el directorio `/opt/sportflow/app` no fue incluido en el respaldo manual del servidor.

El código fuente se conserva en GitHub.

---

## 4. Base de datos

SportFlow utiliza:

```text
PostgreSQL 16 Alpine
```

Contenedor:

```text
sportflow-database
```

Base:

```text
sportflow
```

Usuario PostgreSQL:

```text
sportflow
```

La persistencia del contenedor está asociada al volumen Docker:

```text
sportflow-postgres-data
```

Ruta observada en el VPS:

```text
/var/lib/docker/volumes/sportflow-postgres-data/_data
```

Para la migración no se realizó una copia directa de esta carpeta.

Se utilizó `pg_dump`.

---

## 5. Respaldo manual de PostgreSQL

El 23/08/2026 se creó un respaldo manual actualizado de la base de datos.

Comando utilizado:

```bash
set -o pipefail

BACKUP="/opt/sportflow/backups/postgres/sportflow_manual_$(date +%Y-%m-%d_%H-%M-%S).sql.gz"

docker exec sportflow-database \
  pg_dump -U sportflow -d sportflow \
  | gzip > "$BACKUP"
```

Archivo generado:

```text
/opt/sportflow/backups/postgres/sportflow_manual_2026-08-23_00-51-15.sql.gz
```

Tamaño observado:

```text
42K
```

---

## 6. Verificación del respaldo PostgreSQL

Primero se verificó la integridad del archivo comprimido:

```bash
gzip -t /opt/sportflow/backups/postgres/sportflow_manual_2026-08-23_00-51-15.sql.gz
```

El archivo fue reconocido correctamente por `gzip`.

Después se verificó que el respaldo contuviera las tablas de SportFlow:

```bash
gunzip -c /opt/sportflow/backups/postgres/sportflow_manual_2026-08-23_00-51-15.sql.gz \
  | grep "^CREATE TABLE"
```

Se encontraron:

```text
24 tablas
```

Entre ellas:

```text
alembic_version
attendance
categories
clubs
match_events
match_players
match_sessions
match_substitutions
password_reset_tokens
payment_receipts
player_match_stats
player_payments
players
receipt_counters
refresh_tokens
team_players
teams
token_blocked_list
tournament_players
tournament_teams
tournaments
training_players
training_sessions
users
```

---

## 7. Descarga del respaldo PostgreSQL

El archivo fue descargado desde el VPS hacia una máquina Windows mediante `scp`.

Comando utilizado desde PowerShell:

```powershell
scp sportflowadmin@31.97.146.234:/opt/sportflow/backups/postgres/sportflow_manual_2026-08-23_00-51-15.sql.gz "$env:USERPROFILE\Downloads\"
```

Ubicación local:

```text
C:\Users\sansa\Downloads\sportflow_manual_2026-08-23_00-51-15.sql.gz
```

---

## 8. Verificación SHA256 de PostgreSQL

Hash obtenido en el VPS:

```text
5b24448f481fbe72d22cdedfb22a7e59032ba4447787e69a33b592f5e7c2fcac
```

Hash obtenido en Windows:

```text
5B24448F481FBE72D22CDEDFB22A7E59032BA4447787E69A33B592F5E7C2FCAC
```

Los hashes coinciden.

Esto confirma que el archivo descargado es idéntico al archivo generado en el VPS.

---

## 9. Archivos persistentes

Los archivos subidos por SportFlow se almacenan en:

```text
/opt/sportflow/uploads
```

Dentro del contenedor están disponibles en:

```text
/app/public/uploads
```

El montaje observado es:

```text
/opt/sportflow/uploads -> /app/public/uploads
```

Al momento del respaldo, el tamaño aproximado de esta carpeta era:

```text
67M
```

Esta carpeta contiene archivos persistentes como:

- Fotografías de jugadores.
- Logos.
- Recibos.
- Otros archivos subidos por SportFlow.

Estos archivos no forman parte del respaldo PostgreSQL.

---

## 10. Configuración Docker

La configuración de producción se encuentra en:

```text
/opt/sportflow/docker
```

Se verificó la existencia de:

```text
.env
Dockerfile
compose.yml
compose.yml.backup-20260802-131135
```

El archivo:

```text
/opt/sportflow/docker/.env
```

contiene información sensible.

No debe:

- Subirse a GitHub.
- Compartirse públicamente.
- Copiarse dentro de documentación.
- Mostrarse en logs o capturas sin revisar previamente su contenido.

---

## 11. Respaldo de configuración y archivos persistentes

Se creó el siguiente respaldo:

```text
/home/sportflowadmin/sportflow_server_2026-08-23.tar.gz
```

Comando utilizado:

```bash
cd /opt/sportflow

tar -czf /home/sportflowadmin/sportflow_server_2026-08-23.tar.gz \
  docker \
  uploads \
  deploy.sh \
  scripts \
  local-files \
  backups/backup_postgres.sh
```

El archivo generado tuvo un tamaño aproximado de:

```text
67M
```

Incluye:

```text
docker/
uploads/
deploy.sh
scripts/
local-files/
backups/backup_postgres.sh
```

Dentro de `docker/` se encuentran también:

```text
.env
compose.yml
Dockerfile
```

---

## 12. Verificación del respaldo del servidor

Se comprobó que el archivo pudiera ser leído:

```bash
tar -tzf /home/sportflowadmin/sportflow_server_2026-08-23.tar.gz > /dev/null
```

También se comprobó específicamente la presencia de:

```text
docker/.env
docker/compose.yml
docker/Dockerfile
uploads/
```

---

## 13. Descarga del respaldo del servidor

Desde PowerShell:

```powershell
scp sportflowadmin@31.97.146.234:/home/sportflowadmin/sportflow_server_2026-08-23.tar.gz "$env:USERPROFILE\Downloads\"
```

Ubicación local:

```text
C:\Users\sansa\Downloads\sportflow_server_2026-08-23.tar.gz
```

---

## 14. Verificación SHA256 del respaldo del servidor

Hash en el VPS:

```text
be80896bbeb2b1b170f012dae18d0fb6ca4c720aca092894415437a2964145a2
```

Hash en Windows:

```text
BE80896BBEB2B1B170F012DAE18D0FB6CA4C720ACA092894415437A2964145A2
```

Los hashes coinciden.

---

## 15. Configuración Nginx

SportFlow utiliza una configuración específica de Nginx ubicada en:

```text
/etc/nginx/sites-available/sportflow
```

También se decidió conservar la configuración global:

```text
/etc/nginx/nginx.conf
```

Se creó:

```text
/home/sportflowadmin/sportflow_nginx_2026-08-23.tar.gz
```

Comando:

```bash
sudo tar -czf /home/sportflowadmin/sportflow_nginx_2026-08-23.tar.gz \
  /etc/nginx/nginx.conf \
  /etc/nginx/sites-available/sportflow
```

Después se asignó el archivo al usuario:

```bash
sudo chown sportflowadmin:sportflowadmin \
  /home/sportflowadmin/sportflow_nginx_2026-08-23.tar.gz
```

Contenido verificado:

```text
etc/nginx/nginx.conf
etc/nginx/sites-available/sportflow
```

---

## 16. Descarga y verificación de Nginx

Desde PowerShell:

```powershell
scp sportflowadmin@31.97.146.234:/home/sportflowadmin/sportflow_nginx_2026-08-23.tar.gz "$env:USERPROFILE\Downloads\"
```

Hash en el VPS:

```text
0183d264d0f5100ecff0793977f36654e8b93553916843d1b37e9af3653e6af8
```

Hash en Windows:

```text
0183D264D0F5100ECFF0793977F36654E8B93553916843D1B37E9AF3653E6AF8
```

Los hashes coinciden.

---

## 17. Archivos conservados localmente

Después del procedimiento se dispone de:

```text
C:\Users\sansa\Downloads\
│
├── sportflow_manual_2026-08-23_00-51-15.sql.gz
├── sportflow_server_2026-08-23.tar.gz
└── sportflow_nginx_2026-08-23.tar.gz
```

### PostgreSQL

```text
sportflow_manual_2026-08-23_00-51-15.sql.gz
```

Contiene el respaldo de la base de datos.

### Servidor SportFlow

```text
sportflow_server_2026-08-23.tar.gz
```

Contiene:

```text
uploads
.env
compose.yml
Dockerfile
deploy.sh
scripts
local-files
backup_postgres.sh
```

### Nginx

```text
sportflow_nginx_2026-08-23.tar.gz
```

Contiene:

```text
nginx.conf
sites-available/sportflow
```

---

## 18. Elementos que no fueron respaldados en este procedimiento

### Código de `/opt/sportflow/app`

No se incluyó porque:

- El repositorio está almacenado en GitHub.
- Se verificó que la rama del VPS era `develop`.
- `git status --short` no mostró cambios locales.

### Volumen PostgreSQL en bruto

No se copió:

```text
/var/lib/docker/volumes/sportflow-postgres-data/_data
```

La base de datos fue respaldada mediante `pg_dump`.

### Certificados Let's Encrypt

Los certificados ubicados en:

```text
/etc/letsencrypt/
```

no fueron incluidos en este procedimiento.

---

## 19. Estado de recuperación

Actualmente se encuentran verificados:

| Componente                   | Estado                  |
| ---------------------------- | ----------------------- |
| Código en GitHub             | ✅ Verificado           |
| Rama `develop` en producción | ✅ Verificada           |
| Backup PostgreSQL            | ✅ Generado             |
| Integridad gzip              | ✅ Verificada           |
| Tablas dentro del backup     | ✅ Verificadas          |
| Backup descargado localmente | ✅                      |
| SHA256 PostgreSQL            | ✅ Coincide             |
| `/opt/sportflow/uploads`     | ✅ Respaldado           |
| `.env` de producción         | ✅ Respaldado           |
| `compose.yml`                | ✅ Respaldado           |
| `Dockerfile`                 | ✅ Respaldado           |
| `deploy.sh`                  | ✅ Respaldado           |
| Scripts auxiliares           | ✅ Respaldados          |
| Configuración Nginx          | ✅ Respaldada           |
| SHA256 backup servidor       | ✅ Coincide             |
| SHA256 Nginx                 | ✅ Coincide             |
| Restauración PostgreSQL      | ⏳ Pendiente de validar |
| Restauración de uploads      | ⏳ Pendiente de validar |
| Despliegue sobre VPS nuevo   | ⏳ Pendiente de validar |
| Cambio de DNS                | ⏳ Pendiente            |
| HTTPS sobre VPS nuevo        | ⏳ Pendiente de validar |

---

## 20. Migración hacia un VPS nuevo

La migración completa hacia un VPS nuevo todavía no ha sido ejecutada.

Por lo tanto, este documento no establece todavía un procedimiento definitivo de restauración.

Cuando se realice la migración deberán documentarse y validarse como mínimo:

```text
Nuevo VPS
    |
    ├── Preparación del servidor
    ├── Recuperación del código desde GitHub
    ├── Recuperación de configuración Docker
    ├── Recuperación del .env
    ├── Recuperación de uploads
    ├── Restauración de PostgreSQL
    ├── Inicio de los contenedores
    ├── Configuración de Nginx
    ├── Configuración del dominio
    ├── Configuración HTTPS
    └── Pruebas funcionales
```

Los comandos definitivos deberán añadirse únicamente después de haber sido ejecutados y comprobados.

---

## 21. Regla de seguridad

Los respaldos que contienen:

```text
.env
```

deben considerarse archivos sensibles.

No deben almacenarse en repositorios públicos ni compartirse sin protección.

---

## 22. Estado actual del documento

| Campo                          | Valor                            |
| ------------------------------ | -------------------------------- |
| Documento                      | `07-recuperacion-y-migracion.md` |
| Proyecto                       | SportFlow                        |
| Estado del respaldo            | Verificado                       |
| Estado de restauración         | Pendiente de validar             |
| Fecha del respaldo documentado | 23/08/2026                       |

---

## 23. Procedimiento de respaldo conjunto preparado

La FASE 0.16 añadió al repositorio:

```text
scripts/backup_sportflow.sh
```

Este script prepara en una misma ejecución el dump de PostgreSQL y el archivo
de `/opt/sportflow/uploads`. No incluye `.env`, claves ni configuración privada.
La copia manual descrita en las secciones anteriores se conserva como registro
histórico; no reemplaza la necesidad de ejecutar periódicamente el respaldo
conjunto.

Antes de usarlo en producción:

1. Revisar el script contra el `compose.yml` instalado.
2. Confirmar que el servicio de PostgreSQL se llama `database`.
3. Confirmar el bind mount
   `/opt/sportflow/uploads:/app/public/uploads`.
4. Ejecutarlo primero en una ventana de mantenimiento y revisar su salida.
5. Copiar el conjunto verificado a una ubicación fuera del VPS.
6. Actualizar cron y el respaldo previo al despliegue solo después de esa prueba.

Ejecución prevista desde el checkout de producción:

```bash
cd /opt/sportflow/app
./scripts/backup_sportflow.sh
```

Las rutas y nombres pueden ajustarse mediante `SPORTFLOW_ROOT`, `COMPOSE_DIR`,
`COMPOSE_FILE`, `ENV_FILE`, `UPLOADS_DIR`, `BACKUP_ROOT`,
`BACKUP_RETENTION_DAYS` y `DATABASE_SERVICE`. No es necesario exportar
contraseñas: Docker Compose carga `/opt/sportflow/docker/.env`.

## 24. Restauración del conjunto

Este procedimiento debe ensayarse en un entorno aislado antes de aplicarlo a
producción. Requiere el código y la configuración Docker ya instalados, además
de un conjunto completo creado por `backup_sportflow.sh`.

### 24.1 Verificar el respaldo

```bash
cd /ruta/al/sportflow_YYYY-MM-DD_HH-MM-SSZ
sha256sum -c SHA256SUMS
tar -tzf uploads.tar.gz > /dev/null
```

Comprobar el dump con la misma versión principal de PostgreSQL usada por el
servicio:

```bash
docker compose \
  --env-file /opt/sportflow/docker/.env \
  -f /opt/sportflow/docker/compose.yml \
  exec -T database \
  sh -c 'exec pg_restore --list' \
  < postgres.dump > /dev/null
```

No continuar si falla cualquiera de estas verificaciones.

### 24.2 Detener escrituras y restaurar PostgreSQL

Detener únicamente la aplicación para impedir escrituras durante toda la
restauración:

```bash
docker compose \
  --env-file /opt/sportflow/docker/.env \
  -f /opt/sportflow/docker/compose.yml \
  stop app
```

Restaurar primero la base de datos:

```bash
docker compose \
  --env-file /opt/sportflow/docker/.env \
  -f /opt/sportflow/docker/compose.yml \
  exec -T database \
  sh -c 'exec pg_restore --clean --if-exists --no-owner --no-privileges --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
  < postgres.dump
```

Este comando reemplaza objetos de la base destino. Debe utilizarse solo sobre
la base aislada o sobre el destino de recuperación previamente identificado.

### 24.3 Restaurar uploads

Con `app` todavía detenido, conservar temporalmente el directorio actual como
resguardo operativo y extraer el archivo en un directorio nuevo:

```bash
mv /opt/sportflow/uploads /opt/sportflow/uploads.before-restore
mkdir -p /opt/sportflow/uploads
tar -xzf uploads.tar.gz -C /opt/sportflow/uploads
```

Revisar propietario y permisos según el usuario configurado en el contenedor
de producción. No se documenta un UID fijo porque el Dockerfile de producción
se administra fuera de este repositorio. El servicio `app` debe poder leer los
PDF existentes y escribir nuevos archivos dentro de `uploads/receipts`.

### 24.4 Iniciar y verificar

```bash
docker compose \
  --env-file /opt/sportflow/docker/.env \
  -f /opt/sportflow/docker/compose.yml \
  start app
```

Después de iniciar:

1. Confirmar que la aplicación responde y que las migraciones corresponden al
   código restaurado.
2. Consultar un pago con recibo y comprobar que su `pdf_url` tenga un archivo
   equivalente bajo `/opt/sportflow/uploads/receipts`.
3. Abrir el recibo desde una sesión autorizada.
4. Generar un enlace compartible nuevo y comprobar que sirve el PDF. Los links
   firmados existentes pueden haber expirado y dependen del mismo
   `TOKEN_SECRET`; no forman parte del archivo PDF.
5. Generar un recibo de prueba en el entorno aislado y confirmar que el
   contenedor puede escribir en `uploads/receipts`.

No eliminar `uploads.before-restore` hasta terminar estas comprobaciones. Su
eliminación es una acción operativa separada.

## 25. Consistencia entre recibos y archivos

`PaymentReceipt.pdf_url` se guarda en PostgreSQL, mientras que el PDF se guarda
en `public/uploads/receipts`, que en producción corresponde a
`/opt/sportflow/uploads/receipts`. Por eso ambos elementos deben pertenecer al
mismo conjunto de respaldo.

Para un respaldo consistente se recomienda detener temporalmente `app`, crear
el conjunto y volver a iniciar la aplicación. El script no detiene servicios de
forma automática. Así evita cambiar el estado operativo del servidor sin una
decisión explícita del administrador.

La restauración completa todavía no ha sido ejecutada en el VPS de producción.
Los pasos anteriores quedaron preparados y la restauración de archivos se
validó localmente durante la FASE 0.16; la tabla de la sección 19 mantiene el
estado de producción como pendiente.
