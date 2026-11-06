"""Real HTTP + authenticated Mongo replica set, with explicit object/AI/scanner doubles."""
import base64
import copy
import hashlib
import io
import json
import time
import uuid
from datetime import date
from pathlib import Path

import httpx
import jwt
import pytest
from reportlab.pdfgen import canvas
from integration.guard import database
from app.services.catalog import catalog_service

GRANTS = ["clinical:read", "clinical:write", "documents:download", "extractions:confirm", "extractions:validate", "clinical:review", "reports:export"]
VALUES = {"hemoglobin": 14.2, "glucose": 90, "cholesterol_total": 170, "ldl_cholesterol": 100,
          "hdl_cholesterol": 55, "triglycerides": 96, "creatinine": 1, "vitamin_d": 50,
          "calcium": 9.5, "crp_high_sensitivity": 1}


def output(codes=None, day=None, kind="blood_panel"):
    panels = {}
    for cat in catalog_service.list_catalog():
        code = cat["marker_code"]
        if codes is not None and code not in codes:
            continue
        panel = panels.setdefault(cat["panel_code"], {"panel_code": cat["panel_code"],
            "panel_name_raw": "SYNTHETIC ONLY", "specimen": cat["specimen"], "markers": []})
        panel["markers"].append({"marker_code": code, "raw_name": "SYNTHETIC " + code,
            "value_raw": str(VALUES[code]), "unit_raw": cat["canonical_unit"],
            "confidence": dict.fromkeys(["value", "unit", "reference", "name"], .99),
            "page": 1, "evidence": "Synthetic integration annotation"})
    return {"schema_version": "1.0", "document_type": kind, "language": "es", "page_count": 1,
            "collection_date": day or date.today().isoformat(), "panels": list(panels.values())}


def pdf(payload):
    data = io.BytesIO(); c = canvas.Canvas(data)
    c.drawString(10, 750, "SYNTHETIC INTEGRATION DOCUMENT - NOT PATIENT DATA")
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    c.drawString(10, 700, "WQINT:" + encoded); c.save()
    return data.getvalue()


@pytest.fixture(scope="session")
def raw():
    return database()


class Context:
    def __init__(self, raw):
        self.raw = raw
        self.tenant = "integration-" + uuid.uuid4().hex
        self.patient = "patient-" + uuid.uuid4().hex
        self.doctor = "doctor-" + uuid.uuid4().hex
        self.client = httpx.Client(base_url="http://api-int:8000/api/v1", timeout=30)
        raw.patient_access.insert_one({"client_id": self.tenant, "patient_id": self.patient,
                                      "authorised_clinicians": [self.doctor]})

    def token(self, role="patient", identity=None, tenant=None, **overrides):
        own = identity or (self.patient if role == "patient" else self.doctor)
        now = int(time.time())
        claims = {"sub": "account:" + own, "client_id": tenant or self.tenant, "role": role,
            "resource_id": own, "patient_id" if role == "patient" else "clinician_id": own,
            "iat": now, "nbf": now, "exp": now + 600,
            "iss": "https://identity.wellq-integration.invalid", "aud": "wellq-integration-only",
            "permissions": GRANTS, "capabilities": ["report_export"]}
        claims.update(overrides)
        return jwt.encode(claims, Path("/identity/private.pem").read_bytes(), algorithm="RS256")

    def headers(self, role="patient", key=None, **claims):
        return {"Authorization": "Bearer " + self.token(role, **claims), "Idempotency-Key": key or uuid.uuid4().hex}

    def req(self, method, path, role="patient", headers=None, **kwargs):
        headers = headers or self.headers(role)
        for attempt in range(10):
            result = self.client.request(method, path, headers=headers, **kwargs)
            try:
                code = result.json().get("detail", {}).get("code")
            except (ValueError, AttributeError):
                code = None
            if code != "RETRYABLE_CONFLICT":
                return result
            time.sleep(min(.2 * 2 ** attempt, 2))
        raise AssertionError("Real write conflicts did not resolve within retry budget")

    def start(self, payload=None, day=None, ai=True, title="SYNTHETIC TEST"):
        payload = payload or output(day=day)
        data = pdf(payload)
        body = {"client_upload_id": uuid.uuid4().hex, "file_name": "synthetic.pdf", "mime_type": "application/pdf",
            "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "test_type": "blood_test",
            "title": title, "test_date": day or date.today().isoformat(), "ai_consent": ai}
        result = self.req("POST", "/clinical-tests/uploads/initiate", json=body)
        assert result.status_code == 201, "Real initiate must succeed"
        init = result.json()
        upload = self.client.put(init["upload"]["signed_url"], content=data, headers=init["upload"]["required_headers"])
        assert upload.status_code == 200
        complete_body = {k: body[k] for k in ("client_upload_id", "sha256", "size_bytes")}
        done = self.req("POST", "/clinical-tests/uploads/" + init["upload_id"] + "/complete", json=complete_body)
        assert done.status_code == 200 and done.json()["local_file_can_be_deleted"] is False
        return init

    def wait_ext(self, init, previous=None):
        path = "/clinical-tests/" + init["clinical_test_id"] + "/extraction"
        for _ in range(200):
            response = self.req("GET", path)
            if response.status_code == 200 and response.json()["extraction_id"] != previous:
                return response.json()
            time.sleep(.2)
        raise AssertionError("Worker failed to produce expected extraction")

    def confirm(self, init, ext, action="confirm", key=None, edits=None, **extras):
        body = {"action": action, "extraction_id": ext["extraction_id"],
                "document_edits": {"identity_confirmed": True}, "marker_edits": edits or []}
        body.update(extras)
        return self.req("PATCH", "/clinical-tests/" + init["clinical_test_id"] + "/extraction",
                        headers=self.headers(key=key), json=body)

    def ready(self, payload=None, day=None, confirmed=True):
        init = self.start(payload, day); ext = self.wait_ext(init)
        if confirmed:
            response = self.confirm(init, ext)
            assert response.status_code == 200
            ext = response.json()
        return init, ext

    def validate(self, init, **body):
        return self.req("POST", "/clinical-tests/" + init["clinical_test_id"] + "/extraction/validate", role="clinician", json=body)

    def patient_url(self, resource):
        return "/patients/" + self.patient + "/" + resource


@pytest.fixture
def ctx(raw):
    c = Context(raw)
    try:
        yield c
    finally:
        raw["__integration_control"].delete_one({"_id": "faults"})
        c.client.close()
