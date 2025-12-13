import threading
import logging
import os
import json
import time
import socket
import subprocess
import sys
import contextlib
from pathlib import Path
from datetime import datetime

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict
from kafka import KafkaConsumer, KafkaProducer
from pydantic import ValidationError
from huggingface_hub import hf_hub_download

from remedios.core.routing import route
from remedios.whatsapp.audio import run
from remedios.commons.schemas import IncomingMessage, AudioMessage, InvalidMessageError
from remedios.log.sender import update_job_status, save_job_result

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whisper-cpp-consumer")


def start_health_server(port: int | None = None):
    if port is None:
        port = int(os.getenv("APP_PORT", "8001"))
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


def _wait_port(host: str, port: int, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(1)
    return False


def start_whisper_server() -> subprocess.Popen:
    raw_model = os.getenv("WHISPER_MODEL", "/app/ggml-large-v3-turbo-q5_0.bin")
    model = Path(raw_model if raw_model.startswith("/") else f"/app/{raw_model}")
    if not model.is_file():
        model.parent.mkdir(parents=True, exist_ok=True)
        repo = os.getenv("WHISPER_MODEL_REPO", "ggerganov/whisper.cpp")
        logger.info("Descargando modelo %s de %s a %s", model.name, repo, model)
        path = hf_hub_download(
            repo_id=repo,
            filename=model.name,
            local_dir=str(model.parent),
            local_dir_use_symlinks=False,
        )
        src = Path(path)
        if src != model:
            model.write_bytes(src.read_bytes())
    if not model.is_file():
        raise RuntimeError(f"Modelo no encontrado en {model}")

    port = int(os.getenv("WHISPER_SERVER_PORT", "9000"))
    lang = os.getenv("WHISPER_LANGUAGE", "es")
    threads = int(os.getenv("WHISPER_SERVER_THREADS", "2"))
    dump_dir = Path(os.getenv("WHISPER_DUMP", "/tmp/whisper-dump"))
    dump_dir.mkdir(parents=True, exist_ok=True)

    log_file = Path("/tmp/whisper-server.log")
    env = os.environ.copy()
    env["WHISPER_DUMP"] = str(dump_dir)

    server_cmd = [
        "/usr/local/bin/whisper-server",
        "--model",
        str(model),
        "--port",
        str(port),
        "--language",
        lang,
        "--host",
        "0.0.0.0",
        "--threads",
        str(threads),
    ]
    logger.info("Arrancando whisper-server: %s", " ".join(server_cmd))
    log_handle = log_file.open("w")
    server = subprocess.Popen(server_cmd, stdout=log_handle, stderr=subprocess.STDOUT, env=env)

    if not _wait_port("127.0.0.1", port, timeout=120):
        logger.error("whisper-server no levantó el puerto en %s", port)
        with contextlib.suppress(subprocess.TimeoutExpired):
            server.terminate()
            server.wait(timeout=5)
        raise RuntimeError("whisper-server no levantó")

    logger.info("whisper-server listo en puerto %s", port)
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
        "group_id": os.environ.get("GROUP_ID", "whatsapp-audio-consumer"),
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
            audio_duration = msg.duration_seconds

            update_job_status(msg.job_id, "completed", None)
            save_job_result(
                msg.job_id,
                {"transcript": transcript, "audio_id": msg.audio_id},
                output_ref="whisper-cpp",
                duration_ms=duration_ms,
                started_at=started_at,
                finished_at=finished_at,
                audio_duration_seconds=audio_duration,
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

    server_proc = start_whisper_server()

    cfg = load_config()
    start_health_server()

    consumer = build_consumer(cfg)
    logger.info("Consumiendo de topic=%s", cfg["audio_topic"])

    dlq_producer = KafkaProducer(
        bootstrap_servers=cfg["bootstrap"],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    try:
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
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()


if __name__ == "__main__":
    main()
