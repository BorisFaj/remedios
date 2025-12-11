# Remedios

**Webhook de WhatsApp escalable y ligero, diseñado para Oracle Cloud Always Free (ARM).**

Remedios es una plataforma de procesamiento de mensajes de WhatsApp que despliega una arquitectura de microservicios robusta y escalable sobre Kubernetes (k3s), optimizada para ejecutarse en instancias ARM64 gratuitas de Oracle Cloud (Ampere), pero capaz de escalar horizontalmente añadiendo más nodos.

## 🚀 Objetivo del Proyecto

El objetivo principal es permitir el despliegue de un stack completo de procesamiento de IA (Whisper, LLMs, etc.) utilizando recursos gratuitos (Oracle Always Free), sin sacrificar la calidad de la arquitectura.

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
    - **Webhook Server** (`remedios/core/dispatcher.py`): Recibe webhooks de WhatsApp y los publica en Kafka.
    - **Remetext** (`remedios`): Servicio de procesamiento de texto.
    - **Whisper Worker**: Servicio de transcripción de audio optimizado para ARM64 (usando `whisper.cpp` o `whisper-turbo`).

## 📋 Requisitos Previos

1.  **Instancia Oracle Cloud**: Ubuntu 22.04 (ARM64 Ampere).
2.  **Dominio**: Un dominio público apuntando a la IP pública de tu instancia.
3.  **Tailscale**: Una cuenta de Tailscale y una Auth Key (reusable y efímera recomendada).
4.  **GitHub Token**: Un Personal Access Token (Classic) con permiso `read:packages` para descargar las imágenes desde GHCR.

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
GHCR_TOKEN=ghp_tu_token_github
# Opcional: Configuración de Whisper
WHISPER_MODEL=ggml-large-v3-turbo-q5_0.bin
```

### 2. Configurar Inventario

Edita `zordon/ansible/inventory.ini`. Para un despliegue "Single Node" (todo en una máquina), solo define el `master`:

```ini
[master]
tu-usuario@tu-ip-publica

[nodes]
# Deja esto vacío si solo usas un nodo
```

### 3. Desplegar Cluster e Infraestructura

Ejecuta el playbook de cluster. Esto instalará k3s, Tailscale, Traefik y Kafka:

```bash
ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/cluster.yml
```

### 4. Desplegar Servicios

Una vez el cluster esté arriba, despliega los servicios de aplicación (Remedios, Whisper, etc.):

```bash
ansible-playbook -i zordon/ansible/inventory.ini zordon/ansible/services.yml
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

- `remedios/`: Código fuente de la aplicación (lógica de negocio, servicios de texto y core).
- `zordon/`: Infraestructura y despliegue.
    - `ansible/`: Playbooks de automatización.
    - `deploy/`: Manifiestos de Kubernetes (YAMLs).

## 🐛 Debugging y Logs

Ver estado de los pods:
```bash
kubectl -n remedios get pods
```

Ver logs del webhook:
```bash
kubectl -n remedios logs -l app=remedios -f
```

Ver logs de Kafka:
```bash
kubectl -n kafka logs -l app=kafka -f
```

## 📄 Licencia

MIT.
