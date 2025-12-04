#!/usr/bin/env bash
set -euo pipefail

echo "== Bootstrapping worker node =="

# ==== 0. Precondiciones ====

if [ ! -f .secrets ]; then
  echo "ERROR: .secrets no encontrado"
  exit 1
fi

# ==== 1. Cargar variables ====

set -a
. .secrets
set +a

if [ -z "${TAILSCALE_AUTHKEY:-}" ]; then
  echo "ERROR: TAILSCALE_AUTHKEY vacío en .secrets"
  exit 1
fi

if [ -z "${MASTER_TAILSCALE_IP:-}" ] && [ -z "${MASTER_TAILSCALE_HOST:-}" ]; then
  echo "ERROR: MASTER_TAILSCALE_IP/MASTER_TAILSCALE_HOST vacíos en .secrets"
  exit 1
fi

if [ -z "${K3S_TOKEN:-}" ]; then
  echo "ERROR: K3S_TOKEN vacío en .secrets"
  exit 1
fi

TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-remedios-node-$(hostname)}"
TAILSCALE_UP_FLAGS="${TAILSCALE_UP_FLAGS:-}"
MASTER_TAILSCALE_HOST="${MASTER_TAILSCALE_HOST:-$MASTER_TAILSCALE_IP}"
K3S_URL="https://${MASTER_TAILSCALE_HOST}:6443"

if [ -n "${MASTER_TAILSCALE_IP:-}" ]; then
  echo "Usando MASTER_TAILSCALE_IP=$MASTER_TAILSCALE_IP"
fi
echo "Usando MASTER_TAILSCALE_HOST=$MASTER_TAILSCALE_HOST (MagicDNS o IP)"
echo "Usando TAILSCALE_HOSTNAME=$TAILSCALE_HOSTNAME"
if [ -n "$TAILSCALE_UP_FLAGS" ]; then
  echo "Usando flags adicionales para tailscale up: $TAILSCALE_UP_FLAGS"
fi

# ==== 2. Paquetes ====

sudo apt update
sudo apt install -y curl ufw openssl

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

# ==== 4. Firewall ====

sudo ufw allow 22/tcp
sudo ufw allow 10250/tcp
sudo ufw allow 8472/udp
sudo ufw allow 6443/udp
sudo ufw allow 41641/udp
sudo ufw allow in on tailscale0
sudo ufw allow out on tailscale0
sudo ufw --force enable

# ==== 5. Instalar k3s agent ====

curl -sfL https://get.k3s.io | sudo K3S_URL="$K3S_URL" K3S_TOKEN="$K3S_TOKEN" INSTALL_K3S_EXEC="agent --node-ip $TAILSCALE_IP --flannel-iface tailscale0" sh -

echo "== Node listo (verifica en el master con: sudo k3s kubectl get nodes -o wide) =="
