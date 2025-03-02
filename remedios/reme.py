from whatsapp import get_message, get_phone_number, send_text_answer, extract_audio
from stt.whisper import transcribe
from chat.fool import ask
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Enviar logs a stdout para que Docker los capture
    ],
)

logger = logging.getLogger(__name__)

def run(request: dict):
    logger.info("Incoming webhook message")
    message = get_message(request)
    phone_number = get_phone_number(request)
    logger.info(f"from: {phone_number}")

    if message:
        if message.get("type") == "text":
            _message_body = message['text']['body']
            respuesta_chatgpt = ask(_message_body)
            # respuesta_chatgpt = "recibido lokiii"

            logger.info(f"[HUMAN]: {_message_body}")
            logger.info(f"[IA-Chat]: {respuesta_chatgpt}")

            send_text_answer(respuesta_chatgpt, message["from"], message["id"], phone_number)

            logger.debug("Text answer send ;)")
        elif message.get("type") == "audio":
            logger.info("Extrayendo audio...")
            audio = extract_audio(message, phone_number)
            logger.info("Audio extraido.")
            # _pregunta = whats.transcribe(stt)
            # answer = whats.ask(_pregunta)
            # whats.send_text_answer(answer, message["from"], message["id"], phone_number)
            # whats.send_audio_answer(answer, phone_number)
            transcription = transcribe(audio)
            logger.info(f"[IA-Transcription]: {transcription}")
            send_text_answer(transcription, message["from"], message["id"], phone_number)
        else:
            logger.debug("pos na")