# OpenClaw Guide

## Build Images (ARM64)

```bash
docker buildx build --platform linux/arm64 \
  --no-cache \
  -t ghcr.io/borisfaj/openclaw:latest \
  -f remedios/services/openclaw/Dockerfile \
  --push .

docker buildx build --platform linux/arm64 \
  --no-cache \
  -t ghcr.io/borisfaj/openclaw-snapshot:latest \
  -f remedios/services/openclaw/snapshot.Dockerfile \
  --push .
```

## Deploy OpenClaw

```bash
ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/services.yml \
  -e "deploy_openclaw=true"
```

This deploy includes:
- OpenClaw deployment with PVC state
- restore init container
- snapshot sidecar
- daily snapshot cronjob

## Enable/Disable UI

Enable UI ingress (VPN-only access via your tailnet host):

```bash
ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/services.yml \
  -e "deploy_openclaw_ui=true"
```

Disable UI ingress:

```bash
ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/services.yml \
  -e "deploy_openclaw_ui=false"
```

URL format:

```text
https://<OPENCLAW_UI_HOST>
```

## First-Time Manual Onboarding (Required)

First use requires running onboarding interactively inside the pod:

```bash
POD=$(kubectl -n remedios get pod -l app=openclaw -o jsonpath='{.items[0].metadata.name}')
kubectl -n remedios exec -it "$POD" -c openclaw -- openclaw onboard
```

## Token and Access

OpenClaw manages its own token in persisted config (`/home/node/.openclaw`).

Read current token:

```bash
POD=$(kubectl -n remedios get pod -l app=openclaw -o jsonpath='{.items[0].metadata.name}')
kubectl -n remedios exec "$POD" -c openclaw -- sh -lc "grep -n '\"token\"' /home/node/.openclaw/openclaw.json"
```

Open UI with tokenized URL:

```text
https://<OPENCLAW_UI_HOST>/?token=<TOKEN>
```

## Pairing

Pairing can be required for control UI/webchat clients.

List pending requests (channel required):

```bash
POD=$(kubectl -n remedios get pod -l app=openclaw -o jsonpath='{.items[0].metadata.name}')
kubectl -n remedios exec -it "$POD" -c openclaw -- openclaw pairing list --channel webchat
```

Approve pairing code:

```bash
kubectl -n remedios exec -it "$POD" -c openclaw -- openclaw pairing approve --channel webchat <CODE>
```
