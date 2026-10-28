# Sincronización automática de pagos

## Objetivo

Esta automatización ejecuta diariamente el comando administrativo existente:

```text
flask sync-monthly-payments --all
```

El cron no calcula pagos. El flujo conserva una sola implementación financiera:

```text
cron del host
  -> scripts/sync_monthly_payments.sh
  -> docker compose exec -T app
  -> flask sync-monthly-payments --all
  -> execute_monthly_sync()
```

## Infraestructura revisada

La infraestructura de producción no se encuentra dentro de este repositorio,
pero está documentada con estas rutas y nombres:

| Elemento | Valor |
|---|---|
| Checkout | `/opt/sportflow/app` |
| Directorio Compose | `/opt/sportflow/docker` |
| Archivo Compose | `/opt/sportflow/docker/compose.yml` |
| Archivo de variables | `/opt/sportflow/docker/.env` |
| Servicio de aplicación | `app` |
| Contenedor de aplicación | `sportflow-app` |
| Servicio PostgreSQL | `database` |
| Directorio de logs del host | `/opt/sportflow/logs` |

Compose carga las variables privadas desde su archivo `.env`. El wrapper no
contiene ni carga manualmente contraseñas, JWT o claves.

## Horario y timezone

La documentación operacional actual sitúa el VPS y los respaldos en UTC. El
backend también resuelve las fechas financieras mediante UTC y no existe una
timezone configurable por Club.

La propuesta ejecuta la sincronización a las **03:15 UTC**, una vez al día. Se
elige ese horario para mantenerla separada del respaldo diario documentado a
las 02:00 UTC. La plantilla fija `CRON_TZ=UTC` para no depender de un cambio
accidental de timezone del host.

El cron no calcula `as_of`: el comando Flask continúa resolviendo una sola
fecha y entregándola al servicio financiero.

## Wrapper

Ruta versionada:

```text
/opt/sportflow/app/scripts/sync_monthly_payments.sh
```

El wrapper:

- usa el modo estricto de Bash;
- valida Docker, Docker Compose, el checkout, el Compose y su `.env`;
- comprueba que el servicio `app` esté levantado;
- cambia al checkout de producción;
- ejecuta exactamente `flask sync-monthly-payments --all` dentro de `app`;
- registra inicio y fin en UTC;
- conserva el exit code del comando Flask.

Los valores operativos pueden sobrescribirse para pruebas aisladas mediante
`SPORTFLOW_ROOT`, `APP_DIR`, `COMPOSE_DIR`, `COMPOSE_FILE`, `ENV_FILE`,
`APP_SERVICE` y `DOCKER_BIN`. Ninguna de estas variables contiene secretos en
el script.

## Plantilla cron

La plantilla versionada está en:

```text
scripts/cron/sportflow-monthly-payments.cron.example
```

Su entrada efectiva es:

```cron
CRON_TZ=UTC
15 3 * * * flock -n /opt/sportflow/logs/monthly-payments.lock /opt/sportflow/app/scripts/sync_monthly_payments.sh >> /opt/sportflow/logs/monthly-payments.log 2>&1
```

`flock -n` evita que dos ejecuciones programadas se solapen. El índice único de
mensualidades y los savepoints siguen protegiendo la base de datos si la API
manual y el cron coinciden; el lock operativo no sustituye esa protección.

## Logs y rotación

Cron captura stdout y stderr en:

```text
/opt/sportflow/logs/monthly-payments.log
```

El comando ya informa fecha, Clubs procesados y omitidos, mensualidades
creadas, pagos marcados vencidos, advertencias y errores. El wrapper agrega la
hora de inicio, la hora de finalización y el exit code cuando existe un fallo.

No hay una configuración logrotate versionada actualmente. Antes de activar el
cron puede instalarse esta configuración del host, después de revisar la
política general del VPS:

```text
/opt/sportflow/logs/monthly-payments.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

Ese bloque es una plantilla. Esta fase no escribe en `/etc/logrotate.d/`.

## Instalación posterior

La instalación es una operación de producción y debe realizarse únicamente
después de desplegar y validar el wrapper:

1. Confirmar que `/opt/sportflow/logs` existe y es escribible por el usuario
   operativo.
2. Confirmar `docker compose version` y `command -v flock` con ese mismo
   usuario.
3. Confirmar que el checkout contiene el wrapper desplegado y ejecutable.
4. Ejecutar manualmente el wrapper y revisar su salida:

   ```bash
   /opt/sportflow/app/scripts/sync_monthly_payments.sh
   ```

5. Instalar el contenido de la plantilla en el crontab del usuario operativo.
6. Instalar la configuración de logrotate revisada para ese VPS.
7. Verificar al día siguiente el log, el exit code operacional y los totales.

No se ejecutó `crontab -e`, no se modificó `/etc/crontab` ni se creó un archivo
en `/etc/cron.d/` durante esta fase.

## Comportamiento operativo

- `--all` procesa únicamente Clubs activos y omite los suspendidos.
- Una configuración incompleta, una jugadora inactiva o un Club suspendido son
  omisiones esperadas, no fallos globales.
- Cada Club mantiene su propia transacción. El fallo de uno hace rollback de
  ese Club y permite continuar con los demás.
- Si hubo uno o más errores reales, el comando termina con exit code no cero y
  el wrapper lo propaga.
- Owner y Staff conservan la sincronización manual de Payments como mecanismo
  de actualización inmediata y recuperación.
- Los previews continúan siendo de solo lectura.
- Los GET de Payments consultan únicamente el estado persistido. La creación de
  mensualidades y la transición de `pending` a `overdue` dependen de una
  sincronización explícita.

## Advertencia de despliegue para FASE 2.14F

No desplegar FASE 2.14F en producción hasta confirmar que al menos uno de estos
mecanismos está operativo:

- el cron automático de FASE 2.14E está instalado y fue probado; o
- la sincronización manual de FASE 2.14D está disponible y fue verificada.

La configuración recomendada para producción es mantener el cron probado y la
sincronización manual como mecanismo de recuperación. Esta fase no instala ni
activa el cron.
