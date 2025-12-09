from remedios.whatsapp.handler import get_message, get_phone_number, send_text_answer, extract_audio
from remedios.commons.stt.whisper import transcribe
from remedios.commons.stt.whisper import whisper_cpp
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

            # Preparar audio en wav para whisper-server cpp
            try:
                wav_bytes = whisper_cpp._to_wav_file(audio)
            except Exception as exc:
                logger.exception("No se pudo convertir audio a wav: %s", exc)
                wav_bytes = None

            cpp_txt = "[cpp no ejecutado]"
            turbo_txt = "[turbo no ejecutado]"
            # Transcripción cpp via server (servicio whisper-cpp:9000)
            if wav_bytes:
                try:
                    cpp_txt = whisper_cpp._transcribe_via_server(
                        wav_bytes, url="http://whisper-cpp:9000"
                    )
                except Exception as exc:
                    cpp_txt = f"[error cpp: {exc}]"

            # Transcripción turbo (servicio http whisper-turbo)
            try:
                turbo_txt = transcribe(audio)
            except Exception as exc:
                turbo_txt = f"[error turbo: {exc}]"

            final_msg = f"[cpp] {cpp_txt}\n[turbo] {turbo_txt}"
            logger.info(f"[IA-Transcription]: {final_msg}")

            send_text_answer(final_msg, message["from"], message["id"], phone_number)
            validate_message(message["from"], "IA", final_msg, "audio")
