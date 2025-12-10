# Remedios en Always Free (Oracle ARM 1C/6GB)

Remedios es un webhook de WhatsApp escrito en Flask que publica los eventos en Kafka y se sirve detrás de Traefik con certificados emitidos automáticamente. Este README está pensado para desplegar el stack actual (y los servicios de la próxima release) en instancias **Always Free** de Oracle Cloud con 1 CPU ARM y 6 GB de RAM cada una.

## Qué vas a desplegar
- **Aplicación Remedios** (`zordon/server.py`): expone `/webhook` y `/health`, envía texto y audio a topics de Kafka.
- **Kafka (modo Raft, sin Zookeeper)** en el namespace `kafka`.
- **Traefik** con ACME HTTP-01 y TLS automático.
- **Tailscale** para la red privada entre nodos (k3s usa `tailscale0`).
- **Manifiestos y bootstrap** en `zordon/` (`remedios.yaml`, `kafka.yaml`, `traefik-acme.yaml`, scripts `master-init.sh` y `node-init.sh`).
- **Playbooks Ansible** opcionales (`zordon/ansible/`) para automatizar el cluster y los servicios.

## Requisitos previos
- Instancias Oracle Cloud **ARM** (mínimo 1 master, opcional workers), Ubuntu 22.04+ con sudo.
- Puertos 80/443 abiertos en cada nodo para Traefik.
- Un dominio público apuntando a la IP pública del master.
- Cuenta de Tailscale con auth key (idealmente efímera y reusable).
- (Opcional) Credenciales de GHCR si consumes imágenes privadas: `GHCR_USERNAME`, `GHCR_TOKEN`.

## Preparar las instancias
1. Crea las VM Always Free (1C/6GB) y habilita el puerto 22 + 80/443 en las reglas de seguridad.
2. En el **master**, instala dependencias básicas y clona el repo:
   ```bash
   sudo apt-get update && sudo apt-get install -y git jq curl
   git clone https://github.com/borisfaj/remedios.git
   cd remedios/zordon
   ```
3. Crea el fichero `.secrets` en `zordon/` con las variables mínimas:
   ```bash
   cat <<'EOFVARS' > .secrets
   DOMAIN=tu.dominio
   WEBHOOK_VERIFY_TOKEN=token_webhook
   TAILSCALE_AUTHKEY=tskey-...
   # Opcionales
   TAILSCALE_HOSTNAME=remedios-master
   GHCR_USERNAME=...
   GHCR_TOKEN=...
   EOFVARS
   ```

## Añadir workers (opcional)
1. Copia `.secrets` al worker y añade:
   ```bash
   MASTER_TAILSCALE_IP=100.x.y.z    # o MASTER_TAILSCALE_HOST=host.tailnet.ts.net
   K3S_TOKEN=$(ssh master sudo cat /var/lib/rancher/k3s/server/node-token)
   ```
2. Ejecuta en cada worker:
   ```bash
   cd ~/remedios/zordon
   bash node-init.sh
   ```
3. Valida que aparece como `Ready` con IP 100.x en:
   ```bash
   sudo k3s kubectl get nodes -o wide
   ```

## Despliegue con Ansible
La vía soportada es Ansible (sin bootstrap manual):
1. Ajusta `zordon/ansible/inventory.example.ini` y guarda tu inventario como `inventory.ini`.
2. Prepara `zordon/.secrets` en tu máquina local con las mismas variables base del master (sin `MASTER_TAILSCALE_IP/HOST` ni `K3S_TOKEN`).
3. Despliega el **cluster y el core** (k3s + Traefik + Kafka Raft + Remedios) con:
   ```bash
   ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/cluster.yml
   ```
4. Cuando el cluster ya existe, despliega los **servicios** adicionales (release en curso) con:
   ```bash
   ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/services.yml --limit master
   ```

## Verificación rápida
- Listar recursos clave:
  ```bash
  sudo k3s kubectl -n remedios get all
  sudo k3s kubectl -n kafka get all
  ```
- Logs de la app:
  ```bash
  sudo k3s kubectl -n remedios logs deploy/remedios -f
  ```
- Consumidor de ejemplo desde Kafka:
  ```bash
  sudo k3s kubectl -n kafka exec -it deploy/kafka -- \
    kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic whatsapp-text --from-beginning
  ```

## Servicios de la próxima release
Los manifiestos siguen el mismo patrón (Traefik + Secrets + imagePullSecrets). Cuando publiques nuevas imágenes multi-arch, agrégalas a los YAML de `zordon/` y reutiliza los Secrets existentes.

<details>
<summary>Notas y issues a tener en cuenta</summary>

- Tailscale debe estar arriba antes de unir workers; usa `tailscale status --json | jq -r '.Self.DNSName'` para MagicDNS.
- Traefik necesita rutas a `10.42.0.0/16` y `10.43.0.0/16` por la interfaz CNI (`cni0`/`flannel.1`).
- Certificados ACME: valida que el challenge HTTP-01 responde en 80; el Secret `remedios-tls` aparece en el ns `remedios`.
- Si usas GHCR privado, define `GHCR_USERNAME/GHCR_TOKEN` para crear el secret `ghcr-creds` y referenciarlo en `imagePullSecrets`.
- El webhook opcionalmente valida `WEBHOOK_VERIFY_TOKEN` en la suscripción de WhatsApp.
- Las instancias Always Free no tienen almacenamiento persistente abundante; monitoriza el disco de Kafka o usa temas compactados.

</details>

## Licencia
MIT, ver `LICENSE`.
