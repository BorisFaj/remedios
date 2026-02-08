<p align="center">
  <img src="logo.png" alt="Remedios logo" width="600"/>
</p>

**Webhook de WhatsApp escalable y ligero, diseñado para Oracle Cloud Always Free (ARM).**

Remedios es una plataforma de procesamiento de mensajes de WhatsApp que despliega una arquitectura de microservicios robusta y escalable sobre Kubernetes (k3s), optimizada para ejecutarse en instancias ARM64 gratuitas de Oracle Cloud (Ampere), pero capaz de escalar horizontalmente añadiendo más nodos.

## 🚀 Objetivo del Proyecto

El objetivo principal es desplegar un stack de procesamiento de IA en Oracle Always Free para voz y routing de mensajes, manteniendo una arquitectura escalable que permita añadir un nodo GPU cuando se necesite ejecutar un LLM.

- **Coste Cero**: Funciona en instancias ARM (4 OCPUs, 24GB RAM) de la capa gratuita.
- **Escalabilidad**: Diseño basado en eventos (Kafka) y Kubernetes. Puedes añadir workers fácilmente.
- **Seguridad**: Red mesh privada con Tailscale y TLS automático con Traefik.

## 🏗 Arquitectura

El sistema se compone de varios módulos desacoplados:

1.  **Ingress & Seguridad**:
    - **Traefik**: Ingress Controller que gestiona certificados SSL automáticamente (Let's Encrypt).
    - **Tailscale**: Crea una red privada segura (Mesh VPN) entre todos los nodos del cluster, sin exponer puertos de gestión a internet.

2.  **Event Bus**:
    - **Kafka**: Desacopla la recepción de mensajes del procesamiento. El webhook solo encola eventos, garantizando alta disponibilidad y baja latencia de respuesta a Meta.

3.  **Servicios (Microservicios)**:
    - **Dispatcher** (`remedios/core/dispatcher`): Recibe webhooks de WhatsApp, registra el mensaje vía API interna y publica en Kafka.
    - **API interna** (`remedios/core/api`): Persiste estados/resultados y ofrece endpoints internos para envío de respuestas y extracción de audio.
    - **Remetext** (`remedios/consumers/text`): Procesamiento de texto y respuesta por WhatsApp.
    - **Whisper Workers** (`remedios/consumers/audio`): Transcripción de audio con `whisper-turbo` o `whisper-cpp`.

## 📋 Requisitos Previos

1.  **Instancias Oracle Cloud**: Ubuntu 22.04 (ARM64 Ampere) para el/los nodos del cluster.
2.  **Dominio**: Un dominio público apuntando a la IP pública de tu instancia.
3.  **Tailscale**: Cuenta de Tailscale y una Auth Key (reusable y efímera recomendada).
4.  **Oracle Autonomous DB**: Un Autonomous Database activo (región y endpoint conocidos).
5.  **Oracle Object Storage**: Un bucket existente (namespace, nombre y permisos IAM).
6.  **Credenciales GHCR (opcional)**: Si las imágenes son privadas, necesitas `GHCR_USERNAME` y `GHCR_TOKEN` con permiso `read:packages`. Si son públicas, no hace falta.

## ✅ Pasos Previos (desde cero)

### 1) Nodos y red
- Crea una instancia ARM64 (o varias) en OCI con Ubuntu 22.04.
- Asegura salida a internet y acceso al puerto 443 para GitHub y OCI APIs.
- Apunta el dominio público a la IP del nodo master.

### 2) Base de datos (Autonomous DB)
- Crea una Autonomous Database.
- Descarga el **wallet** y descomprímelo en tu máquina local.
- Elige el alias del servicio (`*_high`, `*_medium`, etc.) de `tnsnames.ora`.

### 3) Object Storage (bucket)
- Crea un bucket en Object Storage.
- Anota **namespace**, **bucket name** y región.
- Asegura permisos IAM para el usuario (o principal) que usará el SDK.

### 4) Credenciales OCI para el SDK
- Genera una **API Key** para el usuario (o crea una nueva):
  - `oci setup config` y guarda el config en un fichero dedicado (ej. `~/.oci/config_cloud`).
  - Sube la **clave pública** al usuario en OCI Console → User → API Keys.
- Guarda la **clave privada** en una ruta local segura.

### 5) Secretos locales para el deploy
Crea `zordon/.secrets` con lo mínimo:

```ini
# Dominio y WhatsApp/Graph
DOMAIN=tu-dominio.com
WEBHOOK_VERIFY_TOKEN=tu-token-secreto
GRAPH_URL=https://graph.facebook.com/v19.0
GRAPH_API_TOKEN=tu_token

# Tailscale
TAILSCALE_AUTHKEY=tskey-auth-tu-key

# Oracle DB
ORACLE_USER=tu_usuario
ORACLE_PASSWORD=tu_password
ORACLE_DSN=golismeos_high
ORACLE_WALLET_PATH=/ruta/al/wallet_descomprimido
ORACLE_WALLET_PASSWORD=opcional_si_protegido

# OCI SDK (Object Storage)
OCI_CONFIG_PATH=/.oci/config_cloud
OCI_API_KEY_PATH=/.oci/cloud.pem
OCI_PROFILE=DEFAULT
OCI_BUCKET_NAME=tu_bucket
OCI_BUCKET_NAMESPACE=tu_namespace
OCI_BUCKET_PREFIX=whatsapp

# GHCR (opcional)
GHCR_USERNAME=tu-usuario-github
GHCR_TOKEN=tu_token_ghcr
```

Notas:
- `ORACLE_WALLET_PATH` debe apuntar a **carpeta**, no ZIP.
### 6) Añadir el inventory
Edita `zordon/ansible/inventory.ini` con tu `master` y, si aplica, los `nodes`.

## 🛠 Instalación (Ansible)

La infraestructura se despliega automáticamente usando Ansible.

### 1. Preparación

Clona el repositorio:
```bash
git clone https://github.com/BorisFaj/remedios.git
cd remedios
```

Crea un archivo `.secrets` en `zordon/.secrets` (este archivo es ignorado por git):

```bash
# zordon/.secrets
DOMAIN=tu-dominio.com
WEBHOOK_VERIFY_TOKEN=tu-token-secreto
TAILSCALE_AUTHKEY=tskey-auth-tu-key
GHCR_USERNAME=tu-usuario-github
GHCR_TOKEN=tu_token_ghcr
# Opcional: Configuración de Whisper
WHISPER_MODEL=ggml-large-v3-turbo-q5_0.bin
```

No compartas este archivo.

### 2. Configurar Inventario

Edita `zordon/ansible/inventory.ini`. Para un despliegue "Single Node" (todo en una máquina), solo define el `master`:

```ini
[master]
tu-usuario@tu-ip-publica

[nodes]
# Deja esto vacío si solo usas un nodo
```

### 3. Desplegar Cluster e Infraestructura

Ejecuta el playbook de cluster. Esto instalará k3s, Tailscale, Traefik y Kafka (solo infraestructura, sin desplegar los servicios de aplicación):

```bash
ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/cluster.yml
```

### 4. Desplegar Servicios

Una vez el cluster esté arriba, despliega los servicios de aplicación (dispatcher, api interna, Remetext, Whisper, etc.):

```bash
ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/services.yml \
  -e "deploy_dispatcher=true deploy_remedios_api=true deploy_remetext=true deploy_whisper_turbo=true deploy_whisper_cpp=false"
```

## 📈 Escalabilidad (Añadir Nodos)

Gracias a la arquitectura basada en Tailscale, añadir nodos es trivial, incluso si están en otras redes o proveedores.

1.  Añade la IP del nuevo servidor al grupo `[nodes]` en `zordon/ansible/inventory.ini`.
2.  Ejecuta de nuevo el playbook de cluster:
    ```bash
    ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/cluster.yml
    ```
    El script detectará automáticamente el token del master y unirá el nuevo nodo a través del túnel seguro de Tailscale.

## 📂 Estructura del Proyecto

- `remedios/`: Código fuente de la aplicación (core, API, consumers).
- `zordon/`: Infraestructura y despliegue.
    - `ansible/`: Playbooks de automatización.
    - `deploy/`: Manifiestos de Kubernetes (YAMLs).

### Logs en Oracle
- La capa de persistencia vive en `remedios/core/api/persistence` y la usa la API interna.
- Variables necesarias en `.secrets`: `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_DSN` (alias en `tnsnames.ora`). El wallet se monta como secreto en `/opt/oracle/wallet` y el pod exporta `ORACLE_WALLET_PATH=/opt/oracle/wallet`. Opcional: `ORACLE_WALLET_PASSWORD`.

### Migraciones (Alembic)
Usa el script para cargar variables de `zordon/.secrets` y ejecutar Alembic con el wallet local:

```bash
./scripts/alembic-oracle.sh stamp head
./scripts/alembic-oracle.sh upgrade head
```

Para crear nuevas migraciones (revisa el SQL generado):
```bash
./scripts/alembic-oracle.sh revision -m "descripcion" --autogenerate
```

## 🐛 Debugging y Logs

Ver estado de los pods:
```bash
kubectl -n remedios get pods
```

Ver logs del dispatcher:
```bash
kubectl -n remedios logs -l app=dispatcher -f
```

Ver logs de la API interna:
```bash
kubectl -n remedios logs -l app=remedios-api -f
```

Ver logs de Kafka:
```bash
kubectl -n kafka logs -l app=kafka -f
```

## 📄 Licencia

MIT.
