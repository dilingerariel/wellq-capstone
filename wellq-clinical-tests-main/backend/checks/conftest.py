"""Entirely in-process synthetic tests; no socket, live API, Mongo or GCS."""
import copy
import io
import sys
import threading
import socket
import time
from contextlib import contextmanager
from pathlib import Path
import pytest
import mongomock
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.database import mongodb, INDEXES
from app.tenancy import TenantDatabase
from app.dependencies.auth import current_identity
from app.services.storage import storage_service


def export_precondition(env, headers, **params):
    """Upgrade a test client explicitly; never patch all requests or bypass 428."""
    query = {k: v for k, v in params.items() if k in {"clinical_test_id", "window_months"}}
    response = env["client"].get("/api/v1/patients/patient-test/lab-report", headers=headers, params=query)
    assert response.status_code == 200
    return {**params, "expected_source_version": response.json()["source_version"]}

@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Network forbidden in checks")))
    raw = mongomock.MongoClient().wellq_isolated_memory
    for collection, entries in INDEXES.items():
        for name, keys in entries:
            raw[collection].create_index(keys, unique=True, name=name)
    lock = threading.RLock()
    @contextmanager
    def memory_atomic(self):
        # Model rollback for application tests; this does NOT verify Mongo transactions.
        with lock:
            before = {n: list(raw[n].find()) for n in raw.list_collection_names()}
            try:
                yield
            except BaseException:
                for n in raw.list_collection_names():
                    raw[n].delete_many({})
                for n, docs in before.items():
                    if docs: raw[n].insert_many(copy.deepcopy(docs))
                raise
    monkeypatch.setattr(TenantDatabase, "atomic", memory_atomic)
    monkeypatch.setattr(mongodb, "db", raw)
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "AI_PROVIDER_APPROVED", True)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    monkeypatch.setattr(settings, "JWT_PUBLIC_KEY", public)
    monkeypatch.setattr(settings, "JWT_ISSUER", "https://identity.test.invalid")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "wellq-isolated")
    current_identity.set(None)
    grants = ["clinical:read", "clinical:write", "documents:download", "reports:export", "clinical:review",
              "extractions:confirm", "extractions:validate"]
    def token(role="patient", identity="patient-test", tenant="tenant-a", **overrides):
        now = int(time.time())
        payload = {"sub": "account:" + identity, "role": role, "client_id": tenant, "resource_id": identity,
            ("patient_id" if role == "patient" else "clinician_id"): identity,
            "iat": now, "nbf": now, "exp": now + 300, "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE, "permissions": grants, "capabilities": ["report_export"]}
        payload.update(overrides)
        return jwt.encode(payload, private, algorithm="RS256")
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)  # No context/lifespan: no real DB startup.
    return {"raw": raw, "db": TenantDatabase(raw, "tenant-a"), "token": token, "client": client,
            "key": private, "monkeypatch": monkeypatch}

@pytest.fixture
def sample_pdf():
    from reportlab.pdfgen import canvas
    output = io.BytesIO(); c = canvas.Canvas(output); c.drawString(30, 40, "SYNTHETIC TEST DOCUMENT"); c.save()
    return output.getvalue()

@pytest.fixture
def fake_storage(env):
    objects = {}
    def sign(key, content_type, expiration_minutes=15, **_constraints):
        return {"method": "PUT", "signed_url": "https://storage.test.invalid/upload", "required_headers": {"Content-Type": content_type},
                "expires_at": "2099-01-01T00:00:00Z"}
    def read(key, generation=None):
        if key not in objects:
            from app.services.storage import unavailable
            raise unavailable()
        return objects[key]
    def promote(key, generation, sha):
        target = key.replace("quarantine/", "private/", 1) + "/" + sha
        objects[target] = objects[key]
        return target, objects[key][2]
    def upload(object_key, data, content_type="application/pdf"):
        objects[object_key] = (data, content_type, 1)
        return "gcs"
    for name, value in {"generate_upload_url": sign, "read_object": read, "promote": promote, "upload_bytes": upload,
                        "generate_download_url": lambda **kw: {"url": "https://storage.test.invalid/download", "expires_at": "2099-01-01T00:00:00Z"}}.items():
        env["monkeypatch"].setattr(storage_service, name, value)
    return objects
