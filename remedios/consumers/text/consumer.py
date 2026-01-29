import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict
from kafka import KafkaConsumer, KafkaProducer
from pydantic import ValidationError
from remedios.core.routing import kafka_route, api_route
from remedios.consumers.text.fool import ask
from remedios.commons.schemas import IncomingMessage, TextMessage, InvalidMessageError
from remedios.commons.utils import post_internal_api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("text-consumer")

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
    required = ["BOOTSTRAP_SERVER", "INTERNAL_API_URL", "INTERNAL_API_TOKEN"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(f"Faltan variables requeridas: {', '.join(missing)}")

    return {
        "bootstrap": os.environ["BOOTSTRAP_SERVER"],
        "text_topic": os.environ.get("TEXT_TOPIC", kafka_route["text"]),
        "dlq_topic": os.environ.get("DLQ_TOPIC", kafka_route["dlq"]),
        "group_id": os.environ.get("GROUP_ID", "whatsapp-text-consumer"),
        "internal_api_url": os.environ["INTERNAL_API_URL"].rstrip("/"),
        "internal_api_token": os.environ["INTERNAL_API_TOKEN"],
    }


def build_consumer(cfg: Dict[str, str]) -> KafkaConsumer:
    return KafkaConsumer(
        cfg["text_topic"],
        bootstrap_servers=cfg["bootstrap"],
        group_id=cfg["group_id"],
        enable_auto_commit=False,
        auto_offset_reset="latest",
        value_deserializer=None
    )
def _send_text_answer(msg: TextMessage, text: str, cfg: Dict[str, str]):
    post_internal_api(
        cfg["internal_api_url"],
        cfg["internal_api_token"],
        "/internal/send_text_answer",
        {
            "text": text,
            "phone_number": msg.phone,
            "message_id": msg.message_id,
            "number_id": msg.number_id,
        },
    )


def process_message(raw: bytes, cfg: Dict[str, str]) -> bool:
    try:
        base = IncomingMessage.model_validate_json(raw)
    except ValidationError as e:
        raise InvalidMessageError(str(e))

    if base.message_type == "text":
        msg = TextMessage.model_validate_json(raw)

        try:
            if msg.job_id is None:
                raise InvalidMessageError("job_id requerido en el mensaje")
            started = time.time()
            started_at = datetime.now(timezone.utc)
            post_internal_api(
                cfg["internal_api_url"],
                cfg["internal_api_token"],
                api_route["job_status"],
                {"job_id": msg.job_id, "status": "processing"},
            )

            result = ask(msg.text)
            _send_text_answer(msg, result, cfg)

            duration_ms = int((time.time() - started) * 1000)
            finished_at = datetime.now(timezone.utc)

            post_internal_api(
                cfg["internal_api_url"],
                cfg["internal_api_token"],
                api_route["job_status"],
                {"job_id": msg.job_id, "status": "completed"},
            )

            post_internal_api(
                cfg["internal_api_url"],
                cfg["internal_api_token"],
                api_route["job_result"],
                {
                    "job_id": msg.job_id,
                    "result": {"answer": result, "input": msg.text},
                    "output_ref": f"{ask.__module__}.{ask.__name__}",
                    "duration_ms": duration_ms,
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                },
            )
        except Exception as exc:
            post_internal_api(
                cfg["internal_api_url"],
                cfg["internal_api_token"],
                api_route["job_status"],
                {"job_id": msg.job_id, "status": "failed", "error_message": str(exc)},
            )
            raise exc
    else:
        raise InvalidMessageError(f"Unsupported message_type={base.message_type}")
    return True


def main():
    if os.environ.get("HEALTHCHECK_ONLY") == "1":
        start_health_server()
        logger.info("Modo healthcheck habilitado, no se inicia el consumer de Kafka")
        while True:
            time.sleep(60)

    cfg = load_config()
    start_health_server()

    consumer = build_consumer(cfg)
    logger.info("Consumiendo de topic=%s", cfg["text_topic"])

    dlq_producer = KafkaProducer(
        bootstrap_servers=cfg["bootstrap"],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    for record in consumer:
        try:
            process_message(record.value, cfg)
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
