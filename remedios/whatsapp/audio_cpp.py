import logging
import sys

from remedios.commons.log.sender import validate_message
from remedios.commons.stt.whisper import whisper_cpp
from remedios.whatsapp.handler import extract_audio, get_message, get_phone_number, send_text_answer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run(request: dict):
    logger.info("Incoming webhook message (cpp)")
    message = get_message(request)
    phone_number = get_phone_number(request)
    logger.info("from: %s", phone_number)

    if not message or message.get("type") != "audio":
        logger.info("Mensaje no es audio, ignorando")
        return

    logger.info("Extrayendo audio...")
    audio = extract_audio(message, phone_number)
    logger.info("Audio extraído.")

    try:
        wav_bytes = whisper_cpp._to_wav_file(audio)
    except Exception as exc:
        logger.exception("No se pudo convertir audio a wav: %s", exc)
        wav_bytes = None

    transcript = ""
    if wav_bytes:
        try:
            transcript = whisper_cpp._transcribe_via_server(
                wav_bytes, url="http://whisper-cpp:9000"
            )
        except Exception as exc:
            logger.exception("Error transcribiendo con whisper-cpp: %s", exc)
            transcript = ""

    final_msg = (transcript or "").strip() or "No pude transcribir tu audio, intenta de nuevo."
    logger.info("[IA-Transcription cpp] result=%s", final_msg)

    send_text_answer(final_msg, message["from"], message["id"], phone_number)
    validate_message(message["from"], "IA", final_msg, "audio")
