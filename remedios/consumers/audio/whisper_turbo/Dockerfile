FROM python:3.10-slim

ARG APP_SRC=remedios
ENV VENV=/app/remedios/.venv
ENV PYTHONPATH=/app

# Dependencias base y ffmpeg para manejar audio
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements primero para cache
COPY ${APP_SRC}/requirements.txt ./remedios/
COPY ${APP_SRC}/consumers/audio/whisper_turbo/requirements.txt ./remedios/requirements_audio.txt

# Crear venv e instalar dependencias en modo CPU
RUN python3 -m venv $VENV \
    && $VENV/bin/pip install --upgrade pip setuptools \
    && $VENV/bin/pip install --no-cache-dir -r remedios/requirements_audio.txt \
    && $VENV/bin/pip install --no-cache-dir -r remedios/requirements.txt

# Copiar código
COPY ${APP_SRC}/ /app/remedios

WORKDIR /app
ENV PATH="/app/remedios/.venv/bin:${PATH}"
ENV WHISPER_BACKEND=turbo

# Ejecutar servicio HTTP de audio (backend turbo)
CMD ["/app/remedios/.venv/bin/python", "-m", "remedios.consumers.audio.whisper_turbo.service"]
