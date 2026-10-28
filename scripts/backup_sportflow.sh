#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

SPORTFLOW_ROOT="${SPORTFLOW_ROOT:-/opt/sportflow}"
COMPOSE_DIR="${COMPOSE_DIR:-${SPORTFLOW_ROOT}/docker}"
COMPOSE_FILE="${COMPOSE_FILE:-${COMPOSE_DIR}/compose.yml}"
ENV_FILE="${ENV_FILE:-${COMPOSE_DIR}/.env}"
UPLOADS_DIR="${UPLOADS_DIR:-${SPORTFLOW_ROOT}/uploads}"
BACKUP_ROOT="${BACKUP_ROOT:-${SPORTFLOW_ROOT}/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
DATABASE_SERVICE="${DATABASE_SERVICE:-database}"
DOCKER_BIN="${DOCKER_BIN:-docker}"

fail() {
    printf 'ERROR: %s\n' "$1" >&2
    exit 1
}

for command_name in "$DOCKER_BIN" tar sha256sum find flock date; do
    command -v "$command_name" >/dev/null 2>&1 \
        || fail "No se encontró el comando requerido: $command_name"
done

[[ "$BACKUP_RETENTION_DAYS" =~ ^[0-9]+$ ]] \
    || fail "BACKUP_RETENTION_DAYS debe ser un entero no negativo"

[[ -f "$COMPOSE_FILE" ]] \
    || fail "No existe el archivo Compose: $COMPOSE_FILE"
[[ -f "$ENV_FILE" ]] \
    || fail "No existe el archivo de variables: $ENV_FILE"
[[ -d "$UPLOADS_DIR" ]] \
    || fail "No existe el directorio de uploads: $UPLOADS_DIR"

mkdir -p "$BACKUP_ROOT"

exec 9>"${BACKUP_ROOT}/.backup.lock"
flock -n 9 || fail "Ya existe otro respaldo de SportFlow en ejecución"

timestamp="$(date -u +%Y-%m-%d_%H-%M-%SZ)"
backup_name="sportflow_${timestamp}"
staging_dir="${BACKUP_ROOT}/.${backup_name}.tmp"
final_dir="${BACKUP_ROOT}/${backup_name}"

[[ ! -e "$staging_dir" && ! -e "$final_dir" ]] \
    || fail "Ya existe un respaldo con la marca de tiempo $timestamp"

cleanup_staging() {
    status=$?

    if [[ $status -ne 0 && -n "${staging_dir:-}" && -d "$staging_dir" ]]; then
        rm -rf -- "$staging_dir"
    fi

    exit "$status"
}

trap cleanup_staging EXIT

mkdir "$staging_dir"

printf 'Creando dump de PostgreSQL...\n'
"$DOCKER_BIN" compose \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    exec -T "$DATABASE_SERVICE" \
    sh -c 'exec pg_dump --format=custom --no-owner --no-privileges --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
    > "${staging_dir}/postgres.dump"

[[ -s "${staging_dir}/postgres.dump" ]] \
    || fail "El dump de PostgreSQL quedó vacío"

printf 'Verificando estructura del dump...\n'
"$DOCKER_BIN" compose \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    exec -T "$DATABASE_SERVICE" \
    sh -c 'exec pg_restore --list' \
    < "${staging_dir}/postgres.dump" \
    > /dev/null

printf 'Archivando archivos persistentes...\n'
tar -C "$UPLOADS_DIR" -czf "${staging_dir}/uploads.tar.gz" .
tar -tzf "${staging_dir}/uploads.tar.gz" > /dev/null

cat > "${staging_dir}/MANIFEST.txt" <<EOF
backup_name=${backup_name}
created_at_utc=${timestamp}
database_format=PostgreSQL custom dump
uploads_source=${UPLOADS_DIR}
EOF

(
    cd "$staging_dir"
    sha256sum postgres.dump uploads.tar.gz MANIFEST.txt > SHA256SUMS
    sha256sum -c SHA256SUMS > /dev/null
)

chmod 600 "${staging_dir}"/*
mv "$staging_dir" "$final_dir"
staging_dir=""

find "$BACKUP_ROOT" \
    -mindepth 1 \
    -maxdepth 1 \
    -type d \
    -name 'sportflow_????-??-??_??-??-??Z' \
    -mtime "+${BACKUP_RETENTION_DAYS}" \
    -exec rm -rf -- {} +

printf 'Respaldo verificado: %s\n' "$final_dir"
