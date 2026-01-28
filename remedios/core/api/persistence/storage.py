import json
import logging
import sys
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from .db import _get_session
from .models import Job, JobResult, Message, User

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

def validate_user(phone_number: str, name: str | None = None):
    """Guarda un usuario si no existe; nunca devuelve None (lanza RuntimeError en fallo)."""
    session = _get_session()
    if not session:
        raise RuntimeError("Sesión de base de datos no inicializada (revisa ORACLE_* y wallet)")
    try:
        user = session.query(User).filter_by(phone=phone_number).first()
        if not user:
            new_user = User(phone=phone_number, name=name)
            session.add(new_user)
            session.commit()
            logger.info("👤 Usuario registrado: %s", phone_number)
            return new_user
        else:
            logger.info("✅ Usuario ya existente: %s", phone_number)
            return user
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("❌ Error al guardar usuario %s: %s", phone_number, exc)
        raise
    finally:
        session.close()


def validate_message(sender: str, receiver: str | None, message: str, message_type: str, message_id: str,
                     number_id: str) -> int | None:
    """Guarda un mensaje en la base de datos y devuelve su id."""
    session = _get_session()
    if not session:
        return None

    try:
        new_message = Message(
            sender_phone=sender,
            message_id=message_id,
            number_id=number_id,
            receiver_phone=receiver if receiver else None,
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


def update_job_status(job_id: int, status: str, error_message: str | None = None) -> bool:
    """Actualiza el estado de un job existente."""
    session = _get_session()
    if not session:
        return False
    try:
        job = session.get(Job, job_id)
        if not job:
            logger.warning("Job %s no encontrado, no se actualiza status", job_id)
            return False
        job.status = status
        job.error_message = error_message
        job.updated_at = datetime.utcnow()
        session.commit()
        return True
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("❌ Error al actualizar job %s: %s", job_id, exc)
        return False
    finally:
        session.close()


def save_job_result(job_id: int, result: str | dict, output_ref: str | None = None,
                    duration_ms: int | None = None, started_at: datetime | None = None,
                    finished_at: datetime | None = None, audio_duration_seconds: float | None = None) -> bool:
    """Guarda el resultado de un job (sobrescribe si ya existe)."""
    session = _get_session()
    if not session:
        return False
    try:
        payload = result if isinstance(result, str) else json.dumps(result)
        existing = session.get(JobResult, job_id)
        if existing:
            existing.result_json = payload
            existing.output_ref = output_ref
            existing.duration_ms = duration_ms
            existing.started_at = started_at
            existing.finished_at = finished_at
            existing.audio_duration_seconds = audio_duration_seconds
        else:
            jr = JobResult(
                job_id=job_id,
                result_json=payload,
                output_ref=output_ref,
                duration_ms=duration_ms,
                started_at=started_at,
                finished_at=finished_at,
                audio_duration_seconds=audio_duration_seconds,
            )
            session.add(jr)
        session.commit()
        return True
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("❌ Error al guardar job_result %s: %s", job_id, exc)
        return False
    finally:
        session.close()
