FROM python:3.10-slim

ENV POETRY_VENV=/remedios/.venv

# Instalar dependencias básicas (build deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Copiar solo requirements para aprovechar cache
WORKDIR /remedios
COPY apps/remetext/requirements.txt ./apps/remetext/requirements.txt

# Crear entorno virtual e instalar deps
RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install --upgrade pip setuptools \
    && $POETRY_VENV/bin/pip install --no-cache-dir -r apps/remetext/requirements.txt

# Copiar código
COPY apps ./apps

# Ejecutar
CMD ["/remedios/.venv/bin/python", "-m", "apps.remetext.service"]
