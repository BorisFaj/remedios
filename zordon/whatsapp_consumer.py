import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict

import requests
from kafka import KafkaConsumer


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp-consumer")


def start_health_server(port: int = 8080):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):  # noqa: N802
            return

    server = HTTPServer(("", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server listening on %s", port)


def load_config() -> Dict[str, str]:
    required = ["BOOTSTRAP_SERVER", "TEXT_ENDPOINT", "AUDIO_ENDPOINT"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(f"Faltan variables requeridas: {', '.join(missing)}")

    return {
        "bootstrap": os.environ["BOOTSTRAP_SERVER"],
        "text_endpoint": os.environ["TEXT_ENDPOINT"],
        "audio_endpoint": os.environ["AUDIO_ENDPOINT"],
        "text_topic": os.environ.get("TEXT_TOPIC", "whatsapp-text"),
        "audio_topic": os.environ.get("AUDIO_TOPIC", "whatsapp-audio"),
        "group_id": os.environ.get("GROUP_ID", "whatsapp-consumer"),
    }


def build_consumer(cfg: Dict[str, str]) -> KafkaConsumer:
    return KafkaConsumer(
        cfg["text_topic"],
        cfg["audio_topic"],
        bootstrap_servers=cfg["bootstrap"],
        group_id=cfg["group_id"],
        enable_auto_commit=True,
        auto_offset_reset="latest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )


def dispatch_message(record, cfg: Dict[str, str]):
    topic = record.topic
    payload = record.value

    if topic == cfg["text_topic"]:
        url = cfg["text_endpoint"]
    elif topic == cfg["audio_topic"]:
        url = cfg["audio_endpoint"]
    else:
        logger.warning("Topic desconocido %s, ignorando", topic)
        return

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Enviado a %s (%s) status=%s", url, topic, response.status_code)
    except Exception as exc:
        logger.error("Error enviando a %s (%s): %s", url, topic, exc)


def main():
    cfg = load_config()
    start_health_server()

    consumer = build_consumer(cfg)
    logger.info(
        "Consumiendo de topics=%s,%s hacia text=%s audio=%s",
        cfg["text_topic"],
        cfg["audio_topic"],
        cfg["text_endpoint"],
        cfg["audio_endpoint"],
    )

    for record in consumer:
        dispatch_message(record, cfg)


if __name__ == "__main__":
    main()
