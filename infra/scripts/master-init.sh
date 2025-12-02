#!/usr/bin/env bash
set -euo pipefail

echo "== Bootstrapping master node =="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ASSETS_DIR="${SCRIPT_DIR}"
SECRETS_PATH="${SCRIPT_DIR}/.secrets"

if [ ! -f "${ASSETS_DIR}/remedios.yaml" ] && [ -f "${SCRIPT_DIR}/../k8s/remedios.yaml" ]; then
  ASSETS_DIR="${SCRIPT_DIR}/../k8s"
fi

if [ ! -f "$SECRETS_PATH" ] && [ -f "${SCRIPT_DIR}/../.secrets" ]; then
  SECRETS_PATH="${SCRIPT_DIR}/../.secrets"
fi

# ==== 0. Precondiciones ====

if [ ! -f "$SECRETS_PATH" ]; then
  echo "ERROR: .secrets no encontrado en ${SECRETS_PATH}"
  exit 1
fi

# ==== 1. Cargar variables ====

set -a
. "$SECRETS_PATH"
set +a

if [ -z "${DOMAIN:-}" ]; then
  echo "ERROR: DOMAIN vacío en .secrets"
  exit 1
fi

if [ -z "${TAILSCALE_AUTHKEY:-}" ]; then
  echo "ERROR: TAILSCALE_AUTHKEY vacío en .secrets"
  exit 1
fi

TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-remedios-master}"
TAILSCALE_MAGICDNS_HOST="${TAILSCALE_MAGICDNS_HOST:-}"
TAILSCALE_UP_FLAGS="${TAILSCALE_UP_FLAGS:-}"
GHCR_USERNAME="${GHCR_USERNAME:-${GITHUB_USERNAME:-}}"

echo "Usando DOMAIN=$DOMAIN"
echo "Usando TAILSCALE_HOSTNAME=$TAILSCALE_HOSTNAME"
if [ -n "$TAILSCALE_MAGICDNS_HOST" ]; then
  echo "Usando TAILSCALE_MAGICDNS_HOST=$TAILSCALE_MAGICDNS_HOST (SAN adicional)"
fi
if [ -n "$TAILSCALE_UP_FLAGS" ]; then
  echo "Usando flags adicionales para tailscale up: $TAILSCALE_UP_FLAGS"
fi

# ==== 2. Paquetes ====

sudo apt update
sudo apt install -y curl ufw openssl gettext-base

# ==== 3. Tailscale ====

echo "Instalando y configurando Tailscale"
curl -fsSL https://tailscale.com/install.sh | sh
sudo systemctl enable --now tailscaled
sudo tailscale up --reset --authkey "$TAILSCALE_AUTHKEY" --hostname "$TAILSCALE_HOSTNAME" --accept-routes $TAILSCALE_UP_FLAGS

TAILSCALE_IP="$(sudo tailscale ip -4 | head -n 1)"
if [ -z "$TAILSCALE_IP" ]; then
  echo "ERROR: No se pudo obtener la IP de tailscale0"
  exit 1
fi
echo "tailscale0 IP: $TAILSCALE_IP"

if [ -z "$TAILSCALE_MAGICDNS_HOST" ] && command -v python3 >/dev/null 2>&1; then
  TAILSCALE_MAGICDNS_HOST="$({ sudo tailscale status --json 2>/dev/null | python3 - <<'PY'
import json, sys
try:
    data = json.load(sys.stdin)
    dns = data.get("Self", {}).get("DNSName", "")
    print(dns.rstrip("."))
except Exception:
    pass
PY
  } || true)"
fi
if [ -n "$TAILSCALE_MAGICDNS_HOST" ]; then
  echo "MagicDNS detectado: $TAILSCALE_MAGICDNS_HOST"
fi

# ==== 3.1. Config k3s persistente ====

sudo mkdir -p /etc/rancher/k3s
{
  echo "node-ip: $TAILSCALE_IP"
  echo "advertise-address: $TAILSCALE_IP"
  echo "flannel-iface: tailscale0"
  echo "tls-san:"
  echo "  - $TAILSCALE_IP"
  if [ -n "$TAILSCALE_MAGICDNS_HOST" ]; then
    echo "  - $TAILSCALE_MAGICDNS_HOST"
  fi
} | sudo tee /etc/rancher/k3s/config.yaml >/dev/null
echo "Escrito /etc/rancher/k3s/config.yaml con IP/SAN de Tailscale"

# ==== 4. Firewall ====

sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 6443/tcp
sudo ufw allow 10250/tcp
sudo ufw allow 8472/udp
sudo ufw allow 6443/udp
sudo ufw allow 41641/udp
sudo ufw allow in on tailscale0
sudo ufw allow out on tailscale0
sudo ufw --force enable

# ==== 5. Instalar k3s ====

TLS_SANS="--tls-san $TAILSCALE_IP"
if [ -n "$TAILSCALE_MAGICDNS_HOST" ]; then
  TLS_SANS="$TLS_SANS --tls-san $TAILSCALE_MAGICDNS_HOST"
fi

curl -sfL https://get.k3s.io | sudo INSTALL_K3S_EXEC="server --write-kubeconfig-mode=644" sh -
sudo systemctl daemon-reload
sudo systemctl restart k3s

echo "Esperando a que k3s esté listo…"
for i in $(seq 1 30); do
  if sudo k3s kubectl get nodes >/dev/null 2>&1; then
    echo "k3s listo"
    break
  fi
  sleep 5
done
echo "Esperando a que el apiserver esté listo…"
API_READY=0
for i in $(seq 1 20); do
  if sudo k3s kubectl get --raw='/readyz' >/dev/null 2>&1; then
    API_READY=1
    break
  fi
  sleep 3
done
if [ "$API_READY" -ne 1 ]; then
  echo "ERROR: apiserver no listo tras esperar"
  exit 1
fi
sleep 2

# ==== 6. Redes: rutas internas ====
# Asegurar que el host tiene rutas a los CIDR de servicios/pods por la interfaz CNI
CNI_IFACE=""
for i in $(seq 1 45); do
  CNI_IFACE="$(ip -o link show | awk -F': ' '/^(cni[0-9]*|flannel|vxlan)/{print $2; exit}')"
  if [ -n "$CNI_IFACE" ]; then
    break
  fi
  sleep 2
done

if [ -z "$CNI_IFACE" ]; then
  echo "AVISO: No se detectó interfaz CNI (cni0/flannel.1) tras esperar; se omiten las rutas 10.42/10.43. Verifica conectividad de pods/servicios."
else
  echo "Usando interfaz CNI: $CNI_IFACE"
  sudo ip route replace 10.43.0.0/16 dev "$CNI_IFACE"
  sudo ip route replace 10.42.0.0/16 dev "$CNI_IFACE"
fi

# ==== 7. Namespaces ====

sudo k3s kubectl create namespace kafka || true
sudo k3s kubectl create namespace remedios || true

# ==== 8. Pull secret para GHCR (opcional) ====
if [ -n "${GHCR_TOKEN:-}" ]; then
  if [ -z "$GHCR_USERNAME" ]; then
    echo "ERROR: GHCR_TOKEN presente pero GHCR_USERNAME vacío. Añádelo en .secrets."
    exit 1
  fi
  echo "Creando secret ghcr-creds en remedios para ghcr.io (usuario $GHCR_USERNAME)"
  sudo k3s kubectl -n remedios delete secret ghcr-creds --ignore-not-found
  sudo k3s kubectl -n remedios create secret docker-registry ghcr-creds \
    --docker-server=ghcr.io \
    --docker-username="$GHCR_USERNAME" \
    --docker-password="$GHCR_TOKEN"
else
  echo "GHCR_TOKEN no definido: se asumirá que las imágenes son públicas"
fi

# ==== 9. Traefik + ACME (Let’s Encrypt) ====

echo "Aplicando configuracion ACME para Traefik"
sudo k3s kubectl apply -n kube-system -f "${ASSETS_DIR}/traefik-acme.yaml"

# ==== 10. Aplicar kafka ====

echo "Aplicando kafka.yaml"
sudo k3s kubectl apply -f "${ASSETS_DIR}/kafka.yaml"

# ==== 11. Aplicar remedios.yaml con envsubst ====

echo "Aplicando remedios.yaml con DOMAIN=$DOMAIN"
envsubst < "${ASSETS_DIR}/remedios.yaml" > /tmp/remedios.rendered.yaml
sudo k3s kubectl apply -f /tmp/remedios.rendered.yaml


echo "== Setup COMPLETADO =="
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl -n remedios get all
