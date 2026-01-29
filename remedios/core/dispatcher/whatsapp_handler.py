import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(
            sys.stdout
        )  # Enviar logs a stdout para que Docker los capture
    ],
)

sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger()


def get_audio_metadata(request: dict) -> dict:
    """Extrae metadatos (id, mime_type) del mensaje de audio."""
    value = request.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    messages = value.get("messages", [])
    if not isinstance(messages, list) or not messages:
        raise ValueError(f"Mensaje no encontrado: {value}")

    message = messages[0] or {}
    audio_data = message.get("audio", {})

    if not isinstance(audio_data, dict):
        raise ValueError(f"Mensaje no contiene audio válido: {message}")

    return {"audio_id": audio_data.get("id"), "mime_type": audio_data.get("mime_type")}


def get_message_id(request: dict) -> str:
    value = request.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
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
    value = request.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    messages = value.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return ""

    message = messages[0] or {}
    text = message.get("text", {})
    if isinstance(text, dict) and "body" in text:
        return text.get("body", "") or ""

    raise ValueError(f"Mensaje sin texto: {text}")


def get_phone_number(request: dict) -> str:
    value = request.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
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
