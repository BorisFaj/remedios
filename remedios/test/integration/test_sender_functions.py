import os
import pytest
import importlib

@pytest.fixture(scope="module")
def setup_test_db():
    os.environ["ORACLE_USER"] = "TEST"

    from remedios.core.api.persistence import db, storage
    importlib.reload(db)
    importlib.reload(storage)

    if not db.engine:
        pytest.skip("No se pudo conectar a la base de datos (engine es None). Revisa configuración.")

    storage.Base.metadata.create_all(db.engine)

    yield storage

def test_validate_user(setup_test_db):
    sender = setup_test_db
    
    phone = "123456789"
    name = "Test User"
    
    # si existe, validate_user no debe fallar
    sender.validate_user(phone, name)
    
    session = sender.SessionLocal()
    user = session.query(sender.User).filter_by(phone=phone).first()
    assert user is not None
    assert user.name == name
    session.close()

def test_validate_message(setup_test_db):
    sender = setup_test_db
    sender_phone = "123456789"
    receiver_phone = "987654321"
    
    sender.validate_user(receiver_phone, "Receiver User")
    
    msg_id = sender.validate_message(
        sender_phone,
        receiver_phone,
        "Hello World",
        "text",
        "msg-1",
        "number-1",
    )
    assert msg_id is not None
    
    session = sender.SessionLocal()
    msg = session.query(sender.Message).filter_by(id=msg_id).first()
    assert msg is not None
    assert msg.message == "Hello World"
    session.close()

def test_create_job(setup_test_db):
    sender = setup_test_db
    
    # Pre-requisito: mensaje existente
    sender_phone = "123456789"
    receiver_phone = "987654321"
    msg_id = sender.validate_message(
        sender_phone,
        receiver_phone,
        "Job Message",
        "text",
        "msg-2",
        "number-2",
    )
    
    job_id = sender.create_job("transcribe", msg_id)
    assert job_id is not None
    
    session = sender.SessionLocal()
    job = session.query(sender.Job).filter_by(id=job_id).first()
    assert job is not None
    assert job.status == "queued"
    assert job.source_message_id == msg_id
    session.close()
