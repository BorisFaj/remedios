import io
from io import BytesIO

import requests
import json
import os
import logging
import sys
import subprocess
import json as jsonlib

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Enviar logs a stdout para que Docker los capture
    ],
)

logger = logging.getLogger(__name__)

GRAPH_API_TOKEN = os.environ.get("GRAPH_API_TOKEN")
GRAPH_URL = os.environ.get("GRAPH_URL")
__HEADERS = {"Authorization": "Bearer {}".format(GRAPH_API_TOKEN)}
FFPROBE_BIN = os.environ.get("FFPROBE_BIN", "ffprobe")


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
    return (
        request.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("metadata", {})
        .get("phone_number_id")
    )


def send_text_answer(text: str, n_to: int, message_id: int, phone_number: int) -> None:

    if not GRAPH_API_TOKEN or not GRAPH_URL:
        logger.error("GRAPH_API_TOKEN o GRAPH_URL no definidos, no se puede enviar respuesta")
        return

    # Envia una respuesta
    response_data = {
        "messaging_product": "whatsapp",
        "to": n_to,
        "text": {"body": text},
        "context": {"message_id": message_id},
    }

    _post_graph(f"{GRAPH_URL}/{phone_number}/messages", response_data)

    # Marca el mensaje como leido
    mark_read_data = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    _post_graph(f"{GRAPH_URL}/{phone_number}/messages", mark_read_data)

def extract_audio(message: dict, phone_number: int) -> BytesIO:
    audio_id = message["audio"]["id"]
    # mime_type = message["audio"]["mime_type"]

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
            duration = _probe_duration_bytes(content)
            if duration is not None:
                logger.info("audio duration=%.2fs (ffprobe)", duration)
            else:
                logger.warning("No se pudo obtener duración con ffprobe")
            audio_file = content
        else:
            logger.error(f"Error al descargar el archivo: {response_url.status_code}")
            logger.error(response_url.text)
            return io.BytesIO()
    else:
        logger.error("URL no recibida :(")
        return io.BytesIO()

    return audio_file


def _probe_duration_bytes(data: bytes):
    """Devuelve duración en segundos usando ffprobe desde stdin; None si falla."""
    try:
        cmd = [
            FFPROBE_BIN,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            "-i",
            "pipe:0",
        ]
        out = subprocess.check_output(cmd, input=data, stderr=subprocess.STDOUT)
        data = jsonlib.loads(out.decode("utf-8", "ignore"))
        dur = float(data.get("format", {}).get("duration", 0.0))
        return dur
    except Exception as exc:
        logger.error("ffprobe failed to get duration: %s", exc)
        return None

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
