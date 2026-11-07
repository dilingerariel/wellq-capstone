import copy
import hashlib
from datetime import datetime, timedelta
import pytest
from fastapi import HTTPException
from app.config import settings
from app.services.file_validation import validate_document, FileRejected, scanner, ScannerUnavailable
from app.services.storage import StorageService
from app.workers.processing import run_once

def headers(env, **kw):
    return {"Authorization": "Bearer " + env["token"](**kw), "Idempotency-Key": "request-1"}

def initiate(env, data, **changes):
    body = {"client_upload_id": "device-1", "file_name": "synthetic.pdf", "mime_type": "application/pdf",
            "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "test_type": "blood_test",
            "title": "Synthetic test", "test_date": datetime.utcnow().strftime("%Y-%m-%d"), "ai_consent": True}
    body.update(changes)
    r = env["client"].post("/api/v1/clinical-tests/uploads/initiate", headers=headers(env), json=body)
    assert r.status_code == 201, r.text
    doc = env["db"].clinical_tests.find_one({"clinical_test_id": r.json()["clinical_test_id"]})
    return r.json(), body, doc

def complete(env, init, body):
    request = {k: body[k] for k in ("client_upload_id", "size_bytes", "sha256")}
    return env["client"].post("/api/v1/clinical-tests/uploads/" + init["upload_id"] + "/complete", headers=headers(env), json=request)

def test_initiate_replay_conflict_and_quota(env, fake_storage, sample_pdf):
    init, body, _ = initiate(env, sample_pdf)
    env["monkeypatch"].setattr(settings, "MAX_PENDING_UPLOADS", 1)
    r = env["client"].post("/api/v1/clinical-tests/uploads/initiate", headers=headers(env), json=body)
    assert r.status_code == 201 and r.json() == init
    assert env["db"].clinical_tests.count_documents({}) == 1
    body["title"] = "changed"
    assert env["client"].post("/api/v1/clinical-tests/uploads/initiate", headers=headers(env), json=body).status_code == 409

def test_refresh_replay_does_not_consume_limit(env, fake_storage, sample_pdf):
    init, body, _ = initiate(env, sample_pdf)
    url = "/api/v1/clinical-tests/uploads/" + init["upload_id"] + "/refresh-url"
    request = {k: body[k] for k in ("client_upload_id", "sha256")}
    a = env["client"].post(url, headers=headers(env), json=request)
    b = env["client"].post(url, headers=headers(env), json=request)
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert env["db"].clinical_tests.find_one({})["upload"]["refresh_count"] == 1

def test_missing_object_never_ready(env, fake_storage, sample_pdf):
    init, body, _ = initiate(env, sample_pdf)
    assert complete(env, init, body).status_code == 200
    assert run_once(env["raw"])
    doc = env["db"].clinical_tests.find_one({})
    assert doc["upload"]["status"] == "processing"
    assert doc["upload"]["job"]["status"] == "pending"
    status = env["client"].get("/api/v1/clinical-tests/uploads/" + init["upload_id"] + "/status", headers=headers(env)).json()
    assert status["local_file_can_be_deleted"] is False

def test_scanner_unavailable_never_approves(env, fake_storage, sample_pdf):
    init, body, doc = initiate(env, sample_pdf)
    fake_storage[doc["file"]["gcs_object_key"]] = (sample_pdf, "application/pdf", 1)
    complete(env, init, body)
    env["monkeypatch"].setattr(scanner, "scan", lambda data: (_ for _ in ()).throw(ScannerUnavailable()))
    run_once(env["raw"])
    assert env["db"].clinical_tests.find_one({})["upload"]["status"] == "processing"

def test_safe_storage_does_not_wait_for_ai(env, fake_storage, sample_pdf):
    init, body, doc = initiate(env, sample_pdf)
    fake_storage[doc["file"]["gcs_object_key"]] = (sample_pdf, "application/pdf", 7)
    env["monkeypatch"].setattr(scanner, "scan", lambda data: None)
    assert complete(env, init, body).status_code == 200
    assert complete(env, init, body).status_code == 200
    run_once(env["raw"])
    doc = env["db"].clinical_tests.find_one({})
    assert doc["upload"]["status"] == "ready_for_review" and doc["file"]["generation"] == 7
    assert doc["extraction_job"]["status"] == "pending"
    status = env["client"].get("/api/v1/clinical-tests/uploads/" + init["upload_id"] + "/status", headers=headers(env)).json()
    assert status["local_file_can_be_deleted"] is True
    # Unconfigured provider leaves extraction queued without affecting durable storage.
    run_once(env["raw"], "extraction")
    doc = env["db"].clinical_tests.find_one({})
    assert doc["extraction_job"]["status"] == "pending"
    assert doc["upload"]["status"] == "ready_for_review"
    assert env["db"].clinical_test_extractions.count_documents({}) == 0

def test_wrong_checksum_and_malware_reject(env, fake_storage, sample_pdf):
    init, body, doc = initiate(env, sample_pdf)
    fake_storage[doc["file"]["gcs_object_key"]] = (sample_pdf + b"corrupt", "application/pdf", 1)
    complete(env, init, body)
    run_once(env["raw"])
    assert env["db"].clinical_tests.find_one({})["upload"]["status"] == "rejected"

def test_expired_lease_recovered(env, fake_storage, sample_pdf):
    init, body, doc = initiate(env, sample_pdf)
    complete(env, init, body)
    env["db"].clinical_tests.update_one({"_id": doc["_id"]}, {"$set": {"upload.job.status": "running",
        "upload.job.lease_until": datetime.utcnow() - timedelta(seconds=1)}})
    assert run_once(env["raw"])
    assert env["db"].clinical_tests.find_one({})["upload"]["job"]["attempts"] == 1

@pytest.mark.parametrize("case", ["hash", "size", "mime", "corrupt", "unsupported", "large"])
def test_document_validation_failures(env, sample_pdf, case):
    data, mime, size, sha = sample_pdf, "application/pdf", len(sample_pdf), hashlib.sha256(sample_pdf).hexdigest()
    if case == "hash": sha = "a" * 64
    if case == "size": size += 1
    if case == "mime": mime = "image/png"
    if case == "corrupt": data = b"%PDF-invalid"; size = len(data); sha = hashlib.sha256(data).hexdigest()
    if case == "unsupported": data = b"unknown"; size = len(data); sha = hashlib.sha256(data).hexdigest()
    if case == "large": env["monkeypatch"].setattr(settings, "MAX_CLINICAL_FILE_BYTES", 1)
    with pytest.raises(FileRejected): validate_document(data, mime, size, sha)

def test_valid_pdf(env, sample_pdf):
    assert validate_document(sample_pdf, "application/pdf", len(sample_pdf), hashlib.sha256(sample_pdf).hexdigest()) == "application/pdf"

def test_storage_never_falls_back(env):
    storage = StorageService()
    env["monkeypatch"].setattr(settings, "GCS_BUCKET_NAME", None)
    with pytest.raises(HTTPException): storage.generate_upload_url("quarantine/clinical-tests/a/original", "application/pdf")
    with pytest.raises(HTTPException): storage.verify_object_exists("missing")
    with pytest.raises(ValueError): storage.generate_download_url("quarantine/missing")
    with pytest.raises(ScannerUnavailable): scanner.scan(b"synthetic")

def test_concurrent_initiation_preserves_one_session(env, fake_storage, sample_pdf):
    from concurrent.futures import ThreadPoolExecutor
    init, body, _ = initiate(env, sample_pdf)
    def call(_):
        return env["client"].post("/api/v1/clinical-tests/uploads/initiate", headers=headers(env), json=body)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(call, range(8)))
    assert all(r.status_code == 201 and r.json()["upload_id"] == init["upload_id"] for r in results)
    assert env["db"].clinical_tests.count_documents({}) == 1

@pytest.mark.parametrize("format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("HEIC", "image/heic")])
def test_supported_image_content(env, format, mime):
    import io
    from PIL import Image
    image = Image.new("RGB", (2, 2), "white"); out = io.BytesIO()
    if format == "HEIC":
        from pillow_heif import from_pillow
        from_pillow(image).save(out)
    else:
        image.save(out, format=format)
    data = out.getvalue()
    assert validate_document(data, mime, len(data), hashlib.sha256(data).hexdigest()) == mime

def test_infected_document_is_never_promoted(env, fake_storage, sample_pdf):
    init, body, doc = initiate(env, sample_pdf)
    fake_storage[doc["file"]["gcs_object_key"]] = (sample_pdf, "application/pdf", 1)
    env["monkeypatch"].setattr(scanner, "scan", lambda data: (_ for _ in ()).throw(FileRejected("MALWARE_DETECTED")))
    complete(env, init, body); run_once(env["raw"])
    assert env["db"].clinical_tests.find_one({})["upload"]["status"] == "rejected"
    assert not any(k.startswith("private/") for k in fake_storage)

def test_exhausted_lease_becomes_terminal(env, fake_storage, sample_pdf):
    init, body, doc = initiate(env, sample_pdf); complete(env, init, body)
    env["db"].clinical_tests.update_one({"_id": doc["_id"]}, {"$set": {"upload.job.status": "running",
        "upload.job.attempts": settings.JOB_MAX_ATTEMPTS, "upload.job.lease_until": datetime.utcnow() - timedelta(seconds=1)}})
    run_once(env["raw"])
    assert env["db"].clinical_tests.find_one({})["upload"]["status"] == "failed"

def test_real_signer_arguments_enforce_short_expiry_and_create_only(env):
    calls = []
    class Blob:
        def generate_signed_url(self, **kwargs):
            calls.append(kwargs)
            return "https://unit.test.invalid/signed"
    class Bucket:
        def blob(self, *args, **kwargs): return Blob()
    storage = StorageService(); storage.bucket = Bucket()
    result = storage.generate_upload_url("quarantine/clinical-tests/test/original", "application/pdf", 999)
    assert result["required_headers"]["x-goog-if-generation-match"] == "0"
    assert calls[-1]["expiration"].total_seconds() == 15 * 60
    storage.generate_download_url("private/clinical-tests/test/original", 999, generation=7)
    assert calls[-1]["expiration"].total_seconds() == 5 * 60 and calls[-1]["generation"] == 7

def test_lost_commit_ack_does_not_requeue_completed_job(env, fake_storage, sample_pdf):
    from contextlib import contextmanager
    from app.tenancy import TenantDatabase
    init, body, doc = initiate(env, sample_pdf)
    fake_storage[doc["file"]["gcs_object_key"]] = (sample_pdf, "application/pdf", 1)
    env["monkeypatch"].setattr(scanner, "scan", lambda data: None)
    complete(env, init, body)
    original = TenantDatabase.atomic
    from contextvars import ContextVar
    depth = ContextVar("memory_transaction_depth", default=0)
    @contextmanager
    def commit_then_lose_ack(self):
        # Nested facade writes reuse the outer real session; only the actual
        # outer commit can lose an acknowledgement. The memory model has none.
        previous = depth.get()
        marker = depth.set(previous + 1)
        try:
            with original(self):
                yield
        finally:
            depth.reset(marker)
        if previous == 0:
            raise RuntimeError("Simulated lost commit acknowledgement")
    env["monkeypatch"].setattr(TenantDatabase, "atomic", commit_then_lose_ack)
    assert run_once(env["raw"])
    stored = env["db"].clinical_tests.find_one({})
    assert stored["upload"]["status"] == "ready_for_review"
    assert stored["upload"]["job"]["status"] == "done"
    assert not run_once(env["raw"])
