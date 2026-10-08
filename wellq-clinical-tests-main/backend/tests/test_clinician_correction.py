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
        "headers_c": {"Authorization": f"Bearer {token_c}"},
        "patient_id": patient_id,
    }


def _upload_and_confirm(client, headers_p, test_date="2026-09-28"):
    client_upload_id = f"upl_cor_{uuid.uuid4().hex[:8]}"
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    r = client.post("/clinical-tests/uploads/initiate", json={
        "client_upload_id": client_upload_id,
        "file_name": "analitica.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1024000,
        "sha256": sha,
        "test_type": "blood_test",
        "title": "Analítica para corrección",
        "test_date": test_date,
        "notes": "test corrección",
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


def test_clinician_correction_reaches_series_and_report(users):
    """La corrección clínica de un marcador EXISTENTE debe reemplazar el valor vigente (sin duplicados)
    en la serie (#17) y en el reporte (#19), y generar un snapshot con trigger clinician_correction."""
    headers_p, headers_c, patient_id = users["headers_p"], users["headers_c"], users["patient_id"]

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        ct = _upload_and_confirm(client, headers_p)

        # Valor original confirmado por el paciente
        r = client.get(f"/patients/{patient_id}/markers?marker_codes=hemoglobin", headers=headers_c)
        assert r.status_code == 200
        before = r.json()["series"][0]["points"]
        assert len(before) == 1
        original_value = before[0]["value"]
        corrected_value = 13.0
        assert original_value != corrected_value

        # Corrección clínica
        r = client.post(f"/clinical-tests/{ct}/extraction/validate", json={
            "validation_status": "validated",
            "marker_corrections": [{
                "marker_code": "hemoglobin", "value_raw": "13.0", "unit_raw": "g/dL",
                "reason": "transcription_error",
            }],
            "clinical_note": "Corrección verificada con el laboratorio.",
        }, headers=headers_c)
        assert r.status_code == 200

        # Serie: un solo punto vigente, con el valor corregido (el anterior queda invalidado)
        r = client.get(f"/patients/{patient_id}/markers?marker_codes=hemoglobin", headers=headers_c)
        assert r.status_code == 200
        after = r.json()["series"][0]["points"]
        assert len(after) == 1, f"se esperaba 1 punto vigente y hay {len(after)}: {after}"
        assert after[0]["value"] == corrected_value

        # Reporte: la fila del examen muestra el valor corregido
        r = client.get(f"/patients/{patient_id}/lab-report?clinical_test_id={ct}", headers=headers_c)
        assert r.status_code == 200
        rows = [row for p in r.json()["results"]["panels"] for row in p["rows"] if row["marker_code"] == "hemoglobin"]
        assert len(rows) == 1
        assert rows[0]["value"] == corrected_value

        # El puntaje se recalculó por la corrección
        r = client.get(f"/patients/{patient_id}/lab-score", headers=headers_c)
        assert r.status_code == 200
        assert r.json()["current_snapshot"]["trigger"] == "clinician_correction"