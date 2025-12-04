import logging
import sys

from flask import Flask, jsonify, request

from remedios.whatsapp.audio import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
