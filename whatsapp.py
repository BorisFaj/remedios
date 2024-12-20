import os
import requests
import json

from chat.gpt4all import ask

from transcribe.whisper import *
from audio.tts.facebook import *
from transformers import VitsModel, AutoTokenizer
from flask import Flask, request, jsonify
from pyngrok import ngrok
from dotenv import find_dotenv, load_dotenv

########## CONSTANTES ##########
_PROCESSED_AUDIOS = []  # homemade_kafka =)

# tts
tts_model = VitsModel.from_pretrained("facebook/mms-tts-spa")
tts_tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-spa")

### Env
env_file = find_dotenv(".env")
load_dotenv(env_file)

### Flask
app = Flask(__name__)

### Variables de entorno
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")
GRAPH_API_TOKEN = os.environ.get("GRAPH_API_TOKEN")
PORT = int(os.environ.get("PORT", 5000))  # Puerto por defecto 5000

__URL = "https://graph.facebook.com/v21.0"
__HEADERS = {"Authorization": "Bearer {}".format(GRAPH_API_TOKEN)}


########## FUNCIONCITAS ##########

def get_message() -> json:
    return(
        request.json.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("messages", [{}])[0]
    )

def get_phone_number() -> json:
    return (
        request.json.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("metadata", {})
        .get("phone_number_id")
    )

def extract_audio(message: dict):
    audio_id = message["audio"]["id"]
    mime_type = message["audio"]["mime_type"]

    _PROCESSED_AUDIOS.append(audio_id)

    if "ogg" in mime_type:
        file_name = "test/media_file.ogg"
    else:
        file_name = "media_file"

    print(f"[DEBUG]: buscando audio {audio_id}...")
    response_url = requests.get("{}/{}".format(__URL, audio_id), headers=__HEADERS)

    # Verifica si la solicitud fue exitosa
    if response_url.status_code == 200:
        json_url = json.loads(response_url.content)
        audio_response = requests.get(json_url["url"], headers=__HEADERS)
        if audio_response.status_code == 200:
        # Guarda el contenido en un archivo
            with open(file_name, "wb") as file:
                file.write(audio_response.content)
            print(f"Archivo guardado como {file_name}")
        else:
            print(f"Error al descargar el archivo: {response_url.status_code}")
            print(response_url.text)
    else:
        print("URL no recibida :(")

    return transcribe(file_name)

def send_text_message(message, business_phone_number_id):
    respuesta_chatgpt = ask(message["text"]["body"])

    print(f"[DEBUG][GPT4ALL]: {respuesta_chatgpt}")
    # respuesta_chatgpt = "recibido lokiii"

    # Envia una respuesta
    response_data = {
        "messaging_product": "whatsapp",
        "to": message.get("from"),
        "text": {"body": respuesta_chatgpt},
        "context": {"message_id": message["id"]},
    }

    # Envia el mensaje de respuesta
    requests.post(
        "{}/{}/messages".format(__URL, business_phone_number_id),
        headers=__HEADERS,
        json=response_data,
    )

    # Marca el mensaje como leido
    mark_read_data = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message["id"],
    }
    requests.post(
        "{}/{}/messages".format(__URL, business_phone_number_id),
        headers=__HEADERS,
        json=mark_read_data,
    )

def send_audio_message(message, business_phone_number_id):
    # Transcribir audio
    _pregunta = extract_audio(message)
    # Preguntar LLM
    respuesta_chatgpt = ask(_pregunta)

    # TTS
    _audio = generate_audio(respuesta_chatgpt)
    # Subir el audio a meta
    payload = {
        "file": _audio,
        "type": "MP3",
        "messaging_product": "whatsapp"
    }
    media_response = requests.post(
        "{}/{}/media".format(__URL, business_phone_number_id),
        headers=__HEADERS,
        data=_audio,
        params=payload,
    )

    if media_response.status_code == 200:
        print("[DEBUG]: Mensaje subido :)")
        # Enviar post para actualizar
        _body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": "<WHATSAPP_USER_PHONE_NUMBER>",
            "type": "audio",
            "audio": {
                "id": "{}".format(media_response.content)
            }
        }

        requests.post(
            "{}/{}/messages".format(__URL, business_phone_number_id),
            headers=__HEADERS,
            json=_body,
        )

        print("[DEBUG]: Mensaje enviado")
    else:
        # print(f"[ERROR]: {media_response.status_code} - {media_response.content}")
        print(f"[ERROR]: {media_response.status_code}")


@app.route("/webhook", methods=["POST"])
def webhook():
    # Loguea el mensaje entrante
    print("Incoming webhook message:", request.json)

    # Extrae el mensaje
    message = get_message()
    # Extrae el numero de telefono del negocio
    business_phone_number_id = get_phone_number()

    if message:
        print("[DEBUG] Ha entrao otro")
        if message.get("type") == "text":

            send_text_message(message, business_phone_number_id)

        elif message.get("type") == "audio":
            if message["audio"]["id"] not in _PROCESSED_AUDIOS:
                send_audio_message(message, business_phone_number_id)
            else:
                print(f"[DEBUG]: {business_phone_number_id} esta impaciente, que se espere")
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
        print("Webhook verified successfully!")
        return challenge, 200
    else:
        return "Forbidden", 403

@app.route("/")
def home():
    return "¡Hola, mundo! Este es un servicio Flask expuesto con ngrok.", 200

if __name__ == "__main__":
    # Inicia ngrok y expone el servicio
    public_url = ngrok.connect(name="remedios")
    print(f"El servicio está disponible en: {public_url}")

    app.run(port=5000)
