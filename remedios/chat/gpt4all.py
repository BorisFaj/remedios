import psycopg2
from gpt4all import GPT4All
import torch
import warnings
import logging
import sys
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
)

logger = logging.getLogger(__name__)
__gpt_model = None

def load_model():
    global __gpt_model

    if __gpt_model is None:
        logger.info("Cargando modelo por primera vez...")
        # Obtener la lista de modelos disponibles
        available_models = GPT4All.list_models()

        # Buscar el modelo "Llama 3 8B Instruct" en la lista
        model_name = None
        for model in available_models:
            if "Llama 3 8B Instruct" in model["name"]:  # Busca por nombre parcial
                model_name = model["filename"]
                break

        if not model_name:
            raise Exception("❌ No se encontró el modelo de LLaMA 3 8B en la lista de modelos disponibles.")

        logger.info(f"📥 Modelo encontrado: {model_name}")

        # Cargar el modelo
        if torch.cuda.is_available():
            print(f"✅ Ejecutando en GPU: {torch.cuda.get_device_name(0)}")
            __gpt_model = GPT4All(model_name, device="gpu")
        else:
            warnings.warn("⚠ No se detectó GPU. Ejecutando en CPU, puede ser más lento.")
            __gpt_model = GPT4All(model_name)

        logger.info("✅ Modelo cargado correctamente.")

def get_last_messages(phone_number, limit=5):
    """Recupera los últimos mensajes de la conversación desde PostgreSQL."""
    conn = psycopg2.connect(
        host="golismeos.c5aqi48uyz13.eu-north-1.rds.amazonaws.com",
        port="5432",
        dbname="golismeos",
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )
    cur = conn.cursor()

    # Obtener los últimos mensajes del usuario y del bot
    cur.execute("""
        SELECT sender, message FROM messages
        WHERE sender = %s OR receiver = %s
        ORDER BY timestamp DESC
        LIMIT %s;
    """, (phone_number, phone_number, limit))

    messages = cur.fetchall()
    conn.close()

    # Formatear como historial
    history = [f"{'Usuario' if sender == phone_number else 'IA'}: {text}" for sender, text in reversed(messages)]
    return "\n".join(history)


def ask(message: str, from_number: str) -> str:
    # Asegurar que el modelo esté cargado
    load_model()

    # Recuperar historial desde la base de datos
    history = get_last_messages(from_number)

    # Construir el prompt con contexto
    prompt = f"{history}\nUsuario: {message}\nAsistente:"

    # Generar respuesta
    response = __gpt_model.generate(
        prompt=prompt,
        max_tokens=250,
        temp=0.7,
        top_k=40,
        top_p=0.9,
        repeat_penalty=1.15,
    )

    return response
