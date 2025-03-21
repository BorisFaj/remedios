#!/bin/bash

source "$(dirname "$0")/../.secrets"  # Ojo! Esta en la raiz del repo, lejos de Dockerfiles

IMAGE_NAME="remedios-app"
CONTAINER_NAME="remedios"
FORCE_BUILD=false

for arg in "$@"; do
  if [[ "$arg" == "--build" ]]; then
    FORCE_BUILD=true
  fi
done

if [[ "$FORCE_BUILD" == true || "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]]; then
  echo "🔧 Construyendo imagen '$IMAGE_NAME'..."
  docker build -t $IMAGE_NAME . --no-cache
else
  echo "✅ Imagen '$IMAGE_NAME' ya existe. Usa --build para forzar reconstrucción."
fi

if docker ps -a --format '{{.Names}}' | grep -Eq "^$CONTAINER_NAME\$"; then
  echo "🧹 Contenedor '$CONTAINER_NAME' ya existe. Eliminándolo (con volúmenes)..."
  docker rm -fv $CONTAINER_NAME
fi

echo "🚀 Iniciando contenedor '$CONTAINER_NAME'..."
docker run --gpus all -d --name $CONTAINER_NAME \
  --env-file "$(dirname "$0")/../.secrets" \
  -v "$HOME/.cache/huggingface/hub/:$HOME/.cache/huggingface/hub/" \
  $IMAGE_NAME
