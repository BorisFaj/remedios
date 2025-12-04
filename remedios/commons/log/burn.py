import psycopg2
import os

# Conectar a la base de datos
DB_CONN = psycopg2.connect(
    host="golismeos.c5aqi48uyz13.eu-north-1.rds.amazonaws.com",
    port="5432",
    dbname="golismeos",
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS")
)

DB_CONN.autocommit = True
cursor = DB_CONN.cursor()

# Eliminar las tablas si existen (en orden para evitar errores de FK)
cursor.execute("DROP TABLE IF EXISTS messages CASCADE;")
cursor.execute("DROP TABLE IF EXISTS users CASCADE;")
cursor.execute("DROP TABLE IF EXISTS logs CASCADE;")

print("Tablas eliminadas correctamente ✅")

# Cerrar conexión
cursor.close()
DB_CONN.close()