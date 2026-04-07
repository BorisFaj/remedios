import sys
import types

# ruff: noqa: E402


class _DummyParDetails:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _DummyObjectStorage:
    models = types.SimpleNamespace(CreatePreauthenticatedRequestDetails=_DummyParDetails)


dummy_oci = types.SimpleNamespace(
    object_storage=_DummyObjectStorage(),
    auth=types.SimpleNamespace(
        signers=types.SimpleNamespace(InstancePrincipalsSecurityTokenSigner=object)
    ),
    config=types.SimpleNamespace(from_file=lambda *args, **kwargs: {}),
)
sys.modules.setdefault("oci", dummy_oci)

from remedios.core.api import server


def test_split_text_prefers_space_or_newline(monkeypatch):
    monkeypatch.setattr(server, "PART_PREFIX_RESERVE", 0)
    text = "uno dos tres\ncuatro cinco seis"
    parts = server._split_text_for_whatsapp(text, max_chars=12)
    assert all(len(p) <= 12 for p in parts)
    assert " ".join(parts) == " ".join(text.split())


def test_send_text_answer_splits_and_continues_on_partial_failure(monkeypatch):
    calls = []
    statuses = [200, 400, 200]

    def fake_post(url, payload):
        calls.append((url, payload))
        status = statuses[len(calls) - 1] if len(calls) <= len(statuses) else 200
        return types.SimpleNamespace(status_code=status, text=f"status-{status}")

    monkeypatch.setattr(server, "_post_graph", fake_post)
    long_text = ("hola mundo " * 500).strip()
    server._send_text_answer(
        text=long_text,
        phone_number="51999999999",
        message_id="wamid.123",
        number_id="905378489320288",
    )

    text_calls = [c for c in calls if "text" in c[1]]
    mark_read_calls = [c for c in calls if c[1].get("status") == "read"]

    assert len(text_calls) >= 2
    assert len(mark_read_calls) == 1
    assert all(call[1]["context"]["message_id"] == "wamid.123" for call in text_calls)
    assert text_calls[0][1]["text"]["body"].startswith("(1/")
    assert text_calls[1][1]["text"]["body"].startswith("(2/")
    assert all(len(call[1]["text"]["body"]) <= server.WHATSAPP_TEXT_LIMIT for call in text_calls)
