import base64
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict
from kafka import KafkaConsumer, KafkaProducer
from pydantic import ValidationError
from remedios.core.routing import kafka_route, api_route
from remedios.commons.schemas import IncomingMessage, AudioMessage, InvalidMessageError
from remedios.commons.utils import post_internal_api
import requests
from .stt import transcribe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whisper-turbo-consumer")

_UPLOAD_WORKERS = int(os.environ.get("UPLOAD_AUDIO_WORKERS", "2"))
_UPLOAD_POOL = ThreadPoolExecutor(max_workers=_UPLOAD_WORKERS) if _UPLOAD_WORKERS > 0 else None

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
        "audio_topic": os.environ.get("AUDIO_TOPIC", kafka_route["audio"]),
        "dlq_topic": os.environ.get("DLQ_TOPIC", kafka_route["dlq"]),
        "group_id": os.environ.get("GROUP_ID", "whatsapp-audio-consumer"),
        "internal_api_url": os.environ["INTERNAL_API_URL"].rstrip("/"),
        "internal_api_token": os.environ["INTERNAL_API_TOKEN"],
        "upload_audio": os.environ.get("UPLOAD_AUDIO_ENABLED", "0") == "1",
        "upload_timeout": int(os.environ.get("UPLOAD_AUDIO_TIMEOUT", "30")),
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

def _fetch_audio_bytes(msg: AudioMessage, cfg: Dict[str, str]) -> bytes:
    """Descarga el audio vía API interna y lo devuelve en bytes."""
    resp = post_internal_api(
        cfg["internal_api_url"],
        cfg["internal_api_token"],
        "/internal/extract_audio",
        {"audio_id": msg.audio_id},
    )
    try:
        data = resp.json() or {}
    except ValueError as exc:
        raise RuntimeError("Respuesta no JSON de extract_audio") from exc

    if data.get("status") and data.get("status") != "ok":
        raise RuntimeError(data.get("message") or "extract_audio devolvió error")

    audio_b64 = data.get("audio_b64")
    if not audio_b64:
        raise RuntimeError("Audio vacío devuelto por extract_audio")

    try:
        return base64.b64decode(audio_b64)
    except Exception as exc:
        raise RuntimeError("Audio inválido devuelto por extract_audio") from exc


def _send_text_answer(msg: AudioMessage, text: str, cfg: Dict[str, str]):
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


def _request_upload_url(msg: AudioMessage, cfg: Dict[str, str]) -> dict:
    resp = post_internal_api(
        cfg["internal_api_url"],
        cfg["internal_api_token"],
        api_route["audio_upload_url"],
        {
            "job_id": msg.job_id,
            "audio_id": msg.audio_id,
            "mime_type": msg.mime_type,
        },
    )
    data = resp.json() or {}
    if data.get("status") != "ok":
        raise RuntimeError(data.get("error") or "No se pudo obtener upload_url")
    return data


def _upload_audio_async(audio_bytes: bytes, msg: AudioMessage, cfg: Dict[str, str]):
    if not cfg.get("upload_audio"):
        return
    if not _UPLOAD_POOL:
        logger.warning("UPLOAD_AUDIO_WORKERS=0, upload deshabilitado")
        return

    try:
        info = _request_upload_url(msg, cfg)
    except Exception:
        logger.exception("No se pudo obtener upload_url job_id=%s", msg.job_id)
        return

    upload_url = info["upload_url"]
    bucket_name = info.get("bucket_name")
    namespace = info.get("namespace")
    object_key = info.get("object_key")

    def _do_upload():
        try:
            resp = requests.put(
                upload_url,
                data=audio_bytes,
                headers={"Content-Type": msg.mime_type or "application/octet-stream"},
                timeout=cfg["upload_timeout"],
            )
            if resp.status_code >= 300:
                logger.error("Upload OCI failed status=%s body=%s", resp.status_code, resp.text)
                return
            etag = resp.headers.get("etag")
            if etag:
                etag = etag.strip('"')
            post_internal_api(
                cfg["internal_api_url"],
                cfg["internal_api_token"],
                api_route["job_audio"],
                {
                    "job_id": msg.job_id,
                    "provider": "oracle",
                    "bucket_name": bucket_name,
                    "namespace": namespace,
                    "object_key": object_key,
                    "size_bytes": len(audio_bytes),
                    "content_type": msg.mime_type,
                    "etag": etag,
                    "audio_id": msg.audio_id,
                },
            )
        except Exception:
            logger.exception("Error subiendo audio job_id=%s", msg.job_id)

    _UPLOAD_POOL.submit(_do_upload)

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
        post_internal_api(cfg['internal_api_url'], cfg['internal_api_token'], api_route["job_status"], {"job_id": msg.job_id, "status": "processing"})

        audio_bytes = _fetch_audio_bytes(msg, cfg)
        _upload_audio_async(audio_bytes, msg, cfg)
        transcript, duration = transcribe(audio_bytes)
        transcript = transcript.strip() if transcript else ""
        final_response = transcript or "No pude entender tu audio."
        _send_text_answer(msg, final_response, cfg)

        duration_ms = int((time.time() - started) * 1000)
        finished_at = datetime.now(timezone.utc)

        post_internal_api(cfg['internal_api_url'], cfg['internal_api_token'], api_route["job_status"],
                          {"job_id": msg.job_id, "status": "completed"})

        post_internal_api(
            cfg['internal_api_url'],
            cfg['internal_api_token'],
            api_route["job_result"],
            {
                "job_id": msg.job_id,
                "result": {
                    "transcript": transcript,
                    "response_text": final_response,
                    "audio_id": msg.audio_id,
                },
                "output_ref": "whisper-turbo",
                "duration_ms": duration_ms,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "audio_duration_seconds": duration,
            },
        )
        return True
    except Exception as exc:
        try:
            post_internal_api(cfg['internal_api_url'], cfg['internal_api_token'], api_route["job_status"],
                              {"job_id": msg.job_id, "status": "failed", "error_message": str(exc)})
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
