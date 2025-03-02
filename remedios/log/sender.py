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
    user_id = save_user(sender)  # Registrar el usuario si no existe

    try:
        cursor.execute("""
            INSERT INTO messages (sender, receiver, message, message_type, user_id) 
            VALUES (%s, %s, %s, %s, %s)
        """, (sender, receiver, message, message_type, user_id))

        logger.info(f"Mensaje guardado en la base de datos ✅ Tipo: {message_type}")

    except Exception as e:
        logger.error(f"Error al insertar en la base de datos: {e}")


def save_user(phone_number):
    """Guarda el usuario si no existe y devuelve su ID."""
    cursor.execute("SELECT id FROM users WHERE phone = %s", (phone_number,))
    user = cursor.fetchone()

    if not user:
        cursor.execute("INSERT INTO users (phone) VALUES (%s) RETURNING id", (phone_number,))
        user_id = cursor.fetchone()[0]
        logger.info(f"Nuevo usuario registrado: {phone_number} (ID: {user_id})")
        return user_id
    return user[0]
