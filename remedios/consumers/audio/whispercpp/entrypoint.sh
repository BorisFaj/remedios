#!/usr/bin/env bash
set -euo pipefail

MODEL="${WHISPER_MODEL:-/app/ggml-large-v3-turbo-q5_0.bin}"
REPO="${WHISPER_MODEL_REPO:-ggerganov/whisper.cpp}"

# Descarga modelo si no existe
if [ ! -f "$MODEL" ]; then
  mkdir -p "$(dirname "$MODEL")"
  URL="https://huggingface.co/${REPO}/resolve/main/$(basename "$MODEL")"
  echo "Descargando modelo ${MODEL} de ${URL}"
  curl -fL "$URL" -o "$MODEL"
fi

exec /usr/local/bin/whispercpp-consumer
