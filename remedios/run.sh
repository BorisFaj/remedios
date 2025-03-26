#!/bin/bash

# Cargar variables desde .secrets (en la raíz del repo)
SECRETS_PATH="$(dirname "$0")/../.secrets"
source "$SECRETS_PATH"

FORCE_BUILD=false

# Procesar argumentos
for arg in "$@"; do
  if [[ "$arg" == "--build" ]]; then
    FORCE_BUILD=true
  elif [[ "$arg" == "texto" ]]; then
    echo "📦 Ejecutando servicio 'texto' con docker-compose..."
    docker compose -f docker-compose.yml up -d
    exit 0
  elif [[ "$arg" == "audio" ]]; then
    IMAGE_NAME="reme-audio"
    KAFKA_TOPIC="whatsapp-audio"
    KAFKA_GROUP_ID="audio"
    BUILD_FILE="Dockerfile_audio"
    CONTAINER_NAME="remedios-audio"
  else
    echo "❌ Argumento no reconocido: $arg"
    echo "Uso: ${0##*/} [--build] [audio|texto]"
    exit 1
  fi
done

# Si es audio y se especificó
if [[ -n "$IMAGE_NAME" ]]; then
  if [[ "$FORCE_BUILD" == true || "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]]; then
    echo "🔧 Construyendo imagen '$IMAGE_NAME' usando '$BUILD_FILE'..."
    docker build -t $IMAGE_NAME . -f "$BUILD_FILE" --no-cache --progress=plain
  else
    echo "✅ Imagen '$IMAGE_NAME' ya existe. Usa --build para forzar reconstrucción."
  fi

  if docker ps -a --format '{{.Names}}' | grep -Eq "^$CONTAINER_NAME\$"; then
    echo "🧹 Contenedor '$CONTAINER_NAME' ya existe. Eliminándolo..."
    docker rm -fv $CONTAINER_NAME
  fi

  echo "⚙️ Usando KAFKA_TOPIC: $KAFKA_TOPIC"
  echo "🚀 Iniciando contenedor '$CONTAINER_NAME'..."
  docker run --gpus all -d --name $CONTAINER_NAME \
    --env-file "$SECRETS_PATH" \
    -e KAFKA_TOPIC="$KAFKA_TOPIC" \
    -e KAFKA_GROUP_ID="$KAFKA_GROUP_ID" \
    -v "$HOME/.cache/huggingface/hub/:$HOME/.cache/huggingface/hub/" \
    $IMAGE_NAME
fi
