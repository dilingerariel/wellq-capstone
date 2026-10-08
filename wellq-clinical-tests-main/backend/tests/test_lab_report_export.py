import sys
import os
import uuid
import time
import hashlib
import jwt
import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

BASE_URL = "http://localhost:8000/api/v1"
SECRET = "your-secret-key-here"
ALGORITHM = "HS256"
EXPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "exports"))


@pytest.fixture
def users(grant_access):
    patient_id = f"P_SCORE_{uuid.uuid4().hex[:6]}"
    clinician_id = f"DOC_SCORE_{uuid.uuid4().hex[:6]}"
    token_p = jwt.encode(
        {"sub": f"usr_{patient_id}", "role": "patient", "patient_id": patient_id},
        SECRET, algorithm=ALGORITHM,
    )
    token_c = jwt.encode(
        {"sub": f"usr_{clinician_id}", "role": "clinician", "clinician_id": clinician_id},
        SECRET, algorithm=ALGORITHM,
    )
    grant_access(patient_id, clinician_id)
    return {
        "headers_p": {"Authorization": f"Bearer {token_p}", "Idempotency-Key": f"idem_{uuid.uuid4().hex[:8]}"},
        "token_c": token_c,
        "patient_id": patient_id,
        "clinician_id": clinician_id,
    }


def _hc(users, key=None):
    return {"Authorization": f"Bearer {users['token_c']}", "Idempotency-Key": key or f"exp_{uuid.uuid4().hex[:10]}"}


def _upload_and_confirm(client, headers_p, test_date="2026-09-28"):
    client_upload_id = f"upl_exp_{uuid.uuid4().hex[:8]}"
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    r = client.post("/clinical-tests/uploads/initiate", json={
        "client_upload_id": client_upload_id,
        "file_name": "analitica.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1024000,
        "sha256": sha,
        "test_type": "blood_test",
        "title": "Analítica para exportar",
        "test_date": test_date,
        "notes": "test export",
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


def test_export_lab_report_endpoint_20(users):
    headers_p, patient_id, clinician_id = users["headers_p"], users["patient_id"], users["clinician_id"]
    url = f"/patients/{patient_id}/lab-report/export"

    with httpx.Client(base_url=BASE_URL, timeout=40) as client:
        _upload_and_confirm(client, headers_p, "2026-09-20")
        _upload_and_confirm(client, headers_p, "2026-09-28")

        # 1. Exportación nueva
        key = f"exp_{uuid.uuid4().hex[:10]}"
        r = client.post(url, json={}, headers=_hc(users, key))
        assert r.status_code == 200, r.text
        exp = r.json()
        for field in ("export_id", "patient_id", "status", "file_name", "download_url",
                      "expires_at", "size_bytes", "sha256", "storage", "replayed"):
            assert field in exp
        assert exp["patient_id"] == patient_id
        assert exp["status"] == "ready"
        assert exp["replayed"] is False
        assert exp["size_bytes"] > 0
        assert len(exp["sha256"]) == 64
        assert exp["file_name"].endswith(".pdf")

        # 2. Si el PDF quedó en disco local (modo desarrollo), verificar su contenido
        pdf_path = os.path.join(EXPORTS_DIR, f"{exp['export_id']}.pdf")
        if exp["storage"] == "local" and os.path.exists(pdf_path):
            data = open(pdf_path, "rb").read()
            assert data.startswith(b"%PDF")
            assert hashlib.sha256(data).hexdigest() == exp["sha256"]
            assert len(data) == exp["size_bytes"]
            # pie de página obligatorio (§9.5.4): paciente, clínico, versiones y leyenda
            assert patient_id.encode() in data
            assert clinician_id.encode() in data
            assert b"no constituye un diagnostico" in data

        # 3. Idempotencia: misma clave y mismos parámetros => mismo export, sin regenerar
        r2 = client.post(url, json={}, headers=_hc(users, key))
        assert r2.status_code == 200
        assert r2.json()["export_id"] == exp["export_id"]
        assert r2.json()["replayed"] is True

        # 4. Misma clave con parámetros distintos => 409
        r3 = client.post(url, json={"window_months": 6}, headers=_hc(users, key))
        assert r3.status_code == 409

        # 5. Otra clave => otra exportación
        r4 = client.post(url, json={"include_series": False}, headers=_hc(users))
        assert r4.status_code == 200
        assert r4.json()["export_id"] != exp["export_id"]

        # 6. Control de acceso: el paciente recibe 403
        r5 = client.post(url, json={}, headers=headers_p)
        assert r5.status_code == 403


def test_export_lab_report_validation(users):
    patient_id = users["patient_id"]
    url = f"/patients/{patient_id}/lab-report/export"
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        # Sin Idempotency-Key => 422
        r = client.post(url, json={}, headers={"Authorization": f"Bearer {users['token_c']}"})
        assert r.status_code == 422

        # Examen inexistente => 404 (propagado desde el endpoint 19)
        r = client.post(url, json={"clinical_test_id": "ct_inexistente"}, headers=_hc(users))
        assert r.status_code == 404

        # Ventana inválida => 422
        r = client.post(url, json={"window_months": 0}, headers=_hc(users))
        assert r.status_code == 422