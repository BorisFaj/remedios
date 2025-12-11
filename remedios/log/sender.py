import logging
import os
import sys
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
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


def check_user(phone_number: str, name: str | None = None):
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


def validate_message(sender: str, receiver: str, message: str, message_type: str = "text"):
    """Guarda un mensaje en la base de datos."""
    session = _get_session()
    if not session:
        return

    check_user(sender)
    check_user(receiver)

    try:
        new_message = Message(
            sender_phone=sender,
            receiver_phone=receiver,
            message=message,
            message_type=message_type,
        )
        session.add(new_message)
        session.commit()
        logger.info("📩 Mensaje tipo %s registrado en la base de datos ✅", message_type)
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("❌ Error al insertar en la base de datos: %s", exc)
    finally:
        session.close()


def __get_last_text_messages(phone_number: str, n: int = 10):
    """Devuelve los últimos N mensajes de texto enviados o recibidos por un usuario."""
    session = _get_session()
    if not session:
        return []
    try:
        messages = (
            session.query(Message)
            .filter(
                (Message.sender_phone == phone_number) | (Message.receiver_phone == phone_number),
                Message.message_type == "text",
            )
            .order_by(Message.created_at.desc())
            .limit(n)
            .all()
        )
        return list(reversed(messages))
    except SQLAlchemyError as exc:
        logger.error("❌ Error al obtener la conversación de %s: %s", phone_number, exc)
        return []
    finally:
        session.close()


def get_context():
    return "Eres un asistente conversacional de WhatsApp llamado 'Remedios', diseñada para ayudar a los usuarios con reservas, consultas generales y soporte básico. Usa un tono amigable, informal y profesional, como si fueras un amigo conocedor que ayuda rápidamente. Responde siempre en el idioma del mensaje del usuario. Limita tus respuestas a 2-3 frases cortas, a menos que el usuario solicite más detalles. Si no entiendes la solicitud o no puedes responder, di algo como: 'Lo siento, no entendí bien. ¿Podrías darme más detalles o reformular tu pregunta?' Si el usuario pide una reserva, pregunta por los detalles necesarios (fecha, hora, servicio, ubicación) y confirma la acción, o deriva a un agente humano si no puedes completarla. Evita dar opiniones personales, consejos médicos, legales o financieros, y no respondas a preguntas sobre temas sensibles o éticos; en su lugar, sugiere consultar a un profesional."


def get_embeddings_context(phone_number, new_message, bot_name="Remedios", user_name="User"):
    """Devuelve la conversación formateada con el usuario y el bot."""
    historial = __get_last_text_messages(phone_number)
    logger.info("(%s)[HISTORIAL]: %s", phone_number, historial)
    formatted_history = [f"[SYSTEM]: {get_context()}"]

    for msg in historial:
        if msg.sender_phone == phone_number:
            formatted_history.append(f"[{user_name}]: {msg.message}")
        else:
            formatted_history.append(f"[{bot_name}]: {msg.message}")

    formatted_history.append(f"[{user_name}]: {new_message}")
    formatted_history.append(f"[{bot_name}]: ")

    return "\n".join(formatted_history)


def get_engine():
    """Devuelve el engine activo (o None si no se configuró)."""
    return engine
