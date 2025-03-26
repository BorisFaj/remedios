from whatsapp import get_message, get_phone_number, send_text_answer
from chat.llamacpp_server import ask
from log.sender import save_message, format_conversation_history
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
        if message.get("type") == "text":
            _message_body = message['text']['body']
            chat_history = format_conversation_history(message["from"], _message_body)
            logger.info(f"history: {chat_history}")
            respuesta_chatgpt = ask(chat_history)

            logger.info(f"[HUMAN]: {_message_body}")
            logger.info(f"[IA-Chat]: {respuesta_chatgpt}")

            send_text_answer(respuesta_chatgpt, message["from"], message["id"], phone_number)
            save_message(message["from"], "IA", _message_body, "text")
            save_message("IA", message["from"], respuesta_chatgpt, "text")
            logger.debug("Text answer sent ;)")
        else:
            logger.debug("pos na")
