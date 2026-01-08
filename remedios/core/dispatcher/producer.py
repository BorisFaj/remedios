import atexit
import json
import logging
import os
import socket
import sys
from datetime import datetime, timezone
from itertools import count

from flask import Flask, jsonify, request
from kafka import KafkaProducer

from remedios.commons.schemas import TextMessage, AudioMessage
from remedios.commons.utils import post_internal_api
from remedios.core.routing import route
from remedios.core.dispatcher.whatsapp_handler import (
    get_audio_metadata,
    get_message,
    get_message_id,
    get_number_id,
    get_phone_number,
)


# logs
sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger()

# Kafka
bootstrap = os.environ.get("BOOTSTRAP_SERVER")
if not bootstrap:
    raise RuntimeError("BOOTSTRAP_SERVER es obligatorio para inicializar el productor Kafka")

INTERNAL_API_URL = os.environ.get("INTERNAL_API_URL")
INTERNAL_API_TOKEN = os.environ.get("INTERNAL_API_TOKEN")

if not INTERNAL_API_URL:
    raise RuntimeError("INTERNAL_API_URL es obligatorio para contactar la API interna")
if not INTERNAL_API_TOKEN:
    raise RuntimeError("INTERNAL_API_TOKEN es obligatorio para contactar la API interna")

INTERNAL_API_URL = INTERNAL_API_URL.rstrip("/")

producer = KafkaProducer(
    bootstrap_servers=bootstrap,
    security_protocol="PLAINTEXT",
    partitioner=lambda key, all_parts, avail_parts, _c=count(): (
        (avail_parts or all_parts)[next(_c) % len(avail_parts or all_parts)]
        if (avail_parts or all_parts) else None
    ),
)
hostname = str.encode(socket.gethostname())

# Flask
app = Flask(__name__)
INTERNAL_API_TOKEN = os.environ.get("INTERNAL_API_TOKEN")


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
    entry = data.get("entry", [{}])[0]
    changes = entry.get("changes", [{}])
    value = changes[0].get("value", {})

    # Si hay statuses, siempre answer_request
    if "statuses" in value:
        return "answer_request"

    message = (
        value.get("messages", [{}])[0]
        if isinstance(value.get("messages"), list) and value.get("messages")
        else {}
    )

    message_type = message.get("type", "text")

    return route.get(message_type, "answer_request")

def dispatch_message(data):
    _value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    if "statuses" in _value and not _value.get("messages"):
        status = (_value.get("statuses") or [{}])[0] or {}
        logger.info(
            "Ignorando webhook de status id=%s for recipient=%s",
            status.get("id"),
            status.get("recipient_id"),
        )
        return None

    topic = get_topic(data)

    content = None
    if topic == route["audio"]:
        content = get_audio_metadata(data)
    else:
        content = get_message(data)

    msg_id = get_message_id(data)
    number_id = get_number_id(data)
    phone = get_phone_number(data)
    job_id = _create_job(content, phone, topic, number_id, msg_id)
    message = build_message(content, phone, msg_id, number_id, job_id, topic)

    send_to_kafka(message, topic)
    logger.info(f"Sent to kafka, job_id: {job_id}")

    return job_id

def build_message(content, phone, msg_id, number_id, job_id, topic) -> TextMessage | AudioMessage:
    base_args = {
        "phone": phone,
        "message_id": msg_id,
        "number_id": number_id,
        "job_id": job_id,
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc),
    }

    if topic == route["audio"]:
        # content es dict con audio_id, mime_type
        return AudioMessage(
            **base_args,
            audio_id=content["audio_id"],
            mime_type=content["mime_type"],
        )
    else:
        return TextMessage(
            **base_args,
            text=str(content)
        )


def _create_job(content, phone, topic, number_id, msg_id):
    payload = {
        "topic": topic,
        "phone": phone,
        "number_id": number_id,
        "message_id": msg_id,
        "content": content,
    }
    resp = post_internal_api(INTERNAL_API_URL, INTERNAL_API_TOKEN, "/internal/log_message", payload)
    try:
        data = resp.json() or {}
    except ValueError as exc:
        raise RuntimeError("Respuesta no JSON de API interna al registrar mensaje") from exc

    job_id = data.get("job_id")
    if not job_id:
        raise RuntimeError("API interna no devolvió job_id")
    return job_id
def send_to_kafka(msg, topic):
    """Encola el mensaje en Kafka."""
    payload = msg.model_dump_json().encode("utf-8")

    future = producer.send(
        topic,
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

            job_id = dispatch_message(data)

            return jsonify({"status": "success", "job_id": job_id}), 200

        except Exception as e:
            app.logger.exception("❌ Error: %s", e)
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
