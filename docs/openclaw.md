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

Current deploy behavior:
- the base image can stay on `ghcr.io/borisfaj/openclaw:latest`
- the pod installs `openclaw@${OPENCLAW_RUNTIME_VERSION}` into persisted state on first boot
- the pod also installs runtime plugin deps currently needed by Telegram/Slack (`grammy`, `@grammyjs/runner`, `@grammyjs/transformer-throttler`, `@slack/web-api`, `@slack/bolt`)
- the pod writes a small fetch preload patch that resolves external HTTPS hosts to IPv4 and connects by IP while preserving TLS hostnames; this avoids the Node 22 timeout issues seen in this cluster
- the chat UI workspace is pinned to `OPENCLAW_CHAT_WORKSPACE` so it does not reuse the seeded bootstrap workspace with protected files like `USER.md`
- default auth is `none` so local `port-forward` access works without a token
- restore mode is controlled with `OPENCLAW_RESTORE_MODE` (`if-empty`, `force-latest`, `skip`)

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

First use after a clean reset requires running onboarding interactively inside the pod:

```bash
POD=$(kubectl -n remedios get pod -l app=openclaw -o jsonpath='{.items[0].metadata.name}')
kubectl -n remedios exec -it "$POD" -c openclaw -- sh -lc 'export PATH=/home/node/.openclaw/.npm-global/bin:$PATH; openclaw onboard'
```

## Token and Access

If `OPENCLAW_GATEWAY_AUTH=none`, UI access over `port-forward` does not need a token:

```text
http://127.0.0.1:18789/
```

If you later switch to token auth, OpenClaw manages its own token in persisted config (`/home/node/.openclaw`).

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
