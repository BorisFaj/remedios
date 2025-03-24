#!/bin/bash

# Cargar variables desde .secrets
source "$(dirname "$0")/../.secrets"  # Ojo! Esta en la raíz del repo, lejos de Dockerfiles

# Inicializar variables
FORCE_BUILD=false
IMAGE_NAME=""
KAFKA_TOPIC=""
CONTAINER_NAME=""
BUILD_FILE=""

# Procesar argumentos
for arg in "$@"; do
  if [[ "$arg" == "--build" ]]; then
    FORCE_BUILD=true
  elif [[ "$arg" == "audio" ]]; then
    IMAGE_NAME="reme-audio"
    KAFKA_TOPIC="whatsapp-audio"
    BUILD_FILE="Dockerfile_audio"
    CONTAINER_NAME="remedios-audio"
  elif [[ "$arg" == "texto" ]]; then
    IMAGE_NAME="reme-texto"
    KAFKA_TOPIC="whatsapp-text"
    BUILD_FILE="Dockerfile_text"
    CONTAINER_NAME="remedios-texto"
  else
    echo "Argumento no reconocido: $arg"
    echo "Uso: ${0##*/} [--build] [audio|texto]"
    exit 1
  fi
done

# Verificar si se seleccionó una opción válida
if [[ -z "$IMAGE_NAME" || -z "$KAFKA_TOPIC" || -z "$BUILD_FILE" ]]; then
  echo "Error: No se especificó una opción válida (audio o texto)."
  echo "Uso: ${0##*/} [--build] [audio|texto]"
  exit 1
fi

# Construir imagen si se fuerza o no existe
if [[ "$FORCE_BUILD" == true || "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]]; then
  echo "🔧 Construyendo imagen '$IMAGE_NAME' usando '$BUILD_FILE'..."
  docker system prune -a --volumes -f
  docker build -t $IMAGE_NAME . -f "$BUILD_FILE" --no-cache --progress=plain
else
  echo "✅ Imagen '$IMAGE_NAME' ya existe. Usa --build para forzar reconstrucción."
fi

# Eliminar contenedor existente
if docker ps -a --format '{{.Names}}' | grep -Eq "^$CONTAINER_NAME\$"; then
  echo "🧹 Contenedor '$CONTAINER_NAME' ya existe. Eliminándolo (con volúmenes)..."
  docker rm -fv $CONTAINER_NAME
fi

# Configurar variable KAFKA_TOPIC
echo "⚙️ Usando KAFKA_TOPIC: $KAFKA_TOPIC"

# Iniciar contenedor
echo "🚀 Iniciando contenedor '$CONTAINER_NAME'..."
docker run --gpus all -d --name $CONTAINER_NAME \
  --env-file "$(dirname "$0")/../.secrets" \
  -e KAFKA_TOPIC="$KAFKA_TOPIC" \
  -v "$HOME/.cache/huggingface/hub/:$HOME/.cache/huggingface/hub/" \
  $IMAGE_NAME

#docker run --gpus all -it --entrypoint /bin/sh --env-file ../.secrets -e KAFKA_TOPIC=whatsapp-text -v $HOME/.cache/huggingface/hub/:$HOME/.cache/huggingface/hub/ reme-texto