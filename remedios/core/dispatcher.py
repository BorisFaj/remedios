from flask import Flask, request, jsonify, abort
import socket
from kafka import KafkaProducer
import json
import sys
import logging
import os
import atexit
from datetime import datetime, timezone
from remedios.commons.schemas import TextMessage, AudioMessage
from remedios.whatsapp.handler import get_phone_number, get_message, get_message_id, get_number_id, get_audio_metadata
from remedios.log.sender import (
    validate_user,
    validate_message,
    create_job,
    update_job_status,
    save_job_result,
)
from remedios.core.routing import route
from itertools import count


# logs
sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger()

# Kafka
bootstrap = os.environ.get("BOOTSTRAP_SERVER")
if not bootstrap:
    raise RuntimeError("BOOTSTRAP_SERVER es obligatorio para inicializar el productor Kafka")

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


def _check_internal_auth():
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {INTERNAL_API_TOKEN}"


@app.before_request
def _protect_internal_paths():
    path = request.path or ""
    if path.startswith("/internal/"):
        if not INTERNAL_API_TOKEN:
            return abort(403)
        if not _check_internal_auth():
            return abort(401)


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

def log_db(content_or_meta, phone, topic, number_id, msg_id):
    """
    Loggea en DB.
    Si es texto, content_or_meta es el texto.
    Si es audio, content_or_meta es dict con metadata, guardamos algo representativo.
    """
    user = validate_user(phone_number=phone)
    
    msg_content = content_or_meta
    if topic == "transcription_requests" and isinstance(content_or_meta, dict):
        msg_content = f"[Audio ID: {content_or_meta.get('audio_id')}]"
    
    # Asegurar que sea string para la DB
    if not isinstance(msg_content, str):
        msg_content = str(msg_content)

    message_id = validate_message(sender=phone, receiver=None, message=msg_content, message_type=topic, message_id=msg_id,
                                  number_id=number_id)

    if message_id is None:
        raise RuntimeError("No se pudo registrar el mensaje en la base de datos")

    job_id = create_job(job_type=topic, source_message_id=message_id, user_id=user.id)
    if job_id is None:
        raise RuntimeError("No se pudo crear el job asociado al mensaje")
    logger.info("Logged to DB")

    return job_id

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
    job_id = log_db(content, phone, topic, number_id, msg_id)
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


@app.route("/internal/job_status", methods=["POST"])
def internal_job_status():
    if not _check_internal_auth():
        abort(401)
    payload = request.get_json(silent=True) or {}
    job_id = payload.get("job_id")
    status = payload.get("status")
    error_message = payload.get("error_message")
    if not job_id or not status:
        return jsonify({"error": "job_id and status are required"}), 400
    ok = update_job_status(job_id, status, error_message)
    if not ok:
        return jsonify({"error": "failed to update status"}), 500
    return jsonify({"status": "ok"}), 200


@app.route("/internal/job_result", methods=["POST"])
def internal_job_result():
    if not _check_internal_auth():
        abort(401)
    payload = request.get_json(silent=True) or {}
    job_id = payload.get("job_id")
    result = payload.get("result")
    output_ref = payload.get("output_ref")
    duration_ms = payload.get("duration_ms")
    started_at = payload.get("started_at")
    finished_at = payload.get("finished_at")
    audio_duration_seconds = payload.get("audio_duration_seconds")

    if not job_id or result is None:
        return jsonify({"error": "job_id and result are required"}), 400

    # Parse timestamps in ISO format if provided.
    def parse_dt(val):
        if not val:
            return None
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return None

    ok = save_job_result(
        job_id,
        result,
        output_ref=output_ref,
        duration_ms=duration_ms,
        started_at=parse_dt(started_at),
        finished_at=parse_dt(finished_at),
        audio_duration_seconds=audio_duration_seconds,
    )
    if not ok:
        return jsonify({"error": "failed to save job_result"}), 500
    return jsonify({"status": "ok"}), 200


def cerrar_kafka_producer():
    """Cierra el Kafka Producer al finalizar el programa."""
    app.logger.info("🔴 Cerrando Kafka Producer...")
    producer.close()

atexit.register(cerrar_kafka_producer)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
