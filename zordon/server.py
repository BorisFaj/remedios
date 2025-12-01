from flask import Flask, request, jsonify
import socket
from kafka import KafkaProducer
import json
import sys
import logging
from dotenv import load_dotenv, find_dotenv
import os
import atexit
import uuid

load_dotenv(find_dotenv(".env"))

# logs
sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Kafka
bootstrap = os.environ.get("BOOTSTRAP_SERVER")
if not bootstrap:
    raise RuntimeError("BOOTSTRAP_SERVER es obligatorio para inicializar el productor Kafka")

producer = KafkaProducer(
    bootstrap_servers=bootstrap,
    security_protocol="PLAINTEXT",
)
hostname = str.encode(socket.gethostname())

# Flask
app = Flask(__name__)

def on_success(metadata):
    app.logger.info(f"✅ Enviado a '{metadata.topic}' en offset {metadata.offset}")

def on_error(e):
  app.logger.info(f"❌ Error enviando mensaje a Kafka: {e}")

def verificar_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token and challenge:  # Asegurar que todos los valores existen
        if mode == "subscribe" and token == os.environ.get("WEBHOOK_VERIFY_TOKEN"):
            app.logger.info("✅ Webhook verificado correctamente")
            return challenge, 200
        else:
            return jsonify({"status": "error", "message": "Token de verificación inválido"}), 403
    return jsonify({"status": "error", "message": "Parámetros faltantes"}), 400


def get_topic(data):
    """Determina el topic correcto del mensaje."""

    changes = data["entry"][0].get("changes", [])
    value = changes[0].get("value", {})

    if "statuses" in value:
        return "whatsapp-text"

    message = value["messages"][0]
    message_type = message.get("type")

    if message_type == "text":
        return "whatsapp-text"
    elif message_type == "audio":
        return "whatsapp-audio"
    else:
        return "whatsapp-text"


def build_key(data):
    """Construye una clave estable para Kafka usando message_id y remitente."""

    try:
        changes = data["entry"][0].get("changes", [])
        value = changes[0].get("value", {})
        wa_id = value.get("contacts", [{}])[0].get("wa_id", "unknown")

        if "messages" in value and value["messages"]:
            message_id = value["messages"][0].get("id", str(uuid.uuid4()))
        elif "statuses" in value and value["statuses"]:
            message_id = value["statuses"][0].get("id", str(uuid.uuid4()))
        else:
            message_id = str(uuid.uuid4())

        key = f"{wa_id}_{message_id}"
    except Exception:
        key = str(uuid.uuid4())

    return key.encode("utf-8")


def send_to_kafka(data, topic):
    """Encola el mensaje en Kafka."""

    payload = json.dumps(data).encode("utf-8")
    key = build_key(data)

    future = producer.send(
        topic,
        key=key,
        value=payload,
    )
    future.add_callback(on_success)
    future.add_errback(on_error)
    producer.flush()

@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        return verificar_webhook()

    elif request.method == "POST":
        try:
            if request.content_type != "application/json":
                return jsonify({"status": "error", "message": "Unsupported Media Type"}), 415

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "No JSON received"}), 400

            app.logger.info(f"📩 Mensaje recibido: {json.dumps(data, indent=2)}")

            topic = get_topic(data)
            send_to_kafka(data, topic)

            return jsonify({"status": "success", "topic": topic}), 200

        except Exception as e:
            app.logger.info("❌ Error:", str(e))
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "Invalid request"}), 400


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


def cerrar_kafka_producer():
    """Cierra el Kafka Producer al finalizar el programa."""
    app.logger.info("🔴 Cerrando Kafka Producer...")
    producer.close()

atexit.register(cerrar_kafka_producer)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
