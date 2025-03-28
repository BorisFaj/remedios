from whatsapp import get_message, get_phone_number, send_text_answer, extract_audio
from stt.whisper import transcribe
from log.sender import validate_message
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
)
logger = logging.getLogger(__name__)


def run(request: dict):
    logger.info("Incoming webhook message")
    message = get_message(request)
    phone_number = get_phone_number(request)
    logger.info(f"from: {phone_number}")

    if message:
        if message.get("type") == "audio":
            logger.info("Extrayendo audio...")
            audio = extract_audio(message, phone_number)
            logger.info("Audio extraído.")

            transcription = transcribe(audio)
            logger.info(f"[IA-Transcription]: {transcription}")

            send_text_answer(transcription, message["from"], message["id"], phone_number)
            validate_message(message["from"], "IA", transcription, "audio")
