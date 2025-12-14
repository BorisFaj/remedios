import json
import time
from datetime import datetime, timezone

import pytest

from remedios.commons.schemas import TextMessage, AudioMessage
from remedios.consumers.text import consumer as text_consumer
from remedios.consumers.audio.whisper_turbo import consumer as turbo_consumer


def _encode_msg(model):
    return model.model_dump_json().encode("utf-8")


def test_text_consumer_updates_job(monkeypatch):
    status_calls = []
    save_calls = []

    monkeypatch.setattr(text_consumer, "run", lambda msg: "ok")

    def fake_update(job_id, status, error):
        status_calls.append((job_id, status, error))
        return True

    def fake_save(*args, **kwargs):
        save_calls.append((args, kwargs))
        return True

    monkeypatch.setattr(text_consumer, "update_job_status", fake_update)
    monkeypatch.setattr(text_consumer, "save_job_result", fake_save)

    msg = TextMessage(
        schema_version=1,
        message_id="m1",
        number_id="n1",
        phone=123,
        job_id=42,
        message_type="text",
        timestamp=datetime.now(timezone.utc),
        text="hola",
    )

    text_consumer.process_message(_encode_msg(msg))

    assert ("processing" in {s for _, s, _ in status_calls})
    assert ("completed" in {s for _, s, _ in status_calls})
    assert save_calls, "save_job_result no fue llamado"
    _, kwargs = save_calls[-1]
    assert kwargs["duration_ms"] >= 0
    assert kwargs["started_at"] is not None
    assert kwargs["finished_at"] is not None


def test_audio_consumer_passes_duration(monkeypatch):
    status_calls = []
    save_calls = []

    monkeypatch.setattr(turbo_consumer, "run", lambda msg: "audio-ok")

    def fake_update(job_id, status, error):
        status_calls.append((job_id, status, error))
        return True

    def fake_save(*args, **kwargs):
        save_calls.append((args, kwargs))
        return True

    monkeypatch.setattr(turbo_consumer, "update_job_status", fake_update)
    monkeypatch.setattr(turbo_consumer, "save_job_result", fake_save)

    msg = AudioMessage(
        schema_version=1,
        message_id="m2",
        number_id="n2",
        phone=456,
        job_id=99,
        message_type="audio",
        timestamp=datetime.now(timezone.utc),
        audio_id="a1",
        mime_type="audio/ogg",
        duration_seconds=3,
    )

    turbo_consumer.process_message(_encode_msg(msg))

    assert ("processing" in {s for _, s, _ in status_calls})
    assert ("completed" in {s for _, s, _ in status_calls})
    assert save_calls, "save_job_result no fue llamado"
    _, kwargs = save_calls[-1]
    assert kwargs["audio_duration_seconds"] == 3
    assert kwargs["duration_ms"] >= 0
    assert kwargs["started_at"] is not None
    assert kwargs["finished_at"] is not None

