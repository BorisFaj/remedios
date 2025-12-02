import os
import logging
import sys
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from .base import LogBase

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Configurar la conexión a la base de datos (opcional)
DB_URL = os.getenv("DB_URL")
if DB_URL:
    DATABASE_URL = f"postgresql://{DB_URL}"
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    Base = declarative_base()
else:
    logger.warning("DB_URL no definida; logging a DB deshabilitado")
    engine = None
    SessionLocal = None
    session = None
    Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String, unique=True, nullable=False)
    messages_sent = relationship("Message", back_populates="sender", foreign_keys="[Message.sender_phone]")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_phone = Column(String, ForeignKey("users.phone"), nullable=False)
    receiver_phone = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    message_type = Column(String, default="text")
    timestamp = Column(DateTime, default=datetime.utcnow)

    sender = relationship("User", back_populates="messages_sent")

# Crear las tablas en la base de datos (si no existen)
if engine:
    Base.metadata.create_all(engine)


class LogGolismeo(LogBase):
    def __init__(self, message_queue: [str]):
        super().__init__(message_queue)
        self.m_queue = message_queue


def check_user(phone_number):
    """Guarda un usuario si no existe en la base de datos."""
    if not session:
        return
    try:
        user = session.query(User).filter_by(phone=phone_number).first()
        if not user:
            new_user = User(phone=phone_number)
            session.add(new_user)
            session.commit()
            logger.info(f"👤 Usuario registrado: {phone_number}")
        else:
            logger.info(f"✅ Usuario ya existente: {phone_number}")
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Error al guardar usuario {phone_number}: {e}")

def validate_message(sender, receiver, message, message_type="text"):
    """Guarda un mensaje en la base de datos."""
    if not session:
        return
    check_user(sender)  # Registrar el usuario si no existe
    check_user(receiver)  # Registrar el receptor si no existe

    try:
        new_message = Message(
            sender_phone=sender,
            receiver_phone=receiver,
            message=message,
            message_type=message_type
        )
        session.add(new_message)
        session.commit()
        logger.info(f"📩 Mensaje tipo {message_type} registrado en la base de datos ✅")
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Error al insertar en la base de datos: {e}")

def __get_last_text_messages(phone_number, n=10):
    """Devuelve los últimos N mensajes de texto enviados o recibidos por un usuario."""
    if not session:
        return []
    try:
        messages = session.query(Message).filter(
            (Message.sender_phone == phone_number) | (Message.receiver_phone == phone_number),
            Message.message_type == "text"
        ).order_by(Message.timestamp.desc()).limit(n).all()

        return messages[::-1]  # Ordenarlos del más antiguo al más reciente
    except Exception as e:
        logger.error(f"❌ Error al obtener la conversación de {phone_number}: {e}")
        return []

def get_context():
    return "Eres un asistente conversacional de WhatsApp llamado 'Remedios', diseñada para ayudar a los usuarios con reservas, consultas generales y soporte básico. Usa un tono amigable, informal y profesional, como si fueras un amigo conocedor que ayuda rápidamente. Responde siempre en el idioma del mensaje del usuario. Limita tus respuestas a 2-3 frases cortas, a menos que el usuario solicite más detalles. Si no entiendes la solicitud o no puedes responder, di algo como: 'Lo siento, no entendí bien. ¿Podrías darme más detalles o reformular tu pregunta?' Si el usuario pide una reserva, pregunta por los detalles necesarios (fecha, hora, servicio, ubicación) y confirma la acción, o deriva a un agente humano si no puedes completarla. Evita dar opiniones personales, consejos médicos, legales o financieros, y no respondas a preguntas sobre temas sensibles o éticos; en su lugar, sugiere consultar a un profesional."

def get_embeddings_context(phone_number, new_message, bot_name="Remedios", user_name="User"):
    """Devuelve la conversación formateada con el usuario y el bot."""
    historial = __get_last_text_messages(phone_number)
    logger.info(f"({phone_number})[HISTORIAL]: {historial}")
    formatted_history = [f"[SYSTEM]: {get_context()}"]

    for msg in historial:
        if msg.sender_phone == phone_number:
            formatted_history.append(f"[{user_name}]: {msg.message}")
        else:
            formatted_history.append(f"[{bot_name}]: {msg.message}")

    formatted_history.append(f"[{user_name}]: {new_message}")
    formatted_history.append(f"[{bot_name}]: ")

    return "\n".join(formatted_history)
