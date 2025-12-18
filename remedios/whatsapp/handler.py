import base64
import json
import logging
import os
import sys

import requests
from flask import Flask, request, jsonify, abort

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Enviar logs a stdout para que Docker los capture
    ],
)

GRAPH_API_TOKEN = os.environ.get("GRAPH_API_TOKEN")
GRAPH_URL = os.environ.get("GRAPH_URL")
__HEADERS = {"Authorization": "Bearer {}".format(GRAPH_API_TOKEN)}
FFPROBE_BIN = os.environ.get("FFPROBE_BIN", "ffprobe")
INTERNAL_API_TOKEN = os.environ.get("INTERNAL_API_TOKEN")


sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger()

# Flask
app = Flask(__name__)


def _require_internal_token():
    """Aborta con 401 si el token interno no coincide."""
    if not INTERNAL_API_TOKEN:
        return

    auth_header = request.headers.get("Authorization", "")
    if auth_header != f"Bearer {INTERNAL_API_TOKEN}":
        abort(401, description="Token inválido")


def get_audio_metadata(request: dict) -> dict:
    """Extrae metadatos (id, mime_type) del mensaje de audio."""
    value = (
        request.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
    )
    messages = value.get("messages", [])
    if not isinstance(messages, list) or not messages:
        raise ValueError(f"Mensaje no encontrado: {value}")

    message = messages[0] or {}
    audio_data = message.get("audio", {})
    
    if not isinstance(audio_data, dict):
       raise ValueError(f"Mensaje no contiene audio válido: {message}")

    return {
        "audio_id": audio_data.get("id"),
        "mime_type": audio_data.get("mime_type")
    }


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

def get_message_id(request: dict) -> str:
    value = (
        request.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
    )
    messages = value.get("messages", [])
    if not isinstance(messages, list) or not messages:
        raise ValueError(f"Mensaje no encontrado: {value}")

    message = messages[0] or {}
    try:
        return message.get("id")
    except Exception as _:
        raise ValueError(f"Mensaje id no encontrado: {message}")

def get_message(request: dict) -> str:
    """Devuelve el texto del primer mensaje; si no hay texto, levanta ValueError."""
    value = (
        request.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
    )
    messages = value.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return ""

    message = messages[0] or {}
    text = message.get("text", {})
    if isinstance(text, dict) and "body" in text:
        return text.get("body", "") or ""

    raise ValueError(f"Mensaje sin texto: {text}")


def get_phone_number(request: dict) -> str:
    value = (
        request.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
    )
    # Remitente real del mensaje (WA ID del usuario)
    messages = value.get("messages", [])
    if isinstance(messages, list) and messages:
        sender = messages[0].get("from")
        if sender:
            return sender

    raise ValueError(f"No se pudo extraer el teléfono del remitente: {messages}")


def get_number_id(request: dict) -> str | None:
    """Devuelve el phone_number_id (número de negocio asignado por Meta)."""
    return (
        request.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("metadata", {})
        .get("phone_number_id")
    )

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
    """Permite invocación interna sin pasar por Flask."""
    if not GRAPH_API_TOKEN or not GRAPH_URL:
        raise RuntimeError("GRAPH_API_TOKEN o GRAPH_URL no definidos, no se puede enviar respuesta")

    _send_text_answer(text, phone_number, message_id, number_id)


@app.route("/internal/send_text_answer", methods=["POST"])
def send_text_answer_api():
    """Endpoint interno para enviar un texto y marcar el mensaje como leído."""
    _require_internal_token()
    payload = request.get_json(silent=True) or {}
    text = payload.get("text")
    phone_number = payload.get("phone_number")
    message_id = payload.get("message_id")
    number_id = payload.get("number_id")

    missing = [k for k, v in {"text": text, "phone_number": phone_number, "message_id": message_id, "number_id": number_id}.items() if not v]
    if missing:
        return jsonify({"status": "error", "message": f"Faltan campos: {', '.join(missing)}"}), 400

    try:
        send_text_answer(text, phone_number, message_id, number_id)
    except Exception as exc:  # pragma: no cover - red de terceros
        logger.exception("Error enviando respuesta a WhatsApp: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 502

    return jsonify({"status": "ok"}), 200


@app.route("/internal/extract_audio", methods=["POST"])
def extract_audio_api():
    """Endpoint interno que devuelve el audio en base64 dado su audio_id."""
    _require_internal_token()
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


def extract_audio(audio_id: str) -> bytes:
    """Descarga el audio desde Graph y devuelve los bytes."""
    if not GRAPH_API_TOKEN or not GRAPH_URL:
        raise RuntimeError("GRAPH_API_TOKEN o GRAPH_URL no definidos, no se puede obtener audio")

    logger.debug(f"buscando audio {audio_id}...")
    response_url = requests.get("{}/{}".format(GRAPH_URL, audio_id), headers=__HEADERS)
    logger.info("fetch meta URL status=%s", response_url.status_code)

    # Verifica si la solicitud fue exitosa
    if response_url.status_code == 200:
        json_url = json.loads(response_url.content)
        audio_response = requests.get(json_url["url"], headers=__HEADERS)
        content = audio_response.content or b""
        logger.info("audio download status=%s size=%s", audio_response.status_code, len(content))
        if audio_response.status_code == 200:
            audio_file = content
        else:
            logger.error(f"Error al descargar el archivo: {response_url.status_code}")
            logger.error(response_url.text)
            raise RuntimeError(f"Error al descargar el archivo: {response_url.status_code}")
    else:
        logger.error("URL no recibida :(")
        raise RuntimeError(f"URL no recibida: status={response_url.status_code}")

    return audio_file

# def send_audio_answer(message: dict, phone_number) -> None:
#     # Transcribir audio
#     audio = extract_audio(message, phone_number)
#     _pregunta = transcribe(audio)
#
#     # Preguntar LLM
#     respuesta_chatgpt = ask(_pregunta)
#
#     # Audio
#     _audio = generate_audio(respuesta_chatgpt)
#     # Subir el audio a meta
#     payload = {
#         "file": _audio,
#         "type": "MP3",
#         "messaging_product": "whatsapp"
#     }
#     media_response = requests.post(
#         "{}/{}/media".format(GRAPH_URL, phone_number),
#         headers=__HEADERS,
#         data=_audio,
#         params=payload,
#     )
#
#     if media_response.status_code == 200:
#         logger.debug("Mensaje subido :)")
#         # Enviar post para actualizar
#         _body = {
#             "messaging_product": "whatsapp",
#             "recipient_type": "individual",
#             "to": "<WHATSAPP_USER_PHONE_NUMBER>",
#             "type": "audio",
#             "audio": {
#                 "id": "{}".format(media_response.content)
#             }
#         }
#
#         requests.post(
#             "{}/{}/messages".format(GRAPH_URL, phone_number),
#             headers=__HEADERS,
#             json=_body,
#         )
#
#         logger.info("Mensaje de audio enviado")
#     else:
#         logger.error(f"{media_response.status_code} - {media_response.content}")
