import psycopg2
import os
from dotenv import find_dotenv, load_dotenv

env_file = find_dotenv(".env")
load_dotenv(env_file)

DB_HOST = "golismeos.c5aqi48uyz13.eu-north-1.rds.amazonaws.com"
DB_PORT = "5432"
DB_NAME = "postgres"
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

print(f"hola {DB_USER}")
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    print("Conexión exitosa")
    conn.close()
except Exception as e:
    print(f"Error al conectar: {e}")
