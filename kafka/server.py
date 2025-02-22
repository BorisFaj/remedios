from flask import Flask, request, jsonify
from confluent_kafka import Producer
import json
import socket
import os
from dotenv import load_dotenv

load_dotenv(".secrets")

# Configuración de Kafka
KAFKA_BROKER = os.environ.get("PUBLIC_IP") + ":9092"
TOPIC = "whatsapp-events"

# Configurar el productor de Kafka
producer_conf = {
    "bootstrap.servers": KAFKA_BROKER,
    "client.id": socket.gethostname(),
}
producer = Producer(producer_conf)

# Inicializar Flask
app = Flask(__name__)

@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode and token and challenge:  # Asegurar que todos los valores existen
            if mode == "subscribe" and token == os.environ.get("WEBHOOK_VERIFY_TOKEN"):
                app.logger.info("Webhook verified successfully!")
                return challenge, 200
            else:
                return jsonify({"status": "error", "message": "Invalid verification token"}), 403
        else:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400

    elif request.method == "POST":
        try:
            if request.content_type != "application/json":
                return jsonify({"status": "error", "message": "Unsupported Media Type"}), 415

            data = request.get_json(silent=True)  # Evitar que Flask lance una excepción si no es JSON

            if not data:
                return jsonify({"status": "error", "message": "No JSON received"}), 400

            print("Mensaje recibido:", json.dumps(data, indent=2))

            # Enviar el mensaje a Kafka
            producer.produce(TOPIC, json.dumps(data))
            producer.flush()

            return jsonify({"status": "success"}), 200

        except Exception as e:
            print("Error:", str(e))
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "Invalid request"}), 400  # En caso de que no entre en GET o POST


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3000, debug=True)