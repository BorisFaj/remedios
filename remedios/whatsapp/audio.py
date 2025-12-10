from remedios.whatsapp.handler import get_message, get_phone_number, send_text_answer, extract_audio
from remedios.commons.stt.whisper import whisper_turbo
from remedios.commons.log.sender import validate_message
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

            try:
                transcript = whisper_turbo.transcribe(audio)
            except Exception as exc:
                logger.exception("Error transcribiendo audio")
                transcript = ""

            transcript = transcript.strip() if transcript else ""
            final_msg = transcript or "No pude transcribir tu audio, intenta de nuevo."

            logger.info("[IA-Transcription] result=%s", final_msg)

            send_text_answer(final_msg, message["from"], message["id"], phone_number)
            validate_message(message["from"], "IA", final_msg, "audio")
