import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.schema import DefaultClause
from sqlalchemy.orm import sessionmaker

from remedios.core.api.persistence import db, storage
from remedios.core.api.persistence.models import Base


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:", future=True, implicit_returning=False)
    # Ajustar defaults Oracle para SQLite.
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.server_default is not None:
                column.server_default = DefaultClause(text("CURRENT_TIMESTAMP"))
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        Base.metadata.create_all(engine)
    except Exception as exc:
        pytest.skip(f"SQLite no soporta el schema Oracle: {exc}")

    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", SessionLocal)

    return SessionLocal


def test_validate_user_creates(sqlite_session):
    user = storage.validate_user("123456789", "Test User")
    assert user is not None
    assert user.phone == "123456789"
    assert user.name == "Test User"


def test_validate_message_creates(sqlite_session):
    storage.validate_user("123456789", "Test User")
    msg_id = storage.validate_message(
        sender="123456789",
        receiver=None,
        message="Hola",
        message_type="text",
        message_id="msg-1",
        number_id="num-1",
    )
    assert msg_id is not None


def test_create_job_updates_status(sqlite_session):
    storage.validate_user("123456789", "Test User")
    msg_id = storage.validate_message(
        sender="123456789",
        receiver=None,
        message="Hola",
        message_type="text",
        message_id="msg-2",
        number_id="num-2",
    )
    job_id = storage.create_job("text", msg_id)
    assert job_id is not None

    assert storage.update_job_status(job_id, "processing") is True


def test_save_job_result(sqlite_session):
    storage.validate_user("123456789", "Test User")
    msg_id = storage.validate_message(
        sender="123456789",
        receiver=None,
        message="Hola",
        message_type="text",
        message_id="msg-3",
        number_id="num-3",
    )
    job_id = storage.create_job("text", msg_id)
    ok = storage.save_job_result(
        job_id,
        {"answer": "ok"},
        output_ref="unit.test",
        duration_ms=10,
    )
    assert ok is True
