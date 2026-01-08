#!/usr/bin/env bash
set -euo pipefail

MODEL="${WHISPER_MODEL:-/app/ggml-large-v3-turbo-q5_0.bin}"
REPO="${WHISPER_MODEL_REPO:-ggerganov/whisper.cpp}"

# En modo healthcheck no descargamos modelo ni arrancamos whisper-server.
if [ "${HEALTHCHECK_ONLY:-}" = "1" ]; then
  exec /usr/local/bin/whispercpp-consumer
fi

# Descarga modelo si no existe
if [ ! -f "$MODEL" ]; then
  mkdir -p "$(dirname "$MODEL")"
  URL="https://huggingface.co/${REPO}/resolve/main/$(basename "$MODEL")"
  echo "Descargando modelo ${MODEL} de ${URL}"
  curl -fL "$URL" -o "$MODEL"
fi

exec /usr/local/bin/whispercpp-consumer
