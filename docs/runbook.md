# Operations Runbook

## Common Status Checks

```bash
kubectl -n remedios get pods
kubectl -n remedios get svc,ingress
kubectl -n remedios get deploy
```

## Logs

```bash
kubectl -n remedios logs -l app=dispatcher -f
kubectl -n remedios logs -l app=remedios-api -f
kubectl -n remedios logs -l app=remetext -f
kubectl -n remedios logs -l app=whisper-turbo -f
kubectl -n remedios logs -l app=openclaw -c openclaw -f
```

## Rollout Commands

```bash
kubectl -n remedios rollout status deploy/dispatcher
kubectl -n remedios rollout status deploy/remedios-api
kubectl -n remedios rollout status deploy/remetext
kubectl -n remedios rollout status deploy/whisper-turbo
kubectl -n remedios rollout status deploy/openclaw
```

Restart:

```bash
kubectl -n remedios rollout restart deploy/openclaw
```

## OpenClaw Troubleshooting

### 1) UI shows unauthorized / token mismatch
- Read token from `openclaw.json` in pod.
- Open UI with `?token=<TOKEN>`.
- Use private/incognito window if browser cached old token.

### 2) UI shows pairing required
- Run pairing list with channel.
- Approve pending code.

### 3) Rollout stuck
- Check pod events and container logs.
- Validate openclaw proxy sidecar is healthy.

```bash
POD=$(kubectl -n remedios get pod -l app=openclaw -o jsonpath='{.items[0].metadata.name}')
kubectl -n remedios describe pod "$POD"
kubectl -n remedios logs "$POD" -c openclaw --tail=200
kubectl -n remedios logs "$POD" -c openclaw-proxy --tail=200
```

### 4) First use not initialized
- Run manual onboarding inside container (interactive).

## Kafka Logs

```bash
kubectl -n kafka logs -l app=kafka -f
```

## Alembic (Oracle)

```bash
./scripts/alembic-oracle.sh stamp head
./scripts/alembic-oracle.sh upgrade head
./scripts/alembic-oracle.sh revision -m "descripcion" --autogenerate
```
