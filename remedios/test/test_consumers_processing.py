import base64
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
    calls = []

    monkeypatch.setattr(text_consumer, "ask", lambda text: "ok")

    def fake_post_internal(url, token, path, payload):
        calls.append((path, payload))

        class FakeResp:
            def json(self):
                return {"status": "ok"}

        return FakeResp()

    monkeypatch.setattr(text_consumer, "post_internal_api", fake_post_internal)
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

    cfg = {"internal_api_url": "http://internal", "internal_api_token": "tok"}
    text_consumer.process_message(_encode_msg(msg), cfg)

    assert ("processing" in {s for _, s, _ in status_calls})
    assert ("completed" in {s for _, s, _ in status_calls})
    assert save_calls, "save_job_result no fue llamado"
    _, kwargs = save_calls[-1]
    assert kwargs["duration_ms"] >= 0
    assert kwargs["started_at"] is not None
    assert kwargs["finished_at"] is not None
    assert any(path == "/internal/send_text_answer" for path, _ in calls)


def test_audio_consumer_transcribes_and_replies(monkeypatch):
    calls = []

    def fake_post_internal(url, token, path, payload):
        calls.append((path, payload))

        class FakeResp:
            def __init__(self, data):
                self._data = data

            def json(self):
                return self._data

        if path == "/internal/extract_audio":
            audio_b64 = base64.b64encode(b"audio-bytes").decode()
            return FakeResp({"status": "ok", "audio_b64": audio_b64})

        return FakeResp({"status": "ok"})

    monkeypatch.setattr(turbo_consumer, "post_internal_api", fake_post_internal)
    monkeypatch.setattr(turbo_consumer, "transcribe", lambda audio: ("transcripcion", 4.0))

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
    )

    cfg = {
        "internal_api_url": "http://internal",
        "internal_api_token": "tok",
    }

    assert turbo_consumer.process_message(_encode_msg(msg), cfg)

    paths = [p for p, _ in calls]
    assert "/internal/extract_audio" in paths
    assert "/internal/send_text_answer" in paths
    # Último call incluye result con duración y transcript
    result_payloads = [payload for path, payload in calls if path == "/internal/job_status" and "result" in payload]
    assert result_payloads, "job_status con result no fue enviado"
    latest = result_payloads[-1]
    assert latest["result"]["transcript"] == "transcripcion"
    assert latest["result"]["response_text"] == "transcripcion"
    assert latest["audio_duration_seconds"] == 4.0
