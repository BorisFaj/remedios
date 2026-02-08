FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tzdata \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir oci

WORKDIR /app
COPY remedios/services/openclaw/openclaw_snapshot.py /app/openclaw_snapshot.py

CMD ["python", "/app/openclaw_snapshot.py", "--help"]
