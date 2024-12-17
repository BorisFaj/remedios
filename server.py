import os
import requests

from flask import Flask, request, jsonify

app = Flask(__name__)

# Variables de entorno
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")
GRAPH_API_TOKEN = os.environ.get("GRAPH_API_TOKEN")
PORT = int(os.environ.get("PORT", 5000))  # Puerto por defecto 5000

@app.route("/webhook", methods=["POST"])
def webhook():
    # Loguea el mensaje entrante
    print("Incoming webhook message:", request.json)

    # Extrae el mensaje
    message = (
        request.json.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("messages", [{}])[0]
    )

    if message and message.get("type") == "text":
        # Extrae el numero de telefono del negocio
        business_phone_number_id = (
            request.json.get("entry", [{}])[0]
            .get("changes", [{}])[0]
            .get("value", {})
            .get("metadata", {})
            .get("phone_number_id")
        )

        # Envia una respuesta
        response_data = {
            "messaging_product": "whatsapp",
            "to": message.get("from"),
            "text": {"body": "Echo: " + message["text"]["body"]},
            "context": {"message_id": message["id"]},
        }
        headers = {"Authorization": "Bearer {}".format(GRAPH_API_TOKEN)}

        # Envia el mensaje de respuesta
        requests.post(
            "https://graph.facebook.com/v18.0/{}/messages".format(business_phone_number_id),
            headers=headers,
            json=response_data,
        )

        # Marca el mensaje como leido
        mark_read_data = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message["id"],
        }
        requests.post(
            "https://graph.facebook.com/v18.0/{}/messages".format(business_phone_number_id),
            headers=headers,
            json=mark_read_data,
        )

    return jsonify({}), 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    # Verificacion del webhook
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        print("Webhook verified successfully!")
        return challenge, 200
    else:
        return "Forbidden", 403

@app.route("/")
def home():
    return "<pre>Nothing to see here.\nCheckout README.md to start.</pre>", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
