# 📦 Remedios

Remedios es un sistema modular para integrar y procesar mensajes de WhatsApp.

## 🚀 Características

- Recibe mensajes de WhatsApp a través de un webhook.
- Encola los mensajes en Kafka para su procesamiento asíncrono.
- Implementación modular para facilitar la extensión.

## 🛠 Instalación

### Requisitos previos

- Python 3.10
- Docker
- Kafka y Zookeeper en ejecución

### Instalación

1. Clona el repositorio:
   ```sh
   git clone https://github.com/BorisFaj/remedios-public.git
   cd remedios-public
   ```

2. Instala las dependencias:
   ```sh
   pip install -r server_requirements.txt
   ```

3. Configura las variables de entorno.

4. Ejecuta el servicio:
   ```sh
   python kafka/server.py
   ```

## 📜 Uso

1. Configura un webhook en tu cuenta de WhatsApp Business API.
2. Envia mensajes y observa cómo son encolados en Kafka.


## 🔧 Configuración

Remedios requiere dos tipos de configuración:  

### 1️⃣ `.env` para `server.py`
Este archivo define las credenciales de acceso a Redpanda/Kafka:

```ini
REDPANDA_PASS={mi_pass}
REDPANDA_USER={mi_user}
BOOTSTRAP_SERVER={mi_server}
```

### 2️⃣ Variables de entorno para Docker
Para levantar correctamente el Docker, remedios necesita que le pases estas variables de entorno:

```ini
GRAPH_URL={url}
GRAPH_API_TOKEN={token}
HF_TOKEN={token}
REDPANDA_PASS={pass}
REDPANDA_USER={user}
KAFKA_TOPIC={topic}
BOOTSTRAP_SERVER={server}
```

📌 **Comportamiento del `super_consumer` según `KAFKA_TOPIC`**:

- **`whatsapp-text`** → Levanta un consumidor de texto con el modelo **Mistral NeMo Instruct**.
- **`whatsapp-audio`** → Levanta un consumidor de audio con el modelo **Whisper 3 Turbo**.


## 🛠 Contribuir

¡Contribuciones bienvenidas! Si quieres mejorar el proyecto, sigue estos pasos:

1. Haz un **fork** del repo.
2. Crea una rama con tu mejora: `git checkout -b mi-mejora`.
3. Haz commit de los cambios: `git commit -m "Añadida nueva funcionalidad"`.
4. Sube tu rama: `git push origin mi-mejora`.
5. Abre un **pull request**.

## 📄 Licencia

Este proyecto está bajo la licencia Apache 2.0. Consulta el archivo `LICENSE` para más detalles.
