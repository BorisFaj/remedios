# Remedios

Ingesta de mensajes de WhatsApp con un webhook Flask que encola en Kafka y dos servicios que procesan texto y audio reutilizando un núcleo común.

## Estructura
- `apps/webhook/`: servidor Flask del webhook (`server.py`), Dockerfile y requirements propios.
- `apps/consumer/`: consumidor Kafka central (`super_consumer.py`) y utilidades adicionales (`whatsapp_consumer.py`), junto con Dockerfiles de los consumidores.
- `apps/remetext/`: handler y servicio HTTP para mensajes de texto.
- `apps/remeaudio/`: handler para mensajes de audio y transcripción.
- `apps/common/`: lógica compartida (mensajería, WhatsApp helpers, chat, TTS/STT, logging).
- `infra/k8s/`: manifiestos de Kubernetes y configuraciones (`remedios.yaml`, `kafka.yaml`, `traefik-acme.yaml`, etc.).
- `infra/ansible/`: playbooks de aprovisionamiento y despliegue.
- `infra/scripts/`: bootstrap de k3s/Tailscale (`master-init.sh`, `node-init.sh`). Esperan un fichero `.secrets` en `infra/.secrets`.
- `ops/`: herramientas locales como `docker-compose.yml` y `run.sh`.

## Flujo de mensajes
1. **Webhook** (`apps/webhook/server.py`): verifica el token de suscripción y publica el payload en Kafka (`whatsapp-text` o `whatsapp-audio`).
2. **Consumer** (`apps/consumer/super_consumer.py`): consume del topic configurado y deriva al handler de texto (`apps.remetext`) o audio (`apps.remeaudio`).
3. **Handlers**: ambos usan `apps.common.messaging` para parsear el payload y `apps.common.whatsapp` para responder. Texto llama a `apps.common.chat`, audio transcribe con `apps.common.stt`.

## Despliegue
- **Kubernetes**: aplica los manifiestos desde `infra/k8s/` (Traefik+ACME, Kafka y los deployments de la app). `infra/scripts/master-init.sh` renderiza `remedios.yaml` con `envsubst` y aplica todo sobre k3s.
- **Ansible**: playbooks en `infra/ansible/` orquestan la instalación de k3s, Traefik y el despliegue de los servicios.
- **Secretos**: coloca un `.secrets` en `infra/.secrets` con al menos `DOMAIN`, `WEBHOOK_VERIFY_TOKEN`, credenciales de Tailscale (`TAILSCALE_AUTHKEY`, `MASTER_TAILSCALE_IP`/`MASTER_TAILSCALE_HOST`, `K3S_TOKEN`) y, si usas GHCR, `GHCR_USERNAME`/`GHCR_TOKEN`.

## Operación local
- **Webhook**: `docker build -t remedios-webhook . -f apps/webhook/Dockerfile`.
- **Servicios de texto/audio**: usa `ops/run.sh texto` para levantar el stack de texto con Docker Compose, o `ops/run.sh --build audio` para regenerar y correr el servicio de audio.
- **Docker Compose**: `docker compose -f ops/docker-compose.yml up -d` levanta el LLM auxiliar y el consumidor de texto.

## Comprobaciones rápidas
- Salud webhook: `curl -v "https://$DOMAIN/webhook?hub.mode=subscribe&hub.verify_token=$WEBHOOK_VERIFY_TOKEN&hub.challenge=123"`.
- Topics Kafka: asegúrate de que existen `whatsapp-text` y `whatsapp-audio` en tu clúster.
