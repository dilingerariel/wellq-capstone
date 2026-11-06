"""Explicit TEST doubles: filesystem objects/signed local gateway and annotated PDF AI.

These are never selected by app.main or production Dockerfile. They do not
certify GCS, Google signatures/IAM, malware signatures or model accuracy.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from fastapi import HTTPException
from pypdf import PdfReader
from integration.guard import database


@lru_cache(maxsize=1)
def control_database():
    return database()


def controls():
    return control_database()["__integration_control"].find_one({"_id": "faults"}) or {}


def object_path(key):
    root = Path(os.environ["INTEGRATION_STORE"]).resolve()
    result = (root / key).resolve()
    if not result.is_relative_to(root) or not key.startswith(("quarantine/clinical-tests/", "private/")):
        raise ValueError("Non-integration object key")
    return result


def sign(key, method, ttl=300):
    expiry = int(time.time()) + ttl
    secret = Path(os.environ["INTEGRATION_SIGNING_KEY"]).read_bytes()
    signature = hmac.new(secret, f"{method}:{key}:{expiry}".encode(), hashlib.sha256).hexdigest()
    return f"http://objects-int:8080/object/{key}?" + urlencode({"expiry": expiry, "signature": signature})


def verify_signature(key, method, expiry, signature):
    if int(expiry) < time.time():
        return False
    secret = Path(os.environ["INTEGRATION_SIGNING_KEY"]).read_bytes()
    expected = hmac.new(secret, f"{method}:{key}:{expiry}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class FilesystemStorage:
    def generate_upload_url(self, object_key, content_type, expiration_minutes=15):
        if controls().get("upload_signer_unavailable"):
            raise HTTPException(503, detail={"code": "STORAGE_UNAVAILABLE", "message": "Explicit test signer outage"})
        if not object_key.startswith("quarantine/clinical-tests/"):
            raise ValueError("Quarantine only")
        return {"method": "PUT", "signed_url": sign(object_key, "PUT", 900),
                "required_headers": {"Content-Type": content_type, "x-goog-if-generation-match": "0"},
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}

    def generate_download_url(self, object_key, expiration_minutes=5, generation=None):
        if not object_key.startswith("private/"):
            raise ValueError("Private only")
        if controls().get("signer_unavailable"):
            raise HTTPException(503, detail={"code": "STORAGE_UNAVAILABLE", "message": "Explicit test signer outage"})
        return {"url": sign(object_key, "GET"),
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}

    def read_object(self, object_key, generation=None):
        path = object_path(object_key)
        if not path.exists():
            raise HTTPException(503, detail={"code": "STORAGE_UNAVAILABLE", "message": "Test object missing"})
        meta = json.loads(path.with_name(path.name + ".meta").read_text())
        if generation is not None and generation != meta["generation"]:
            raise RuntimeError("Test generation changed")
        return path.read_bytes(), meta["mime"], meta["generation"]

    def promote(self, key, generation, sha):
        data, mime, actual = self.read_object(key, generation)
        if hashlib.sha256(data).hexdigest() != sha:
            raise RuntimeError("Test hash mismatch")
        target = key.replace("quarantine/", "private/", 1) + "/" + sha
        self.upload_bytes(target, data, mime)
        return target, 1

    def upload_bytes(self, object_key, data, content_type="application/pdf"):
        if not object_key.startswith("private/"):
            raise ValueError("Private only")
        path = object_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as f:
                f.write(data)
            path.with_name(path.name + ".meta").write_text(json.dumps({"mime": content_type, "generation": 1}))
        except FileExistsError:
            if path.read_bytes() != data:
                raise RuntimeError("Test create-only conflict")
        return "gcs"  # Existing API enum; implementation explicitly documented as a double.


class AnnotatedPdfProvider:
    model_id, model_version, is_test = "integration-content-fixture", "1", True

    def extract(self, data, mime):
        faults = controls()
        if faults.get("provider_unavailable"):
            raise RuntimeError("Explicit test provider outage")
        time.sleep(min(20, faults.get("provider_delay_seconds", 0)))
        text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
        match = re.search(r"WQINT:([A-Za-z0-9+/=]+)", text)
        if not match:
            raise RuntimeError("Only annotated synthetic integration PDFs are supported")
        return json.loads(base64.b64decode(match.group(1)))


def configure_doubles():
    # This bootstrap is guarded by test project/DB ownership. Faults affect only
    # the named synthetic resource and exercise real Mongo transaction rollback.
    from app.tenancy import TenantCollection
    from pymongo.errors import OperationFailure
    original_insert = TenantCollection.insert_one
    def audit_insert(self, document, **kwargs):
        if document.get("event") in ("clinical_test_metadata_updated", "clinical_test_reviewed"):
            fault = controls().get("review_audit_failure", {})
            if fault.get("resource_id") == document.get("resource_id"):
                if fault.get("when") == "after":
                    original_insert(self, document, **kwargs)
                raise OperationFailure("Explicit synthetic audit failure")
        return original_insert(self, document, **kwargs)
    TenantCollection.insert_one = audit_insert
    if os.environ.get("WELLQ_INTEGRATION_ASSOCIATION_MODE") == "explicit-test-double":
        from app.services import associations
        class SyntheticAssociationVerifier:
            def verify(self, kind, resource_id, scope):
                if controls().get("association_unavailable"):
                    raise TimeoutError("Explicit synthetic verifier outage")
                row = control_database()["__integration_control"].find_one({"_id": "association:" + resource_id}) or {}
                return associations.AssociationDecision(kind, resource_id,
                    row.get("client_id", ""), row.get("patient_id", ""),
                    exists=bool(row), authorized=row.get("authorized", False),
                    active=row.get("active", False), care_relationship_valid=row.get("care_relationship_valid", False))
        associations.association_verifier = SyntheticAssociationVerifier()
    from app.services.storage import storage_service
    from app.services.extractor import extraction_engine
    from app.services.file_validation import scanner, FileRejected
    store = FilesystemStorage()
    for name in ("generate_upload_url", "generate_download_url", "read_object", "promote", "upload_bytes"):
        setattr(storage_service, name, getattr(store, name))
    extraction_engine.provider = AnnotatedPdfProvider()
    if os.environ.get("WELLQ_INTEGRATION_SCAN_MODE") == "explicit-test-double":
        def synthetic_scan(data):
            if b"WELLQ_SYNTHETIC_REJECT" in data:
                raise FileRejected("MALWARE_DETECTED")
        scanner.scan = synthetic_scan
