import io
from io import BytesIO

import flask
import requests
import json
import logging

import server
from chat.gpt4all import ask

from transcribe.whisper import *
from audio.tts.facebook import *

# Variables de entorno
GRAPH_API_TOKEN = server.GRAPH_API_TOKEN
GRAPH_URL = server.GRAPH_URL

__HEADERS = {"Authorization": "Bearer {}".format(GRAPH_API_TOKEN)}
_PROCESSED_AUDIOS = []  # homemade kafka =)

logger = logging.getLogger()

def get_message(request: flask.request) -> json:
    return(
        request.json.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("messages", [{}])[0]
    )

def get_phone_number(request: flask.request) -> int:
    return (
        request.json.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("metadata", {})
        .get("phone_number_id")
    )


def send_text_answer(text: str, n_to: int, message_id: int, phone_number: int) -> None:
    # Envia una respuesta
    response_data = {
        "messaging_product": "whatsapp",
        "to": n_to,
        "text": {"body": text},
        "context": {"message_id": message_id},
    }

    # Envia el mensaje de respuesta
    requests.post(
        "{}/{}/messages".format(GRAPH_URL, phone_number),
        headers=__HEADERS,
        json=response_data,
    )

    # Marca el mensaje como leido
    mark_read_data = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    requests.post(
        "{}/{}/messages".format(GRAPH_URL, phone_number),
        headers=__HEADERS,
        json=mark_read_data,
    )

def validate_audio_id(business_phone_number_id: int, audio_id: int):
    if audio_id in _PROCESSED_AUDIOS:
        logger.warning(f"{business_phone_number_id} esta impaciente, que se espere")
        return ""

def extract_audio(message: dict, phone_number: int) -> BytesIO:
    audio_id = message["audio"]["id"]
    # mime_type = message["audio"]["mime_type"]

    validate_audio_id(phone_number, audio_id)

    logger.debug(f"buscando audio {audio_id}...")
    response_url = requests.get("{}/{}".format(GRAPH_URL, audio_id), headers=__HEADERS)

    # Verifica si la solicitud fue exitosa
    if response_url.status_code == 200:
        json_url = json.loads(response_url.content)
        audio_response = requests.get(json_url["url"], headers=__HEADERS)
        if audio_response.status_code == 200:
            # with open("audio_descargado.ogg", "wb") as file:
            #     file.write(audio_response.content)  # me lo guardo a ver que onda
            audio_file = audio_response.content
        else:
            logger.error(f"Error al descargar el archivo: {response_url.status_code}")
            logger.error(response_url.text)
            return io.BytesIO()
    else:
        logger.error("URL no recibida :(")
        return io.BytesIO()

    _PROCESSED_AUDIOS.append(audio_id)  # Toodo OK

    return audio_file

def send_audio_answer(message: dict, phone_number) -> None:
    # Transcribir audio
    audio = extract_audio(message, phone_number)
    _pregunta = transcribe(audio)

    # Preguntar LLM
    respuesta_chatgpt = ask(_pregunta)

    # TTS
    _audio = generate_audio(respuesta_chatgpt)
    # Subir el audio a meta
    payload = {
        "file": _audio,
        "type": "MP3",
        "messaging_product": "whatsapp"
    }
    media_response = requests.post(
        "{}/{}/media".format(GRAPH_URL, phone_number),
        headers=__HEADERS,
        data=_audio,
        params=payload,
    )

    if media_response.status_code == 200:
        logger.debug("Mensaje subido :)")
        # Enviar post para actualizar
        _body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": "<WHATSAPP_USER_PHONE_NUMBER>",
            "type": "audio",
            "audio": {
                "id": "{}".format(media_response.content)
            }
        }

        requests.post(
            "{}/{}/messages".format(GRAPH_URL, phone_number),
            headers=__HEADERS,
            json=_body,
        )

        logger.info("Mensaje de audio enviado")
    else:
        logger.error(f"{media_response.status_code} - {media_response.content}")
