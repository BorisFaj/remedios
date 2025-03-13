import os
import logging
import sys
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
env_file = find_dotenv(".env")
load_dotenv(env_file)

# Configurar la conexión a la base de datos
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@golismeos.c5aqi48uyz13.eu-north-1.rds.amazonaws.com:5432/golismeos"
engine = create_engine(DATABASE_URL)

# Crear sesión de base de datos
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

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
Base.metadata.create_all(engine)

def save_user(phone_number):
    """Guarda un usuario si no existe en la base de datos."""
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

def save_message(sender, receiver, message, message_type="text"):
    """Guarda un mensaje en la base de datos."""
    save_user(sender)  # Registrar el usuario si no existe
    save_user(receiver)  # Registrar el receptor si no existe

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

def get_last_text_messages(phone_number, n=10):
    """Devuelve los últimos N mensajes de texto enviados o recibidos por un usuario."""
    try:
        messages = session.query(Message).filter(
            (Message.sender_phone == phone_number) | (Message.receiver_phone == phone_number),
            Message.message_type == "text"
        ).order_by(Message.timestamp.desc()).limit(n).all()

        return messages[::-1]  # Ordenarlos del más antiguo al más reciente
    except Exception as e:
        logger.error(f"❌ Error al obtener la conversación de {phone_number}: {e}")
        return []

def format_conversation_history(phone_number, new_message, bot_name="Remedios", user_name="User"):
    """Devuelve la conversación formateada con el usuario y el bot."""
    historial = get_last_text_messages(phone_number)
    logger.info(f"({phone_number})[HISTORIAL]: {historial}")
    formatted_history = []

    for msg in historial:
        if msg.sender_phone == phone_number:
            formatted_history.append(f"[{user_name}] {msg.message}")
        else:
            formatted_history.append(f"[{bot_name}] {msg.message}")

    formatted_history.append(f"[{user_name}] {new_message}")
    formatted_history.append(f"[{bot_name}] ")

    return "\n".join(formatted_history)

