import os

from flask import Flask, request, jsonify
from pyngrok import ngrok
from dotenv import find_dotenv, load_dotenv
from app import whats
from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})


# Env
env_file = find_dotenv(".env")
load_dotenv(env_file)

# Variables de entorno
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")
GRAPH_API_TOKEN = os.environ.get("GRAPH_API_TOKEN")
PORT = int(os.environ.get("PORT", 5000))  # Puerto por defecto 5000
GRAPH_URL = os.environ.get("GRAPH_URL")


__HEADERS = {"Authorization": "Bearer {}".format(GRAPH_API_TOKEN)}

# Flask
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    # Loguea el mensaje entrante
    app.logger.info("Incoming webhook message: {}".format(request.json))
    # Extrae el mensaje
    message = whats.get_message(request)
    phone_number = whats.get_phone_number(request)

    if message:
        app.logger.info("Recibido: %s" % message)
        if message.get("type") == "text":
            _message_body = message['text']['body']
            respuesta_chatgpt = whats.ask(_message_body)
            # respuesta_chatgpt = "recibido lokiii"

            app.logger.info(f"[HUMAN]: {_message_body}")
            app.logger.info(f"[IA]: {respuesta_chatgpt}")

            whats.send_text_answer(respuesta_chatgpt, message["from"], message["id"], phone_number)

            app.logger.info("Text answer send ;)")
        elif message.get("type") == "audio":
            audio = whats.extract_audio(message, phone_number)
            _pregunta = whats.transcribe(audio)
            answer = whats.ask(_pregunta)
            whats.send_text_answer(answer, message["from"], message["id"], phone_number)
            # whats.send_audio_answer(answer, phone_number)
        else:
            return jsonify({}), 404

    return jsonify({}), 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    # Verificacion del webhook
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        app.logger.info("Webhook verified successfully!")
        return challenge, 200
    else:
        return "Forbidden", 403

@app.route("/")
def home():
    return "¡Hola, mundo! Este es un servicio Flask expuesto con ngrok.", 200

if __name__ == "__main__":
    # Inicia ngrok y expone el servicio
    public_url = ngrok.connect(name="remedios")
    app.logger.info(f"El servicio está disponible en: {public_url}")

    app.run(port=5000)
