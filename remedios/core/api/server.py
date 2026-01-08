import base64
import json
import os
import sys
import logging
import requests
from flask import Flask, request, jsonify, abort
from datetime import datetime, timezone
from remedios.commons.schemas import TextMessage, AudioMessage
from remedios.log.sender import (
    validate_user,
    validate_message,
    create_job,
    update_job_status,
    save_job_result,
)
from remedios.core.routing import route

GRAPH_API_TOKEN = os.environ.get("GRAPH_API_TOKEN")
GRAPH_URL = os.environ.get("GRAPH_URL")
__HEADERS = {"Authorization": "Bearer {}".format(GRAPH_API_TOKEN)}

# logs
sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger()

# Flask
app = Flask(__name__)
INTERNAL_API_TOKEN = os.environ.get("INTERNAL_API_TOKEN")


def _check_internal_auth():
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {INTERNAL_API_TOKEN}"


def _post_graph(url: str, payload: dict) -> requests.Response:
    """Envia un POST a Graph y loguea cualquier error HTTP o de conexión."""
    try:
        resp = requests.post(url, headers=__HEADERS, json=payload, timeout=10)
        if resp.status_code >= 400:
            logger.error(
                "Graph POST %s failed status=%s body=%s", url, resp.status_code, resp.text
            )
        return resp
    except Exception as exc:  # pragma: no cover - red de terceros
        logger.error("Graph POST %s failed: %s", url, exc)
        raise


def _send_text_answer(text: str, phone_number: str, message_id: str, number_id: str):
    response_data = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "text": {"body": text},
        "context": {"message_id": message_id},
    }

    _post_graph(f"{GRAPH_URL}/{number_id}/messages", response_data)

    mark_read_data = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    _post_graph(f"{GRAPH_URL}/{number_id}/messages", mark_read_data)


def send_text_answer(text: str, phone_number: str, message_id: str, number_id: str):
    """Envía una respuesta de texto por WhatsApp."""
    if not GRAPH_API_TOKEN or not GRAPH_URL:
        raise RuntimeError("GRAPH_API_TOKEN o GRAPH_URL no definidos, no se puede enviar respuesta")

    _send_text_answer(text, phone_number, message_id, number_id)


def extract_audio(audio_id: str) -> bytes:
    """Descarga el audio desde Graph y devuelve los bytes."""
    if not GRAPH_API_TOKEN or not GRAPH_URL:
        raise RuntimeError("GRAPH_API_TOKEN o GRAPH_URL no definidos, no se puede obtener audio")

    logger.debug("buscando audio %s...", audio_id)
    response_url = requests.get("{}/{}".format(GRAPH_URL, audio_id), headers=__HEADERS)
    logger.info("fetch meta URL status=%s", response_url.status_code)

    if response_url.status_code == 200:
        json_url = json.loads(response_url.content)
        audio_response = requests.get(json_url["url"], headers=__HEADERS)
        content = audio_response.content or b""
        logger.info("audio download status=%s size=%s", audio_response.status_code, len(content))
        if audio_response.status_code == 200:
            audio_file = content
        else:
            logger.error("Error al descargar el archivo: %s", audio_response.status_code)
            logger.error(audio_response.text)
            raise RuntimeError(f"Error al descargar el archivo: {audio_response.status_code}")
    else:
        logger.error("URL no recibida :(")
        raise RuntimeError(f"URL no recibida: status={response_url.status_code}")

    return audio_file


@app.before_request
def _protect_internal_paths():
    path = request.path or ""
    if path.startswith("/internal/"):
        if not INTERNAL_API_TOKEN:
            return abort(403)
        if not _check_internal_auth():
            return abort(401)

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

    message_id = validate_message(sender=phone, receiver=None, message=msg_content, message_type=topic,
                                  message_id=msg_id,
                                  number_id=number_id)

    if message_id is None:
        raise RuntimeError("No se pudo registrar el mensaje en la base de datos")

    job_id = create_job(job_type=topic, source_message_id=message_id, user_id=user.id)
    if job_id is None:
        raise RuntimeError("No se pudo crear el job asociado al mensaje")
    logger.info("Logged to DB")

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


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/internal/log_message", methods=["POST"])
def internal_log_message():
    if not _check_internal_auth():
        abort(401)
    payload = request.get_json(silent=True) or {}
    topic = payload.get("topic")
    phone = payload.get("phone")
    number_id = payload.get("number_id")
    message_id = payload.get("message_id")
    content = payload.get("content")

    missing = [k for k, v in {"topic": topic, "phone": phone, "message_id": message_id}.items() if not v]
    if missing:
        return jsonify({"error": f"topic, phone y message_id son requeridos; faltan: {', '.join(missing)}"}), 400

    try:
        job_id = log_db(content, phone, topic, number_id, message_id)
    except Exception as exc:
        logger.exception("Error registrando mensaje en DB")
        return jsonify({"error": str(exc)}), 500

    return jsonify({"status": "ok", "job_id": job_id}), 200


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


@app.route("/internal/send_text_answer", methods=["POST"])
def internal_send_text_answer():
    if not _check_internal_auth():
        abort(401)
    payload = request.get_json(silent=True) or {}
    text = payload.get("text")
    phone_number = payload.get("phone_number")
    message_id = payload.get("message_id")
    number_id = payload.get("number_id")

    missing = [
        k
        for k, v in {
            "text": text,
            "phone_number": phone_number,
            "message_id": message_id,
            "number_id": number_id,
        }.items()
        if not v
    ]
    if missing:
        return jsonify({"status": "error", "message": f"Faltan campos: {', '.join(missing)}"}), 400

    try:
        send_text_answer(text, phone_number, message_id, number_id)
    except Exception as exc:  # pragma: no cover - red de terceros
        logger.exception("Error enviando respuesta a WhatsApp: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 502

    return jsonify({"status": "ok"}), 200


@app.route("/internal/extract_audio", methods=["POST"])
def internal_extract_audio():
    if not _check_internal_auth():
        abort(401)
    payload = request.get_json(silent=True) or {}
    audio_id = payload.get("audio_id")
    if not audio_id:
        return jsonify({"status": "error", "message": "audio_id requerido"}), 400

    try:
        audio_file = extract_audio(audio_id)
    except Exception as exc:  # pragma: no cover - red de terceros
        logger.exception("Error obteniendo audio %s: %s", audio_id, exc)
        return jsonify({"status": "error", "message": str(exc)}), 502

    encoded = base64.b64encode(audio_file).decode("utf-8")
    return jsonify(
        {
            "status": "ok",
            "audio_id": audio_id,
            "audio_b64": encoded,
            "size_bytes": len(audio_file),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
