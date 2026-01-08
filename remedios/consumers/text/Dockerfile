FROM python:3.10-slim

ARG APP_SRC=remedios
ENV POETRY_VENV=/app/remedios/.venv
ENV PYTHONPATH=/app

# Instalar dependencias básicas (build deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Copiar solo requirements para aprovechar cache
WORKDIR /app
COPY ${APP_SRC}/requirements.txt /app/remedios/requirements.txt
COPY ${APP_SRC}/consumers/text/requirements.txt /app/remedios/consumers/text/requirements.txt

# Crear entorno virtual e instalar deps
RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install --upgrade pip setuptools \
    && $POETRY_VENV/bin/pip install --no-cache-dir -r /app/remedios/requirements.txt \
    && $POETRY_VENV/bin/pip install --no-cache-dir -r /app/remedios/consumers/text/requirements.txt

# Copiar código
COPY ${APP_SRC}/ /app/remedios

WORKDIR /app

# Ejecutar
CMD ["/app/remedios/.venv/bin/python", "-m", "remedios.consumers.text.consumer"]
