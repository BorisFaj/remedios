from flask import Flask, request, jsonify, abort
import sys
import logging
import os
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
