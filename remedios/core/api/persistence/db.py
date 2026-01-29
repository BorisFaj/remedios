import logging
import os
import sys
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

SessionLocal = None
engine = None


def _prepare_wallet_dir(wallet_path: str) -> Path:
    """Acepta una ruta de carpeta o un zip con el wallet y devuelve la carpeta lista."""
    path = Path(wallet_path)
    if not path.exists():
        raise FileNotFoundError(f"Wallet no encontrado en {wallet_path}")
    if path.is_dir():
        return path
    if path.suffix.lower() == ".zip":
        target = Path(tempfile.mkdtemp(prefix="wallet_"))
        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(target)
        return target
    raise ValueError(f"Ruta de wallet no soportada: {wallet_path}")


def _create_engine_from_env():
    """Construye el engine de SQLAlchemy para Oracle usando el wallet."""
    required = ["ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN", "ORACLE_WALLET_PATH"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        logger.warning(
            "Logging a DB deshabilitado; faltan variables: %s", ", ".join(missing)
        )
        return None, None

    try:
        wallet_dir = _prepare_wallet_dir(os.environ["ORACLE_WALLET_PATH"])
    except Exception as exc:
        logger.error("No se pudo preparar el wallet: %s", exc)
        return None, None
    connect_args = {
        "config_dir": str(wallet_dir),
        "wallet_location": str(wallet_dir),
    }
    wallet_password = os.getenv("ORACLE_WALLET_PASSWORD")
    if wallet_password:
        connect_args["wallet_password"] = wallet_password

    dsn = os.environ["ORACLE_DSN"]  # alias del servicio en tnsnames.ora

    engine = create_engine(
        "oracle+oracledb://",
        connect_args={
            "user": os.environ["ORACLE_USER"],
            "password": os.environ["ORACLE_PASSWORD"],
            "dsn": dsn,
            **connect_args,
        },
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, session_factory


engine, SessionLocal = _create_engine_from_env()
if not engine:
    logger.warning("No se inicializó engine de Oracle; se omite persistencia en DB.")


def _get_session():
    if not SessionLocal:
        return None
    return SessionLocal()


def get_engine():
    return engine
