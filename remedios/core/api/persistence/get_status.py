import logging
import sys

from sqlalchemy import text

from remedios.core.api.persistence.db import _create_engine_from_env, get_engine

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    engine = get_engine()
    if not engine:
        engine, _ = _create_engine_from_env()

    if not engine:
        logger.error("❌ Faltan variables para conectar a Oracle (ORACLE_*).")
        sys.exit(1)

    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1 FROM dual"))
            logger.info("✅ Conexión exitosa. Resultado de prueba: %s", result.scalar())
    except Exception as exc:
        logger.error("❌ Error al conectar con la base de datos: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
