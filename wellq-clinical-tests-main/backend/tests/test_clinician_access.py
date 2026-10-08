import sys
import os
import uuid
import time
import jwt
import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

BASE_URL = "http://localhost:8000/api/v1"
SECRET = "your-secret-key-here"
ALGORITHM = "HS256"


def _clinician_headers(clinician_id, extra=None):
    token = jwt.encode(
        {"sub": f"usr_{clinician_id}", "role": "clinician", "clinician_id": clinician_id},
        SECRET, algorithm=ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}", **(extra or {})}


@pytest.fixture
def scenario(grant_access):
    patient_id = f"P_SCORE_{uuid.uuid4().hex[:6]}"
    listed = f"DOC_LISTED_{uuid.uuid4().hex[:6]}"      # en authorised_clinicians
    caregiver = f"DOC_CARE_{uuid.uuid4().hex[:6]}"     # care_clinician_id
    stranger = f"DOC_STRANGER_{uuid.uuid4().hex[:6]}"  # sin relación

    grant_access(patient_id, listed)
    grant_access(patient_id, caregiver, via="care")

    token_p = jwt.encode(
        {"sub": f"usr_{patient_id}", "role": "patient", "patient_id": patient_id},
        SECRET, algorithm=ALGORITHM,
    )
    return {
        "patient_id": patient_id,
        "headers_p": {"Authorization": f"Bearer {token_p}", "Idempotency-Key": f"idem_{uuid.uuid4().hex[:8]}"},
        "listed": listed, "caregiver": caregiver, "stranger": stranger,
    }


def _upload_and_confirm(client, headers_p):
    client_upload_id = f"upl_acc_{uuid.uuid4().hex[:8]}"
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    r = client.post("/clinical-tests/uploads/initiate", json={
        "client_upload_id": client_upload_id,
        "file_name": "analitica.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1024000,
        "sha256": sha,
        "test_type": "blood_test",
        "title": "Analítica para acceso",
        "test_date": "2026-09-28",
        "notes": "test acceso",
    }, headers=headers_p)
    assert r.status_code == 201
    upload_id, ct_id = r.json()["upload_id"], r.json()["clinical_test_id"]
    r = client.post(f"/clinical-tests/uploads/{upload_id}/complete", json={
        "client_upload_id": client_upload_id, "sha256": sha, "size_bytes": 1024000,
    }, headers=headers_p)
    assert r.status_code == 200
    r = None
    for _ in range(40):  # espera a que termine la extracción (409 EXTRACTION_NOT_READY mientras tanto)
        time.sleep(0.5)
        r = client.get(f"/clinical-tests/{ct_id}/extraction", headers=headers_p)
        if r.status_code != 409:
            break
    assert r.status_code == 200
    r = client.patch(f"/clinical-tests/{ct_id}/extraction", json={
        "action": "confirm", "extraction_id": r.json()["extraction_id"], "marker_edits": [],
    }, headers={"Authorization": headers_p["Authorization"], "Idempotency-Key": f"idemp_{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200
    return ct_id


def test_clinician_without_relationship_gets_403_everywhere_and_is_audited(scenario, mongo_test_db):
    """§13.8: un clínico sin relación asistencial recibe 403 en el reporte, la serie, el puntaje y la
    exportación, y el intento queda registrado en auditoría."""
    pid, headers_p = scenario["patient_id"], scenario["headers_p"]
    stranger = scenario["stranger"]

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        ct = _upload_and_confirm(client, headers_p)
        h = _clinician_headers(stranger)
        h_export = _clinician_headers(stranger, {"Idempotency-Key": f"exp_{uuid.uuid4().hex[:10]}"})

        requests = [
            ("GET", f"/patients/{pid}/lab-score", h, None),
            ("GET", f"/patients/{pid}/markers?marker_codes=hemoglobin", h, None),
            ("GET", f"/patients/{pid}/lab-report", h, None),
            ("POST", f"/patients/{pid}/lab-report/export", h_export, {}),
            ("GET", f"/patients/{pid}/clinical-tests", h, None),
            ("GET", f"/clinical-tests/{ct}", h, None),
            ("GET", f"/clinical-tests/{ct}/extraction", h, None),
        ]
        for method, url, headers, body in requests:
            r = client.request(method, url, headers=headers, json=body)
            assert r.status_code == 403, f"{method} {url} => {r.status_code} {r.text}"
            assert r.json()["detail"]["code"] == "NO_PATIENT_ACCESS", f"{method} {url}: {r.text}"

    # Auditoría: cada recurso protegido registró el intento denegado
    denied = list(mongo_test_db.audit_events.find(
        {"event": "access_denied", "patient_id": pid, "actor_id": stranger, "reason": "no_clinical_relationship"}
    ))
    resources = {e["resource"] for e in denied}
    assert {"lab-score", "markers", "lab-report"} <= resources


def test_clinicians_with_relationship_have_access(scenario):
    """Tanto el clínico en authorised_clinicians como el care_clinician_id acceden."""
    pid, headers_p = scenario["patient_id"], scenario["headers_p"]

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        _upload_and_confirm(client, headers_p)
        for clinician in (scenario["listed"], scenario["caregiver"]):
            h = _clinician_headers(clinician)
            assert client.get(f"/patients/{pid}/lab-score", headers=h).status_code == 200
            assert client.get(f"/patients/{pid}/lab-report", headers=h).status_code == 200
            assert client.get(f"/patients/{pid}/markers?marker_codes=hemoglobin", headers=h).status_code == 200