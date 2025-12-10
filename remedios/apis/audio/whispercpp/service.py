import argparse
import logging
import os
import sys

from flask import Flask, jsonify, request

from remedios.whatsapp.audio_cpp import run
from remedios.commons.stt.whisper.whisper_cpp import WHISPER_SERVER_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    # Intentar alcanzar whisper-server si está configurado
    if WHISPER_SERVER_URL:
        import httpx

        url = WHISPER_SERVER_URL.rstrip("/") + "/health"
        try:
            resp = httpx.get(url, timeout=5)
            return jsonify({"status": "ok", "whisper_server": resp.status_code}), 200
        except Exception:
            return jsonify({"status": "ok", "whisper_server": "unreachable"}), 503

    return jsonify({"status": "ok"}), 200


@app.route("/process", methods=["POST"])
def process():
    if request.content_type != "application/json":
        return jsonify({"status": "error", "message": "Unsupported Media Type"}), 415

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"status": "error", "message": "No JSON received"}), 400

    try:
        run(payload)
        return jsonify({"status": "success"}), 200
    except Exception as exc:  # pragma: no cover - external deps
        logger.exception("Error processing audio message")
        return jsonify({"status": "error", "message": str(exc)}), 500


def main() -> None:
    parser = argparse.ArgumentParser(description="Audio service")
    parser.add_argument(
        "--host",
        default=os.getenv("APP_HOST", "0.0.0.0"),
        help="Host a escuchar (default: APP_HOST env o 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("APP_PORT", "8001")),
        help="Puerto a escuchar (default: APP_PORT env o 8001)",
    )
    args = parser.parse_args()
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
