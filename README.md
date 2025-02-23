# Proyecto: Remedios

## SETUP AWS

# 🚀 Restaurar una instancia EC2 con Kafka, Flask y Webhook de WhatsApp

## **🛠️ 1️⃣ Lanzar una nueva instancia desde la AMI**
Si ya creaste una **AMI estable**, puedes lanzar una nueva instancia EC2 siguiendo estos pasos:

1. **Ve a AWS EC2 → AMIs**.
2. **Selecciona la AMI** (`kafka-whatsapp-image` o el nombre que le pusiste).
3. **Haz clic en "Launch instance from image"**.
4. **Selecciona el mismo tipo de instancia** (Ej. `t3.micro` o `t3.small`).
5. **Elige el mismo Security Group** (para que los puertos estén abiertos correctamente).
6. **Haz clic en "Launch Instance"**.

---

## **🌐 2️⃣ Configurar las reglas de los puertos en AWS**
Después de lanzar la nueva instancia, **asegúrate de que los puertos estén abiertos**.

🔹 **Ve a AWS EC2 → Security Groups → Editar reglas de entrada (Inbound Rules).**  
🔹 **Configura las siguientes reglas:**

| Puerto | Protocolo | Origen | Descripción |
|--------|----------|--------|-------------|
| **22** | **TCP** | **Tu IP** (`X.X.X.X/32`) | Para conectarte por SSH |
| **80** | **TCP** | **0.0.0.0/0** | Para tráfico HTTP (nginx y Let's Encrypt) |
| **443** | **TCP** | **0.0.0.0/0** | Para HTTPS (nginx y Let's Encrypt) |
| **3000** | **TCP** | **0.0.0.0/0** | Para el servidor Flask (Webhook de WhatsApp) |
| **9092** | **TCP** | **Tu IP pública** (`X.X.X.X/32`) | Para conectar Kafka desde tu PC |
| **2181** | **TCP** | **0.0.0.0/0** | Para Zookeeper (interno, puede ser opcional) |

📌 **Para mayor seguridad, en `9092` puedes permitir solo la IP de tu PC, en lugar de `0.0.0.0/0`.**  

---

## **🚀 3️⃣ Iniciar los servicios en la nueva instancia**
Una vez que la instancia esté en marcha:

### **1️⃣ Conectarse por SSH a la nueva instancia**
```bash
ssh -i "tu-clave.pem" ubuntu@NUEVA_IP
```
actualizar la IP en el fichero .secrets
actualizar la IP en https://www.duckdns.org/
volver a lanzar el servidor

```bash
pkill gunicorn
gunicorn -w 4 -b 0.0.0.0:3000 server:app --daemon
```

Probar Flask

```bash
curl -X POST -H "Content-Type: application/json" -d '{"message": "Test desde Flask"}' http://NUEVA_IP:3000/webhook
```

Probar nginx
```bash
curl -Ik https://remediosapi.duckdns.org/
```

Si devuelve forbidden está fallando nginx, si devuelve cualquier otro error está fallando Flask.
Se deberia ver algo así: 

```bash
HTTP/2 200
server: nginx/1.18.0 (Ubuntu)
content-type: text/html
```

#### HealthChecks
# 📋 Lista de comprobaciones con `curl`

| Comando | Descripción |
|---------|------------|
| `curl -I http://NUEVA_IP/` | Verifica si Nginx responde en HTTP |
| `curl -Ik https://remediosapi.duckdns.org/` | Verifica si Nginx responde en HTTPS |
| `curl -Ik https://remediosapi.duckdns.org/webhook` | Prueba la redirección a Flask |
| `curl -I http://127.0.0.1:3000/webhook` | Prueba si Flask responde localmente sin Nginx |
| `curl -X POST -H "Content-Type: application/json" -d '{"message": "Test"}' http://127.0.0.1:3000/webhook` | Envía un mensaje de prueba a Flask |
| `nc -zv NUEVA_IP 9092` | Verifica si Kafka acepta conexiones en el puerto 9092 |

Crear topic de prueba:
```bash
docker exec -it kafka kafka-topics.sh --create --topic whatsapp-events --bootstrap-server $(curl -s ifconfig.me):9092 --partitions 1 --replication-factor 1
```

Listar topics:

docker exec -it kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

Conectar al topic:

docker exec -it kafka kafka-console-producer.sh --bootstrap-server localhost:9092 --topic whatsapp-events

Leer todos los mensajes de kafka:

docker exec -it kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic whatsapp-events --from-beginnin

## Descripción
Este proyecto integra la API de WhatsApp de Meta con un servidor local Flask, expuesto a internet mediante ngrok, para procesar mensajes de texto y audio utilizando modelos de inteligencia artificial. Además, se conecta a un servidor GPT4All para generar respuestas dinámicas y contextuales. Aunque el sistema actual no utiliza un broker de mensajería, se contempla la incorporación futura de Kafka para mejorar la escalabilidad y la arquitectura del sistema.

![Diagrama de la arquitectura](/diagrama.webp)

## Arquitectura del Proyecto

El flujo principal de datos sigue estos pasos:

1. **API de WhatsApp**: Recibe y envía mensajes desde la plataforma de WhatsApp. Se comunica con `miApp` mediante un webhook.
2. **Ngrok**: Expone el servidor local `miApp` a internet, facilitando la comunicación con la API de WhatsApp.
3. **miApp (Flask)**:
   - Procesa mensajes de texto y audio.
   - Ejecuta modelos de inteligencia artificial para generar y procesar contenido.
   - Interactúa con el servidor GPT4All para obtener respuestas basadas en IA.
4. **GPT4All**: Proporciona respuestas contextuales basadas en el contenido del mensaje recibido.

### Diagrama de Arquitectura

```mermaid
graph TD
    subgraph WhatsApp
        A[WhatsApp API]
    end
    A -->|Webhook| B[Ngrok]
    B --> C[miApp (Flask)]
    C -->|Procesamiento IA| D[Modelos IA]
    C -->|Consulta| E[GPT4All]
    subgraph Futuro
        F[Kafka (Planeado)]
    end
    A -.->|Mensajería Escalable| F
    F -.->|Intermediario| C
```

## Requisitos

- Python 3.8+
- Flask
- Ngrok
- GPT4All
- Bibliotecas adicionales para modelos IA (especificadas en `requirements.txt`)

## Instalación y Configuración

1. Clona este repositorio:
   ```bash
   git clone https://github.com/tu-usuario/whatsapp-ai-assistant.git
   cd whatsapp-ai-assistant
   ```

2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Configura Ngrok para exponer el servidor local:
   ```bash
   ngrok http 5000
   ```
   Copia la URL generada por ngrok y configúrala como webhook en la API de WhatsApp.

4. Inicia el servidor Flask:
   ```bash
   python app.py
   ```

## Uso

- Envía mensajes de texto o audio a través de WhatsApp.
- El servidor procesará los mensajes y generará respuestas contextuales utilizando modelos de IA.

## Contribuciones

¡Las contribuciones son bienvenidas! Si tienes ideas para mejorar este proyecto, no dudes en abrir un issue o enviar un pull request.

## Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo `LICENSE` para más detalles.

## Disclaimer

Cualquier parecido con la realidad es pura coincidencia.

---

¡Esperamos que disfrutes experimentando con este proyecto y explorando las posibilidades de integrar IA en WhatsApp!
