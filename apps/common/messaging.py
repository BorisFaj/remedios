import logging
import sys
from typing import Optional, Tuple

from apps.common.whatsapp import get_message, get_phone_number

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def extract_request_context(request: dict, expected_type: str) -> Tuple[Optional[dict], Optional[int]]:
    """Return message and phone number when the message type matches.

    Logs the incoming payload source and filters out messages that do not match
    the expected type.
    """
    logger.info("Incoming webhook message")
    message = get_message(request)
    phone_number = get_phone_number(request)
    logger.info("from: %s", phone_number)

    if not message:
        logger.debug("No message received in webhook payload")
        return None, phone_number

    message_type = message.get("type")
    if message_type != expected_type:
        logger.debug("Ignoring message type %s (expected %s)", message_type, expected_type)
        return None, phone_number

    return message, phone_number
