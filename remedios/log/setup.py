import psycopg2
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(".env"))

DB_CONN = psycopg2.connect(
    host="golismeos.c5aqi48uyz13.eu-north-1.rds.amazonaws.com",
    port="5432",
    dbname="golismeos",
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS")
)

DB_CONN.autocommit = True
cursor = DB_CONN.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    sender VARCHAR(255) NOT NULL,
    receiver VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    message_type VARCHAR(50) NOT NULL DEFAULT 'text',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INT,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

print("Base de datos creada correctamente ✅")

cursor.close()
DB_CONN.close()
