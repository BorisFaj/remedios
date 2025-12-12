import logging
import os
import sys
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy import (
    Column,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    TIMESTAMP,
    create_engine,
    text,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from .base import LogBase

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

Base = declarative_base()
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
        logger.warning("Logging a DB deshabilitado; faltan variables: %s", ", ".join(missing))
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


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, Identity(), primary_key=True)
    phone = Column(String(20), unique=True, nullable=False)
    name = Column(String(255))
    created_at = Column(TIMESTAMP(timezone=False), server_default=text("SYSTIMESTAMP"))

    sent_messages = relationship(
        "Message",
        back_populates="sender",
        foreign_keys="Message.sender_phone",
    )
    received_messages = relationship(
        "Message",
        back_populates="receiver",
        foreign_keys="Message.receiver_phone",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, Identity(), primary_key=True)
    sender_phone = Column(String(20), ForeignKey("users.phone"))
    receiver_phone = Column(String(20), ForeignKey("users.phone"))
    message = Column(Text, nullable=False)
    message_type = Column(String(50), nullable=False, default="text")
    created_at = Column(TIMESTAMP(timezone=False), server_default=text("SYSTIMESTAMP"))

    sender = relationship("User", foreign_keys=[sender_phone], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_phone], back_populates="received_messages")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, Identity(), primary_key=True)
    job_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    source_message_id = Column(ForeignKey("messages.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"))
    error_message = Column(Text)
    created_at = Column(TIMESTAMP(timezone=False), server_default=text("SYSTIMESTAMP"))
    updated_at = Column(TIMESTAMP(timezone=False))

    message = relationship("Message")
    user = relationship("User")
    result = relationship("JobResult", uselist=False, back_populates="job")


class JobResult(Base):
    __tablename__ = "job_results"

    job_id = Column(Integer, ForeignKey("jobs.id"), primary_key=True)
    result_json = Column(Text)
    output_ref = Column(String(2000))
    created_at = Column(TIMESTAMP(timezone=False), server_default=text("SYSTIMESTAMP"))


    job = relationship("Job", back_populates="result")


engine, SessionLocal = _create_engine_from_env()
if not engine:
    logger.warning("No se inicializó engine de Oracle; se omite persistencia en DB.")


class LogGolismeo(LogBase):
    def __init__(self, message_queue: [str]):
        super().__init__(message_queue)
        self.m_queue = message_queue


def _get_session():
    if not SessionLocal:
        return None
    return SessionLocal()


def get_engine():
    return engine


def validate_user(phone_number: str, name: str | None = None):
    """Guarda un usuario si no existe en la base de datos."""
    session = _get_session()
    if not session:
        return
    try:
        user = session.query(User).filter_by(phone=phone_number).first()
        if not user:
            new_user = User(phone=phone_number, name=name)
            session.add(new_user)
            session.commit()
            logger.info("👤 Usuario registrado: %s", phone_number)
        else:
            logger.info("✅ Usuario ya existente: %s", phone_number)
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("❌ Error al guardar usuario %s: %s", phone_number, exc)
    finally:
        session.close()


def validate_message(sender: str, receiver: str | None, message: str, message_type: str,) -> int | None:
    """Guarda un mensaje en la base de datos y devuelve su id."""
    session = _get_session()
    if not session:
        return None

    try:
        new_message = Message(
            sender_phone=sender,
            receiver_phone=receiver,
            message=message,
            message_type=message_type,
        )
        session.add(new_message)
        session.commit()
        logger.info("📩 Mensaje tipo %s registrado con id=%s ✅", message_type, new_message.id)
        return new_message.id
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("❌ Error al insertar mensaje en la base de datos: %s", exc)
        return None
    finally:
        session.close()



def create_job(job_type: str, source_message_id: int, user_id: int | None = None,) -> int | None:
    """Crea un job asociado a un mensaje y devuelve su id."""
    session = _get_session()
    if not session:
        return None

    try:
        job = Job(
            job_type=job_type,
            status="queued",
            source_message_id=source_message_id,
            user_id=user_id,
        )
        session.add(job)
        session.commit()
        logger.info("🧵 Job %s creado para message_id=%s", job.id, source_message_id)
        return job.id
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("❌ Error al crear job para message_id=%s: %s", source_message_id, exc)
        return None
    finally:
        session.close()
