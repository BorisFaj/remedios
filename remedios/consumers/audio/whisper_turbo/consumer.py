import threading
import logging
import os
import json
import time
from datetime import datetime

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict
from kafka import KafkaConsumer, KafkaProducer
from pydantic import ValidationError
from remedios.core.routing import route
from remedios.whatsapp.audio import run
from remedios.commons.schemas import IncomingMessage, AudioMessage, InvalidMessageError
from remedios.log.sender import update_job_status, save_job_result

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whisper-turbo-consumer")

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

        def log_message(self, format, *args):
            return

    server = HTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server en :%s/health", port)
    return server


def load_config() -> Dict[str, str]:
    required = ["BOOTSTRAP_SERVER"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(f"Faltan variables requeridas: {', '.join(missing)}")

    return {
        "bootstrap": os.environ["BOOTSTRAP_SERVER"],
        "audio_topic": os.environ.get("AUDIO_TOPIC", route["audio"]),
        "dlq_topic": os.environ.get("DLQ_TOPIC", route["dlq"]),
        "group_id": os.environ.get("GROUP_ID", "whisper-turbo-consumer"),
    }


def build_consumer(cfg: Dict[str, str]) -> KafkaConsumer:
    return KafkaConsumer(
        cfg["audio_topic"],
        bootstrap_servers=cfg["bootstrap"],
        group_id=cfg["group_id"],
        enable_auto_commit=False,
        auto_offset_reset="latest",
        value_deserializer=None
    )


def process_message(raw: bytes):
    try:
        base = IncomingMessage.model_validate_json(raw)
    except ValidationError as e:
        raise InvalidMessageError(str(e))

    if base.message_type == "audio":
        msg = AudioMessage.model_validate_json(raw)
        try:
            if msg.job_id is None:
                raise InvalidMessageError("job_id requerido en el mensaje")
            started = time.time()
            started_at = datetime.utcnow()
            update_job_status(msg.job_id, "processing", None)

            transcript = run(msg)
            duration_ms = int((time.time() - started) * 1000)
            finished_at = datetime.utcnow()

            update_job_status(msg.job_id, "completed", None)
            save_job_result(
                msg.job_id,
                {"transcript": transcript, "audio_id": msg.audio_id},
                output_ref="whisper-turbo",
                duration_ms=duration_ms,
                started_at=started_at,
                finished_at=finished_at,
            )

        except Exception as exc:
            update_job_status(msg.job_id, "failed", str(exc))
            raise
    else:
        raise InvalidMessageError(f"Unsupported message_type={base.message_type}")


def main():
    if os.environ.get("HEALTHCHECK_ONLY") == "1":
        start_health_server()
        logger.info("Modo healthcheck habilitado, no se inicia el consumer de Kafka")
        while True:
            time.sleep(60)

    cfg = load_config()
    start_health_server()

    consumer = build_consumer(cfg)
    logger.info("Consumiendo de topic=%s", cfg["audio_topic"])

    dlq_producer = KafkaProducer(
        bootstrap_servers=cfg["bootstrap"],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    for record in consumer:
        try:
            process_message(record.value)
            consumer.commit()
        except InvalidMessageError as e:
            logger.exception("Mensaje inválido topic=%s offset=%s", record.topic, record.offset)

            payload = {
                "error": str(e),
                "raw": record.value.decode("utf-8", errors="replace"),
                "topic": record.topic,
                "partition": record.partition,
                "offset": record.offset,
            }

            dlq_producer.send(cfg["dlq_topic"], payload).get(timeout=10)
            dlq_producer.flush()
            consumer.commit()
        except Exception as _:
            logger.exception("Fallo procesando topic=%s offset=%s", record.topic, record.offset)


if __name__ == "__main__":
    main()
