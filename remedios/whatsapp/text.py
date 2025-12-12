from remedios.whatsapp.handler import get_message, get_phone_number, send_text_answer
from remedios.commons.chat.fool import ask
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

    try:
        if message:
            if message.get("type") == "text":
                _message_body = message['text']['body']
                respuesta_chatgpt = ask(_message_body)

                logger.info(f"[HUMAN]: {_message_body}")
                logger.info(f"[IA-Chat]: {respuesta_chatgpt}")

                send_text_answer(respuesta_chatgpt, message["from"], message["id"], phone_number)

                logger.debug("Text answer sent ;)")
            else:
                logger.debug("pos na")
    except Exception as _:
        logger.error("Oye, se nos ha jodido esto")
        raise
