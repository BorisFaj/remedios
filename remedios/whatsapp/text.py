from remedios.whatsapp.handler import get_message, get_phone_number, send_text_answer
from remedios.commons.chat.fool import ask
from remedios.commons.schemas import TextMessage
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


def run(message: TextMessage):
    logger.info("Procesando mensaje de texto")
    logger.info(f"from: {message.phone}")

    try:
        if message:
            respuesta_modelo = ask(message.text)

            logger.info(f"[HUMAN]: {message.text}")
            logger.info(f"[IA-Chat]: {respuesta_modelo}")

            send_text_answer(text=respuesta_modelo, number_id=message.number_id, message_id=message.message_id,
                             phone_number=message.phone)

            logger.debug("Text answer sent ;)")

    except Exception as _:
        logger.error("Oye, se nos ha jodido esto")
        raise
