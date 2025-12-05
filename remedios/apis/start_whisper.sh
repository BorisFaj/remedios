#!/usr/bin/env sh
set -euo pipefail

MODEL_PATH=${WHISPER_MODEL:-/models/ggml-large-v3-turbo-q5_0.bin}
MODEL_DIR=$(dirname "$MODEL_PATH")
mkdir -p "$MODEL_DIR"

# Descarga previa del modelo si no existe
if [ ! -f "$MODEL_PATH" ]; then
  /app/remedios/.venv/bin/python - <<'PY'
import os
from pathlib import Path
from huggingface_hub import hf_hub_download

repo = os.getenv("WHISPER_MODEL_REPO", "ggerganov/whisper.cpp")
filename = os.path.basename(os.getenv("WHISPER_MODEL", "ggml-large-v3-turbo-q5_0.bin"))
dest = Path(os.getenv("WHISPER_MODEL", f"/models/{filename}"))
dest.parent.mkdir(parents=True, exist_ok=True)

path = hf_hub_download(repo_id=repo, filename=filename, local_dir=str(dest.parent), local_dir_use_symlinks=False)
if Path(path) != dest:
    dest.write_bytes(Path(path).read_bytes())
print(f"Modelo disponible en {dest}")
PY
fi

PORT=${WHISPER_SERVER_PORT:-9000}
LANG=${WHISPER_LANGUAGE:-es}

# Lanzar whisper-server en segundo plano
/usr/local/bin/whisper-server -m "$MODEL_PATH" -p "$PORT" -l "$LANG" --host 0.0.0.0 --no-ssl >/tmp/whisper-server.log 2>&1 &
SERVER_PID=$!

# Esperar a que el puerto esté arriba (máx 120s)
for i in $(seq 1 120); do
  if nc -z 127.0.0.1 "$PORT" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! nc -z 127.0.0.1 "$PORT" >/dev/null 2>&1; then
  echo "whisper-server no arrancó en el puerto $PORT" >&2
  cat /tmp/whisper-server.log >&2 || true
  kill "$SERVER_PID" 2>/dev/null || true
  exit 1
fi

exec /app/remedios/.venv/bin/python -m remedios.apis.audio_service
