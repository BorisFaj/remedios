# Deployment Guide

## Prerequisites

1. Oracle Cloud instances (Ubuntu 22.04 ARM64)
2. Domain configured for ingress traffic
3. Tailscale account + auth key
4. Oracle Autonomous DB (wallet downloaded and extracted)
5. Oracle Object Storage bucket
6. Optional GHCR credentials for private images

## Secrets File

Create `zordon/.secrets`:

```ini
# Domain and WhatsApp/Graph
DOMAIN=tu-dominio.com
WEBHOOK_VERIFY_TOKEN=tu-token-secreto
GRAPH_URL=https://graph.facebook.com/v19.0
GRAPH_API_TOKEN=tu_token

# Tailscale
TAILSCALE_AUTHKEY=tskey-auth-tu-key

# Oracle DB
ORACLE_USER=tu_usuario
ORACLE_PASSWORD=tu_password
ORACLE_DSN=tu_alias_tns
ORACLE_WALLET_PATH=/ruta/al/wallet_descomprimido
ORACLE_WALLET_PASSWORD=opcional

# OCI SDK (Object Storage)
OCI_CONFIG_PATH=/home/usuario/.oci/config_cloud
OCI_API_KEY_PATH=/home/usuario/.oci/cloud.pem
OCI_PROFILE=DEFAULT
OCI_BUCKET_NAME=tu_bucket
OCI_BUCKET_NAMESPACE=tu_namespace

# OpenClaw (optional)
OPENCLAW_IMAGE=ghcr.io/tu-org/openclaw:latest
OPENCLAW_SNAPSHOT_IMAGE=ghcr.io/tu-org/openclaw-snapshot:latest
OPENCLAW_PVC_SIZE=5Gi
OPENCLAW_STORAGE_CLASS=local-path
OPENCLAW_BUCKET_PREFIX=openclaw/snapshots
OPENCLAW_RETENTION_DAYS=10
OPENCLAW_CHECKPOINT_INTERVAL_MINUTES=30
OPENCLAW_DAILY_HOUR_UTC=3
OPENCLAW_DAILY_MINUTE_UTC=0
OPENCLAW_DAILY_CRON="0 3 * * *"
OPENCLAW_UI_HOST=openclaw.tu-tailnet.ts.net

# GHCR (optional)
GHCR_USERNAME=tu-usuario-github
GHCR_TOKEN=tu_token_ghcr
```

Notes:
- `ORACLE_WALLET_PATH` must point to a folder, not a zip.
- OCI files are mounted as Kubernetes secrets and must stay out of git.

## Inventory

Edit `zordon/ansible/inventory.ini`:

```ini
[master]
tu-usuario@tu-ip-publica

[nodes]
# Add worker nodes here
```

## Deploy Cluster

```bash
ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/cluster.yml
```

## Deploy Application Services

```bash
ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/services.yml \
  -e "deploy_dispatcher=true deploy_remedios_api=true deploy_remetext=true deploy_whisper_turbo=true"
```

## Scale Whisper Turbo

To keep 2 replicas via manifests:
- `zordon/deploy/audio_whisperturbo.yaml` uses `replicas: 2`

To apply:

```bash
ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/services.yml \
  -e "deploy_whisper_turbo=true"
```
