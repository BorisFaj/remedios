import os
import requests
import json
import torch

from chat.gpt4all import ask

from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from flask import Flask, request, jsonify
from pyngrok import ngrok
from dotenv import find_dotenv, load_dotenv

########## CONSTANTES ##########
### Torch y Whisper
device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

model_id = "openai/whisper-large-v3-turbo"

model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id, torch_dtype=torch_dtype, low_cpu_mem_usage=True, use_safetensors=True
)
model.to(device)

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

def transcribe(file_name: str):
    processor = AutoProcessor.from_pretrained(model_id)

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        torch_dtype=torch_dtype,
        device=device,
    )

    result = pipe(file_name, return_timestamps=True, generate_kwargs={"language": "spanish"})
    print("[DEBUG] Transcripcion: {}".format(result["text"]))
    return result["text"]


@app.route("/webhook", methods=["POST"])
def webhook():
    # Loguea el mensaje entrante
    print("Incoming webhook message:", request.json)

    # Extrae el mensaje
    message = get_message()
    # Extrae el numero de telefono del negocio
    business_phone_number_id = get_phone_number()

    if message:
        if message.get("type") == "text":
            _pregunta = message["text"]["body"]
            respuesta_chatgpt = ask(_pregunta)
        elif message.get("type") == "audio":
            _pregunta = extract_audio(message)
            respuesta_chatgpt = ask(_pregunta)
        else:
            respuesta_chatgpt = "qué me estás contando?"  # error


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
    # app.run(host="0.0.0.0", port=PORT)
    # Inicia ngrok y expone el servicio
    public_url = ngrok.connect(name="remedios")
    print(f"El servicio está disponible en: {public_url}")

    app.run(port=5000)
