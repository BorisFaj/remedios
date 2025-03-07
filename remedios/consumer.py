import json
from kafka import KafkaConsumer
import reme
import logging
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Enviar logs a stdout para que Docker los capture
    ],
)

logger = logging.getLogger(__name__)

consumer = KafkaConsumer(
  bootstrap_servers=os.environ.get("BOOTSTRAP_SERVER"),
  security_protocol="SASL_SSL",
  sasl_mechanism="SCRAM-SHA-256",
  sasl_plain_username=os.environ.get("REDPANDA_USER"),
  sasl_plain_password=os.environ.get("REDPANDA_PASS"),
  auto_offset_reset="earliest",
  enable_auto_commit=False,
  consumer_timeout_ms=10000
)
consumer.subscribe(os.environ.get("KAFKA_TOPIC"))

for message in consumer:
  topic_info = f"topic: {message.topic} ({message.partition}|{message.offset})"
  message_info = f"key: {message.key}, {message.value}"
  print(f"{topic_info}, {message_info}")

  message_data = json.loads(message.value)
  logger.info(f"📩 Mensaje recibido: {json.dumps(message_data, indent=2)}")

  reme.run(message_data)
