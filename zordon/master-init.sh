#!/usr/bin/env bash
set -euo pipefail

echo "== Bootstrapping master node =="

# ==== 0. Precondiciones ====

if [ ! -f .secrets ]; then
  echo "ERROR: .secrets no encontrado"
  exit 1
fi

# ==== 1. Cargar variables ====

set -a
. .secrets
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
GHCR_USERNAME="${GHCR_USERNAME:-${GITHUB_USERNAME:-}}"

echo "Usando DOMAIN=$DOMAIN"
echo "Usando TAILSCALE_HOSTNAME=$TAILSCALE_HOSTNAME"

# ==== 2. Paquetes ====

sudo apt update
sudo apt install -y curl ufw openssl gettext-base

# ==== 3. Tailscale ====

echo "Instalando y configurando Tailscale"
curl -fsSL https://tailscale.com/install.sh | sh
sudo systemctl enable --now tailscaled
sudo tailscale up --authkey "$TAILSCALE_AUTHKEY" --hostname "$TAILSCALE_HOSTNAME" --accept-routes

TAILSCALE_IP="$(sudo tailscale ip -4 | head -n 1)"
if [ -z "$TAILSCALE_IP" ]; then
  echo "ERROR: No se pudo obtener la IP de tailscale0"
  exit 1
fi
echo "tailscale0 IP: $TAILSCALE_IP"

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

curl -sfL https://get.k3s.io | sudo INSTALL_K3S_EXEC="server --write-kubeconfig-mode=644 --node-ip $TAILSCALE_IP --advertise-address $TAILSCALE_IP --tls-san $TAILSCALE_IP --flannel-iface tailscale0" sh -

echo "Esperando a que k3s esté listo…"
for i in $(seq 1 30); do
  if sudo k3s kubectl get nodes >/dev/null 2>&1; then
    echo "k3s listo"
    break
  fi
  sleep 5
done

# ==== 6. Redes: rutas internas ====
# Asegurar que el host tiene rutas a los CIDR de servicios/pods por la interfaz CNI
CNI_IFACE="$(ip -o link show | awk -F': ' '/^(cni|flannel|vxlan)/{print $2; exit}')"
if [ -z "$CNI_IFACE" ]; then
  echo "ERROR: No se detectó interfaz CNI (cni0/flannel.1). Revisa el despliegue de k3s."
  exit 1
fi
echo "Usando interfaz CNI: $CNI_IFACE"
sudo ip route replace 10.43.0.0/16 dev "$CNI_IFACE"
sudo ip route replace 10.42.0.0/16 dev "$CNI_IFACE"

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
sudo k3s kubectl apply -n kube-system -f traefik-acme.yaml

# ==== 10. Aplicar kafka ====

echo "Aplicando kafka.yaml"
sudo k3s kubectl apply -f kafka.yaml

# ==== 11. Aplicar remedios.yaml con envsubst ====

echo "Aplicando remedios.yaml con DOMAIN=$DOMAIN"
envsubst < remedios.yaml > /tmp/remedios.rendered.yaml
sudo k3s kubectl apply -f /tmp/remedios.rendered.yaml


echo "== Setup COMPLETADO =="
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl -n remedios get all
