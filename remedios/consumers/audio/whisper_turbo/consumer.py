import threading
import logging
import os
import json
import time
from datetime import datetime, timezone

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict
from kafka import KafkaConsumer, KafkaProducer
from pydantic import ValidationError
import requests
from remedios.core.routing import route
from remedios.whatsapp.audio import run
from remedios.commons.schemas import IncomingMessage, AudioMessage, InvalidMessageError

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
    required = ["BOOTSTRAP_SERVER", "INTERNAL_API_URL", "INTERNAL_API_TOKEN"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(f"Faltan variables requeridas: {', '.join(missing)}")

    return {
        "bootstrap": os.environ["BOOTSTRAP_SERVER"],
        "audio_topic": os.environ.get("AUDIO_TOPIC", route["audio"]),
        "dlq_topic": os.environ.get("DLQ_TOPIC", route["dlq"]),
        "group_id": os.environ.get("GROUP_ID", "whatsapp-audio-consumer"),
        "internal_api_url": os.environ["INTERNAL_API_URL"].rstrip("/"),
        "internal_api_token": os.environ["INTERNAL_API_TOKEN"],
    }


def build_consumer(cfg: Dict[str, str]) -> KafkaConsumer:
    return KafkaConsumer(
        cfg["audio_topic"],
        bootstrap_servers=cfg["bootstrap"],
        group_id=cfg["group_id"],
        enable_auto_commit=False,
        auto_offset_reset="latest",
        value_deserializer=None,
        max_poll_interval_ms=600000,
        max_poll_records=1,
    )


def _headers(cfg):
    return {
        "Authorization": f"Bearer {cfg['internal_api_token']}",
        "Content-Type": "application/json",
    }


def _post(cfg, path: str, payload: dict):
    url = f"{cfg['internal_api_url']}{path}"
    resp = requests.post(url, headers=_headers(cfg), json=payload, timeout=10)
    if resp.status_code >= 400:
        raise RuntimeError(f"POST {url} failed status={resp.status_code} body={resp.text}")
    return resp


def process_message(raw: bytes, cfg: Dict[str, str]) -> bool:
    try:
        base = IncomingMessage.model_validate_json(raw)
    except ValidationError as e:
        raise InvalidMessageError(str(e))

    if base.message_type != "audio":
        raise InvalidMessageError(f"Unsupported message_type={base.message_type}")

    msg = AudioMessage.model_validate_json(raw)
    try:
        started = time.time()
        started_at = datetime.now(timezone.utc)
        try:
            _post(cfg, "/internal/job_status", {"job_id": msg.job_id, "status": "processing"})
        except Exception as exc:
            logger.warning("No se pudo marcar processing job_id=%s: %s", msg.job_id, exc)

        transcript, duration = run(msg)
        duration_ms = int((time.time() - started) * 1000)
        finished_at = datetime.now(timezone.utc)
        # Duración de audio si venía en el mensaje

        try:
            _post(cfg, "/internal/job_status", {"job_id": msg.job_id, "status": "completed"})
        except Exception as exc:
            logger.warning("No se pudo marcar completed job_id=%s: %s", msg.job_id, exc)
        try:
            _post(
                cfg,
                "/internal/job_result",
                {
                    "job_id": msg.job_id,
                    "result": {"transcript": transcript, "audio_id": msg.audio_id},
                    "output_ref": "whisper-turbo",
                    "duration_ms": duration_ms,
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                    "audio_duration_seconds": duration,
                },
            )
        except Exception as exc:
            logger.warning("No se pudo guardar job_result job_id=%s: %s", msg.job_id, exc)
        return True
    except Exception as exc:
        try:
            _post(cfg, "/internal/job_status", {"job_id": msg.job_id, "status": "failed", "error_message": str(exc)})
        except Exception:
            logger.exception("Error notificando estado failed a API interna job_id=%s", msg.job_id)
        logger.exception("Error procesando job_id=%s", msg.job_id)
        return False


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
        ok = False
        try:
            ok = process_message(record.value, cfg)
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
            ok = True  # Consideramos procesado al mandarlo a DLQ
        finally:
            if ok:
                consumer.commit()


if __name__ == "__main__":
    main()
