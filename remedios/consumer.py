import json
from kafka import KafkaConsumer
import reme
import logging
import sys
import os
import time
import signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
)

logger = logging.getLogger(__name__)

running = True  # Variable de control para salir del bucle


def signal_handler(sig, frame):
    global running
    logger.info("🛑 Señal recibida, cerrando consumidor de Kafka...")
    running = False


signal.signal(signal.SIGINT, signal_handler)  # Capturar CTRL+C
signal.signal(signal.SIGTERM, signal_handler)  # Capturar SIGTERM (Docker o systemd)

def start_consumer():
    global running
    while running:
        try:
            consumer = KafkaConsumer(
                bootstrap_servers=os.environ.get("BOOTSTRAP_SERVER"),
                security_protocol="SASL_SSL",
                sasl_mechanism="SCRAM-SHA-256",
                sasl_plain_username=os.environ.get("REDPANDA_USER"),
                sasl_plain_password=os.environ.get("REDPANDA_PASS"),
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                group_id="patio"
            )
            consumer.subscribe([os.environ.get("KAFKA_TOPIC")])

            for message in consumer:
                if not running:
                    break  # Salir del bucle si se recibió SIGINT o SIGTERM

                topic_info = f"topic: {message.topic} ({message.partition}|{message.offset})"
                message_info = f"key: {message.key}, {message.value}"
                print(f"{topic_info}, {message_info}")

                message_data = json.loads(message.value)
                logger.info(f"📩 Mensaje recibido: {json.dumps(message_data, indent=2)}")

                reme.run(message_data)
                consumer.commit()
                logger.info(f"✔ Mensaje confirmado en offset {message.offset}")

            consumer.close()  # Cerrar consumidor al salir del bucle
        except Exception as e:
            logger.error(f"❌ Error en el consumidor: {str(e)}")
            time.sleep(5)  # Espera antes de reintentar para evitar sobrecargar Kafka

if __name__ == "__main__":
    start_consumer()
