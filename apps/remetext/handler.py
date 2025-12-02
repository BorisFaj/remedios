from apps.common.messaging import extract_request_context, logger
from apps.common.whatsapp import send_text_answer
from apps.common.chat.fool import ask
from apps.common.log.sender import validate_message, get_embeddings_context


def run(request: dict):
    message, phone_number = extract_request_context(request, expected_type="text")
    if not message:
        return

    try:
        _message_body = message["text"]["body"]
        emb = get_embeddings_context(message["from"], _message_body)
        respuesta_chatgpt = ask(emb)

        logger.info(f"[HUMAN]: {_message_body}")
        logger.info(f"[IA-Chat]: {respuesta_chatgpt}")

        send_text_answer(respuesta_chatgpt, message["from"], message["id"], phone_number)
        validate_message(message["from"], "IA", _message_body, "text")
        validate_message("IA", message["from"], respuesta_chatgpt, "text")
        logger.debug("Text answer sent ;)")
    except Exception as _:
        logger.error("Oye, se nos ha jodido esto")
        raise
