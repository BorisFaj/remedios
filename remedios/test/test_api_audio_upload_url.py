import sys
import types

# ruff: noqa: E402
import pytest


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


class DummyClient:
    def __init__(self, endpoint="https://objectstorage.test"):
        self.base_client = types.SimpleNamespace(endpoint=endpoint)

    def create_preauthenticated_request(self, namespace, bucket, details):
        assert namespace == "ax8rwj7uv97i"
        assert bucket == "bucket-20260108-2125"
        return types.SimpleNamespace(data=types.SimpleNamespace(access_uri="/p/test-par"))


def _auth_headers():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(server, "INTERNAL_API_TOKEN", "test-token")
    monkeypatch.setattr(server, "OCI_BUCKET_NAME", "bucket-20260108-2125")
    monkeypatch.setattr(server, "OCI_BUCKET_NAMESPACE", "ax8rwj7uv97i")
    monkeypatch.setattr(server, "OCI_BUCKET_PREFIX", "whatsapp")
    monkeypatch.setattr(server, "_get_object_storage_client", lambda: DummyClient())
    server.app.testing = True
    return server.app.test_client()


def test_audio_upload_url_requires_auth(client):
    resp = client.post("/internal/audio_upload_url", json={"job_id": 1, "audio_id": "a1"})
    assert resp.status_code == 401


def test_audio_upload_url_returns_par(client):
    resp = client.post(
        "/internal/audio_upload_url",
        json={"job_id": 123, "audio_id": "audio-1", "mime_type": "audio/ogg"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["object_key"] == "whatsapp/123/audio-1.ogg"
    assert data["upload_url"].startswith("https://objectstorage.test")


def test_audio_upload_url_missing_fields(client):
    resp = client.post(
        "/internal/audio_upload_url",
        json={"job_id": 123},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400
