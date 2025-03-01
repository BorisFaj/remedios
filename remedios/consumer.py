import json
import logging
from logging.config import dictConfig
from confluent_kafka import Consumer

from remedios import remedios

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

logger = logging.getLogger()

conf = {
    'bootstrap.servers': 'remediosapi.duckdns.org:9093',
    'group.id': 'whatsapp-group',
    'auto.offset.reset': 'earliest',
    #'debug': 'consumer,cgrp,broker,topic'
}

consumer = Consumer(conf)
consumer.subscribe(['whatsapp-events'])

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print(f"❌ Error: {msg.error()}")
        continue

    # Decodificar el mensaje de Kafka
    message_str = msg.value().decode('utf-8').strip()  # Evitar espacios en blanco

    # Si el mensaje no es un JSON válido, ignorarlo
    if not message_str.startswith("{"):
        print(f"⚠️ Mensaje ignorado (no es JSON): {message_str}")
        continue

    # Convertir el mensaje en JSON
    message_data = json.loads(message_str)
    print(f"📩 Mensaje recibido: {json.dumps(message_data, indent=2)}")

    remedios.run(message_data)