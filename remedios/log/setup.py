import psycopg2
import os


DB_CONN = psycopg2.connect(
    host="golismeos.c5aqi48uyz13.eu-north-1.rds.amazonaws.com",
    port="5432",
    dbname="golismeos",
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS")
)

DB_CONN.autocommit = True
cursor = DB_CONN.cursor()

# Tabla de usuarios
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# Tabla de mensajes con claves foráneas a users.phone
cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    sender_phone VARCHAR(20) NOT NULL,
    receiver_phone VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    message_type VARCHAR(50) NOT NULL DEFAULT 'text',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sender FOREIGN KEY (sender_phone) REFERENCES users(phone) ON DELETE SET NULL,
    CONSTRAINT fk_receiver FOREIGN KEY (receiver_phone) REFERENCES users(phone) ON DELETE SET NULL
);
""")

# Tabla de logs
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
