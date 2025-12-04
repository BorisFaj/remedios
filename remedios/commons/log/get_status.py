import os
import logging
import sys
from sqlalchemy import create_engine, text

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Leer y construir la URL de conexión
db_url = os.getenv("DB_URL")
if not db_url:
    logger.error("❌ La variable de entorno DB_URL no está definida.")
    sys.exit(1)

DATABASE_URL = f"postgresql://{db_url}"

# Crear engine y probar la conexión
try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        logger.info(f"✅ Conexión exitosa. Resultado de prueba: {result.scalar()}")
except Exception as e:
    logger.error(f"❌ Error al conectar con la base de datos: {e}")
