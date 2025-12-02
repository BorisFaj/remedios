from apps.common.messaging import extract_request_context, logger
from apps.common.whatsapp import send_text_answer, extract_audio
from apps.common.stt.whisper import transcribe
from apps.common.log.sender import validate_message


def run(request: dict):
    message, phone_number = extract_request_context(request, expected_type="audio")
    if not message:
        return

    logger.info("Extrayendo audio...")
    audio = extract_audio(message, phone_number)
    logger.info("Audio extraído.")

    transcription = transcribe(audio)
    logger.info(f"[IA-Transcription]: {transcription}")

    send_text_answer(transcription, message["from"], message["id"], phone_number)
    validate_message(message["from"], "IA", transcription, "audio")
