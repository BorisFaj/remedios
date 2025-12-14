from remedios.whatsapp.handler import get_message, get_phone_number, send_text_answer, extract_audio
from remedios.commons.stt.whisper import transcribe
from remedios.log.sender import validate_message
from remedios.commons.schemas import AudioMessage
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


def run(msg: AudioMessage) -> str:
    logger.info("Procesando AudioMessage job_id=%s audio_id=%s", msg.job_id, msg.audio_id)

    _message_dict = {
        "audio": {"id": msg.audio_id, "mime_type": msg.mime_type}
    }

    try:
        audio_bytes, duration = extract_audio(_message_dict, msg.phone)
        if duration is not None:
            msg.duration_seconds = duration
        transcript = transcribe(audio_bytes)
    except Exception as exc:
        logger.exception("Fallo transcripción job_id=%s. %s", msg.job_id, exc)
        transcript = ""

    transcript = transcript.strip() if transcript else ""
    final_response = transcript or "No pude entender tu audio."
    logger.info("Transcripcion exitosa")
        
    # Enviar respuesta al usuario
    send_text_answer(final_response, msg.phone, msg.message_id, msg.number_id)
    
    return final_response
