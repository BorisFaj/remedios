#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_FILE="${ROOT_DIR}/zordon/.secrets"

if [[ ! -f "${SECRETS_FILE}" ]]; then
  echo "No se encontró ${SECRETS_FILE}. Crea el fichero con ORACLE_*." >&2
  exit 1
fi

load_secrets() {
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    key="$(echo "$key" | xargs)"
    value="$(echo "$value" | xargs)"
    if [[ "$value" =~ ^\".*\"$ ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" =~ ^\'.*\'$ ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
  done < "${SECRETS_FILE}"
}

load_secrets

if [[ -z "${ORACLE_WALLET_PATH:-}" ]]; then
  echo "ORACLE_WALLET_PATH no está definido en ${SECRETS_FILE}." >&2
  exit 1
fi

if [[ -z "${ORACLE_DSN:-}" ]]; then
  if [[ -f "${ORACLE_WALLET_PATH}/tnsnames.ora" ]]; then
    ORACLE_DSN="$(awk 'match($0,/^[[:space:]]*([A-Za-z0-9._-]+)[[:space:]]*=/,a){print a[1]; exit}' "${ORACLE_WALLET_PATH}/tnsnames.ora")"
    export ORACLE_DSN
  fi
fi

if [[ -z "${ORACLE_DSN:-}" ]]; then
  echo "ORACLE_DSN no definido y no se pudo inferir desde tnsnames.ora." >&2
  exit 1
fi

cd "${ROOT_DIR}"
exec alembic "$@"
