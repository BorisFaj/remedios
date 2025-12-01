Remedios
========

Webhook de WhatsApp desplegado en Kubernetes (k3s) que encola los eventos en Kafka. Se sirve detrás de Traefik con TLS automático de Let’s Encrypt.

Contenido clave
---------------
- **Aplicación**: Flask (`zordon/server.py`) con endpoints `/webhook` (POST/GET) y `/health`. Envía los mensajes a Kafka (`whatsapp-text` o `whatsapp-audio`) usando `BOOTSTRAP_SERVER`.
- **Infra**: manifiestos y scripts en `zordon/`:
  - `cloud-init.sh`: instala k3s, abre puertos, fija rutas CNI internas, aplica Traefik + ACME y despliega Kafka y la app.
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
  - (añade otras vars si las necesitas)

Despliegue rápido en instancia nueva
------------------------------------
1) Clona el repo y ve a `zordon/`.
2) Crea `.secrets` con las variables anteriores.
3) Ejecuta el bootstrap:
   ```bash
   cd zordon
   bash cloud-init.sh
   ```
   El script:
   - Instala k3s.
   - Asegura rutas de red internas (10.42.0.0/16 pods, 10.43.0.0/16 servicios) por la interfaz CNI.
   - Aplica Traefik con ACME (HTTP-01).
   - Despliega Kafka (`kafka` namespace).
   - Despliega Remedios (`remedios` namespace) renderizando `remedios.yaml` con `envsubst`.

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
