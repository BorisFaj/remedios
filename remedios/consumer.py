import json
from confluent_kafka import Consumer
import reme
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Enviar logs a stdout para que Docker los capture
    ],
)

logger = logging.getLogger(__name__)

conf = {
    'bootstrap.servers': 'remediosapi.duckdns.org:9093',
    'group.id': 'whatsapp-group',
    'auto.offset.reset': 'earliest',
    #'debug': 'consumer,cgrp,broker,topic'
}

TOPIC = "whatsapp-events"
consumer = Consumer(conf)
consumer.subscribe([TOPIC])
logger.info(f"Suscrito al topic {TOPIC}")

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        logger.error(f"❌ Error: {msg.error()}")
        continue

    # Decodificar el mensaje de Kafka
    message_str = msg.value().decode('utf-8').strip()  # Evitar espacios en blanco

    # Si el mensaje no es un JSON válido, ignorarlo
    if not message_str.startswith("{"):
        logger.warning(f"⚠️ Mensaje ignorado (no es JSON): {message_str}")
        continue

    # Convertir el mensaje en JSON
    message_data = json.loads(message_str)
    logger.info(f"📩 Mensaje recibido: {json.dumps(message_data, indent=2)}")

    reme.run(message_data)
