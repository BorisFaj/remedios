import json
import logging
import sys
import os
import time
import signal
import importlib
from kafka import KafkaConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)
running = True
TOPIC_MODULES = {
    "whatsapp-text": "remetext",
    "whatsapp-audio": "remeaudio"
}

KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC")
if not KAFKA_TOPIC or KAFKA_TOPIC not in TOPIC_MODULES:
    logger.error(f"❌ ERROR: El topic '{KAFKA_TOPIC}' no está definido en TOPIC_MODULES o es inválido.")
    sys.exit(1)

logger.info(f"📡 Iniciando consumidor para el topic: {KAFKA_TOPIC}")

# Capturar señales SIGINT y SIGTERM para un apagado limpio
def signal_handler(sig, frame):
    global running
    logger.info("🛑 Señal recibida, cerrando consumidor de Kafka...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

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
                group_id=os.environ.get("KAFKA_GROUP_ID", "default")
            )

            consumer.subscribe([KAFKA_TOPIC])
            logger.info(f"✅ Consumidor iniciado en topic '{KAFKA_TOPIC}'")

            module = importlib.import_module(TOPIC_MODULES[KAFKA_TOPIC])

            for message in consumer:
                if not running:
                    break  # Salir si se recibió SIGINT o SIGTERM

                message_data = json.loads(message.value)
                logger.info(f"📩 Mensaje recibido en topic '{KAFKA_TOPIC}': {json.dumps(message_data, indent=2)}")

                try:
                    module.run(message_data)

                    consumer.commit()
                    logger.info(f"✔ Mensaje confirmado en offset {message.offset}")

                except Exception as e:
                    logger.error(f"❌ Error al procesar el mensaje en '{KAFKA_TOPIC}': {str(e)}")

            consumer.close()

        except Exception as e:
            logger.error(f"❌ Error en el consumidor: {str(e)}")
            time.sleep(5)  # Esperar antes de reintentar para evitar sobrecargar Kafka

if __name__ == "__main__":
    start_consumer()
