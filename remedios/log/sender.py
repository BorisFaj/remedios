import psycopg2
import os
import logging
import sys
from dotenv import load_dotenv, find_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
)

logger = logging.getLogger(__name__)

env_file = find_dotenv(".env")
load_dotenv(env_file)

DB_CONN = psycopg2.connect(
    host="golismeos.c5aqi48uyz13.eu-north-1.rds.amazonaws.com",
    port="5432",
    dbname="golismeos",
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS")
)

DB_CONN.autocommit = True
cursor = DB_CONN.cursor()


def save_message(sender, receiver, message, message_type="text"):
    save_user(sender)  # Registrar el usuario si no existe
    save_user(receiver)  # Registrar el receptor si no existe

    try:
        cursor.execute("""
            INSERT INTO messages (sender_phone, receiver_phone, message, message_type) 
            VALUES (%s, %s, %s, %s)
        """, (sender, receiver, message, message_type))

        logger.info(f"📩 Mensaje tipo {message_type} registrado en la base de datos ✅")

    except Exception as e:
        logger.error(f"❌ Error al insertar en la base de datos: {e}")

def save_user(phone_number):
    """Guarda el usuario si no existe. No devuelve ID porque ahora usamos phone."""
    try:
        cursor.execute("""
            INSERT INTO users (phone) VALUES (%s) 
            ON CONFLICT (phone) DO NOTHING
        """, (phone_number,))
        logger.info(f"Usuario registrado o ya existente: {phone_number}")
    except Exception as e:
        logger.error(f"❌ Error al guardar usuario {phone_number}: {e}")
