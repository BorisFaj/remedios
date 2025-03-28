import json
import logging
import sys
import os
import time
import signal
import importlib
from confluent_kafka import Consumer, KafkaError

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
            conf = {
                'bootstrap.servers': os.environ.get("BOOTSTRAP_SERVER"),
                'security.protocol': 'SASL_SSL',
                'sasl.mechanisms': 'SCRAM-SHA-256',
                'sasl.username': os.environ.get("REDPANDA_USER"),
                'sasl.password': os.environ.get("REDPANDA_PASS"),
                'group.id': os.environ.get("KAFKA_GROUP_ID", "default"),
                'auto.offset.reset': 'latest',
                'enable.auto.commit': False,
                'session.timeout.ms': 30000
            }

            consumer = Consumer(conf)
            consumer.subscribe([KAFKA_TOPIC])
            logger.info(f"✅ Consumidor conectado al topic '{KAFKA_TOPIC}'")

            module = importlib.import_module(TOPIC_MODULES[KAFKA_TOPIC])

            while running:
                msg = consumer.poll(1.0)  # 1 segundo

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.info("🔚 Fin de partición")
                    else:
                        logger.error(f"❌ Error en el mensaje: {msg.error()}")
                    continue

                try:
                    message_data = json.loads(msg.value().decode("utf-8"))
                    module.run(message_data)
                    consumer.commit(msg)
                    logger.info(f"✔ Offset confirmado en {msg.topic()} [{msg.partition()}] offset {msg.offset()}")
                except Exception as e:
                    logger.error(f"❌ Error al procesar mensaje: {e}")

        except Exception as e:
            logger.error(f"❌ Error creando el consumidor: {e}")

        finally:
            try:
                consumer.close()
            except:
                pass
            time.sleep(5)

if __name__ == "__main__":
    start_consumer()
