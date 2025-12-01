Remedios
========

Webhook de WhatsApp desplegado en Kubernetes (k3s) que encola los eventos en Kafka. Se sirve detrás de Traefik con TLS automático de Let’s Encrypt.

Contenido clave
---------------
- **Aplicación**: Flask (`zordon/server.py`) con endpoints `/webhook` (POST/GET) y `/health`. Envía los mensajes a Kafka (`whatsapp-text` o `whatsapp-audio`) usando `BOOTSTRAP_SERVER`.
- **Infra**: manifiestos y scripts en `zordon/`:
  - `master-init.sh`: instala k3s, abre puertos, fija rutas CNI internas, aplica Traefik + ACME y despliega Kafka y la app sobre tailscale0.
  - `node-init.sh`: añade workers a ese cluster k3s, también sobre tailscale0.
  - `traefik-acme.yaml`: configura Traefik para certs Let’s Encrypt (HTTP-01).
  - `remedios.yaml`: Deployment/Service/Ingress de la app.
  - `kafka.yaml`: despliegue de Kafka/Zookeeper.
  - `whatsapp-consumer.yaml`: consumidor (si lo necesitas).

Requisitos
----------
- Ubuntu 22.04+ con acceso root.
- Dominio público apuntando al IP público de la instancia (A/CNAME para `${DOMAIN}` y, opcional, `www`). Puertos 80 y 443 abiertos.
- `.secrets` en `zordon/` con:
  - `DOMAIN=tu.dominio`
  - `WEBHOOK_VERIFY_TOKEN=token_webhook` (opcional pero recomendado)
  - `TAILSCALE_AUTHKEY=tskey-...` (auth key de Tailscale)
  - Para workers: `MASTER_TAILSCALE_IP=100.x.y.z` (IP tailscale del master) y `K3S_TOKEN=<node-token>`
  - (opcional) `TAILSCALE_HOSTNAME=nombre-personalizado`
  - (añade otras vars si las necesitas)

Despliegue rápido en instancia nueva
------------------------------------
1) Clona el repo y ve a `zordon/`.
2) Crea `.secrets` con las variables anteriores.
3) Ejecuta el bootstrap:
   ```bash
   cd zordon
   bash master-init.sh
   ```
   El script:
   - Instala k3s.
   - Asegura rutas de red internas (10.42.0.0/16 pods, 10.43.0.0/16 servicios) por la interfaz CNI.
   - Aplica Traefik con ACME (HTTP-01).
   - Despliega Kafka (`kafka` namespace).
   - Despliega Remedios (`remedios` namespace) renderizando `remedios.yaml` con `envsubst`.

Workers sobre Tailscale
-----------------------
- Ejecuta `bash master-init.sh` primero. Guarda el `K3S_TOKEN` desde `/var/lib/rancher/k3s/server/node-token` y la IP de tailscale (`tailscale ip -4 | head -n1`).
- En cada worker copia `.secrets` con `TAILSCALE_AUTHKEY`, `MASTER_TAILSCALE_IP` y `K3S_TOKEN` (opcionalmente `TAILSCALE_HOSTNAME`), luego ejecuta `bash node-init.sh`.
- Todo el tráfico de control y flannel viaja por `tailscale0`; expone 80/443 hacia Internet para Traefik como antes.

Despliegue con Ansible (Tailscale automático)
---------------------------------------------
- Prepara un inventario con grupos `master` y `nodes` (ejemplo en `zordon/ansible/inventory.example.ini`).
- Crea en tu máquina (no se trackea en git) el fichero `zordon/.secrets` con las variables base (`DOMAIN`, `WEBHOOK_VERIFY_TOKEN`, `TAILSCALE_AUTHKEY`, opcional `TAILSCALE_HOSTNAME`). No pongas `MASTER_TAILSCALE_IP` ni `K3S_TOKEN`; el playbook los añadirá en destino.
- Ejecuta desde la raíz del repo:
  ```bash
  ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/cluster.yml
  ```
- El playbook copia los scripts, bootstrappea el master, obtiene automáticamente la IP de tailscale y el `K3S_TOKEN`, y luego une los workers sin que tengas que pasar manualmente esos datos.
- Casos de uso:
  - **Cluster de un solo nodo (solo master)**: define solo el host en `master` (o usa `--limit master`). No es necesario declarar `nodes`.
  - **Cluster nuevo con varios nodos**: define `master` + `nodes` y ejecuta el playbook completo (sin `--limit`).
  - **Añadir workers a un cluster existente**: añade los nuevos hosts en el grupo `nodes` y ejecuta `ansible-playbook ... --limit <host1>,<host2>` (o `--limit nodes` si solo hay nuevos). El play contactará al `master` del inventario para leer su IP de tailscale y el token, sin reprovisionar el master.
  - **Solo añadir un worker concreto**: deja el `master` definido en el inventario (para poder delegar), añade el host al grupo `nodes` y ejecuta, por ejemplo:
    ```bash
    ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/cluster.yml --limit master1,worker2
    ```
    Incluir el master en el `--limit` permite delegar la lectura de IP/token sin tocarlo; no se reprovisiona.

Cómo obtener el auth key de Tailscale
-------------------------------------
- Entra a https://login.tailscale.com → Settings → Keys → Generate auth key (idealmente *ephemeral* + reusable si quieres añadir nodos).
- Usa ese valor como `TAILSCALE_AUTHKEY` en `group_vars/all.yml` o en tus variables de inventario.

Verificación
------------
- Traefik/ACME:
  ```bash
  sudo k3s kubectl -n kube-system logs -l app.kubernetes.io/name=traefik -f
  ```
  Debes ver el challenge y la emisión para tu dominio; el Secret `remedios-tls` aparecerá en el ns `remedios`.

- Certificado:
  ```bash
  sudo k3s kubectl -n remedios get secret remedios-tls -o jsonpath='{.data.tls\.crt}' \
    | base64 -d | openssl x509 -noout -issuer -subject -dates
  ```

- Salud HTTP/HTTPS:
  ```bash
  curl -v https://$DOMAIN/health
  curl -v "https://$DOMAIN/webhook?hub.mode=subscribe&hub.verify_token=$WEBHOOK_VERIFY_TOKEN&hub.challenge=123"
  ```

- DNS/Challenge:
  ```bash
  curl -v http://$DOMAIN/.well-known/acme-challenge/test
  ```
  Debe responder 404 desde Traefik sin redirecciones.

Despliegue manual (si ya tienes k3s)
------------------------------------
```bash
cd zordon
set -a; . .secrets; set +a
kubectl apply -n kube-system -f traefik-acme.yaml
envsubst '$DOMAIN $WEBHOOK_VERIFY_TOKEN' < remedios.yaml | kubectl apply -n remedios -f -
```

Notas sobre red
---------------
- Traefik necesita llegar al API de k8s (`10.43.0.1:443`). Si ves en sus logs `no route to host`, asegúrate de que el host tiene rutas a 10.42.0.0/16 y 10.43.0.0/16 por la interfaz CNI (`cni0`/`flannel.1`). El `cloud-init.sh` ya las instala; en sistemas existentes:
  ```bash
  sudo ip route replace 10.43.0.0/16 dev cni0
  sudo ip route replace 10.42.0.0/16 dev cni0
  ```

Kafka
-----
- Kafka se despliega en el namespace `kafka` con `kafka.yaml`.
- El productor Flask usa `BOOTSTRAP_SERVER` del ConfigMap (`kafka.kafka.svc.cluster.local:9092` por defecto).
- Topics usados: `whatsapp-text`, `whatsapp-audio`.

Referencias rápidas
-------------------
- Listar recursos:
  ```bash
  kubectl -n remedios get all
  kubectl -n kafka get all
  ```
- Logs de la app:
  ```bash
  kubectl -n remedios logs deploy/remedios -f
  ```
- Consumidor de ejemplo (desde el pod de Kafka):
  ```bash
  kubectl -n kafka exec -it deploy/kafka -- \
    kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic whatsapp-text --from-beginning
  ```

Próximos pasos
--------------
- Añadir/activar los pipelines de Whisper/GPT (consumidor en `whatsapp_consumer.py` y manifiesto `whatsapp-consumer.yaml`).
- Documentar credenciales externas necesarias (si aplica).

Licencia
--------
MIT. Veja `LICENSE`.
