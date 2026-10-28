#!/usr/bin/env bash

set -Eeuo pipefail

SPORTFLOW_ROOT="${SPORTFLOW_ROOT:-/opt/sportflow}"
APP_DIR="${APP_DIR:-${SPORTFLOW_ROOT}/app}"
COMPOSE_DIR="${COMPOSE_DIR:-${SPORTFLOW_ROOT}/docker}"
COMPOSE_FILE="${COMPOSE_FILE:-${COMPOSE_DIR}/compose.yml}"
ENV_FILE="${ENV_FILE:-${COMPOSE_DIR}/.env}"
APP_SERVICE="${APP_SERVICE:-app}"
DOCKER_BIN="${DOCKER_BIN:-docker}"

fail() {
    printf 'ERROR: %s\n' "$1" >&2
    exit 1
}

command -v "$DOCKER_BIN" >/dev/null 2>&1 \
    || fail "No se encontró Docker: $DOCKER_BIN"
command -v date >/dev/null 2>&1 \
    || fail "No se encontró el comando requerido: date"

"$DOCKER_BIN" compose version >/dev/null 2>&1 \
    || fail "Docker Compose no está disponible"

[[ -d "$APP_DIR" ]] \
    || fail "No existe el checkout de SportFlow: $APP_DIR"
[[ -f "$COMPOSE_FILE" ]] \
    || fail "No existe el archivo Compose: $COMPOSE_FILE"
[[ -f "$ENV_FILE" ]] \
    || fail "No existe el archivo de variables: $ENV_FILE"

compose_args=(
    compose
    --env-file "$ENV_FILE"
    -f "$COMPOSE_FILE"
)

running_services="$({
    "$DOCKER_BIN" "${compose_args[@]}" \
        ps --status running --services "$APP_SERVICE"
} 2>&1)" || fail "No se pudo consultar el servicio Compose $APP_SERVICE: $running_services"

service_is_running=false

while IFS= read -r service_name; do
    if [[ "$service_name" == "$APP_SERVICE" ]]; then
        service_is_running=true
        break
    fi
done <<< "$running_services"

[[ "$service_is_running" == true ]] \
    || fail "El servicio Compose $APP_SERVICE no está levantado"

cd "$APP_DIR"

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '[%s] Iniciando sincronización mensual automática\n' "$started_at"

status=0

"$DOCKER_BIN" "${compose_args[@]}" \
    exec -T "$APP_SERVICE" \
    flask sync-monthly-payments --all \
    || status=$?

finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ $status -eq 0 ]]; then
    printf '[%s] Sincronización mensual finalizada correctamente\n' \
        "$finished_at"
else
    printf '[%s] Sincronización mensual finalizó con error (exit=%s)\n' \
        "$finished_at" "$status" >&2
fi

exit "$status"
