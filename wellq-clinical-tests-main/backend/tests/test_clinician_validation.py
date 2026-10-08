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
    client_upload_id = f"upl_val_{uuid.uuid4().hex[:8]}"
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    r = client.post("/clinical-tests/uploads/initiate", json={
        "client_upload_id": client_upload_id,
        "file_name": "analitica.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1024000,
        "sha256": sha,
        "test_type": "blood_test",
        "title": "Analítica para validación",
        "test_date": test_date,
        "notes": "test validación",
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


def _validate(client, ct, headers_c, corrections, validation_status="validated"):
    return client.post(f"/clinical-tests/{ct}/extraction/validate", json={
        "validation_status": validation_status,
        "marker_corrections": corrections,
        "clinical_note": "test",
    }, headers=headers_c)


def _hemoglobin_points(client, patient_id, headers_c):
    r = client.get(f"/patients/{patient_id}/markers?marker_codes=hemoglobin", headers=headers_c)
    assert r.status_code == 200
    return r.json()["series"][0]["points"]


GOOD = {"marker_code": "hemoglobin", "value_raw": "13.0", "unit_raw": "g/dL", "reason": "transcription_error"}


def test_invalid_corrections_are_rejected_and_nothing_changes(users):
    """Una corrección inválida => 422 con detalle por marcador y NINGÚN cambio (ni siquiera las válidas)."""
    headers_p, headers_c, patient_id = users["headers_p"], users["headers_c"], users["patient_id"]

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        ct = _upload_and_confirm(client, headers_p)
        original = _hemoglobin_points(client, patient_id, headers_c)[0]["value"]

        # 1. Marcador que no existe en este examen (aunque esté en el catálogo)
        r = _validate(client, ct, headers_c, [
            GOOD, {"marker_code": "cholesterol_total", "value_raw": "165.0", "unit_raw": "mg/dL"},
        ])
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert detail["code"] == "INVALID_MARKER_CORRECTIONS"
        assert [e["marker_code"] for e in detail["errors"]] == ["cholesterol_total"]
        assert detail["errors"][0]["code"] == "MARKER_NOT_IN_EXAM"

        # 2. Código inexistente en todo el sistema
        r = _validate(client, ct, headers_c, [
            {"marker_code": "codigo_inexistente", "value_raw": "1", "unit_raw": "mg/dL"},
        ])
        assert r.status_code == 422

        # 3. Unidad no válida para el marcador
        r = _validate(client, ct, headers_c, [
            {"marker_code": "hemoglobin", "value_raw": "13.0", "unit_raw": "banana"},
        ])
        assert r.status_code == 422
        assert r.json()["detail"]["errors"][0]["marker_code"] == "hemoglobin"

        # 4. Corrección duplicada
        r = _validate(client, ct, headers_c, [GOOD, GOOD])
        assert r.status_code == 422
        assert r.json()["detail"]["errors"][0]["code"] == "DUPLICATE_CORRECTION"

        # 5. validation_status inválido
        r = _validate(client, ct, headers_c, [], validation_status="quizas")
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "INVALID_VALIDATION_STATUS"

        # Nada cambió: mismo valor, examen sigue "confirmed" y aún se puede validar
        assert _hemoglobin_points(client, patient_id, headers_c)[0]["value"] == original
        r = client.get(f"/clinical-tests/{ct}/extraction", headers=headers_p)
        assert r.status_code == 200
        assert r.json()["status"] == "confirmed"

        r = _validate(client, ct, headers_c, [GOOD])
        assert r.status_code == 200
        assert r.json()["status"] == "clinically_validated"


def test_correction_is_reflected_in_extraction_panels(users):
    """La corrección clínica llega a la extracción, con valor original y quién la editó."""
    headers_p, headers_c, patient_id = users["headers_p"], users["headers_c"], users["patient_id"]

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        ct = _upload_and_confirm(client, headers_p)
        original = _hemoglobin_points(client, patient_id, headers_c)[0]["value"]

        r = _validate(client, ct, headers_c, [GOOD])
        assert r.status_code == 200

        def hemo(body):
            return next(m for p in body["panels"] for m in p["markers"] if m["marker_code"] == "hemoglobin")

        m = hemo(r.json())
        assert m["value_canonical"] == 13.0
        assert m["edited"] is True
        assert m["edited_by"] == "clinician"      # §7.3: patient | clinician
        assert m["edited_at"]
        assert m["original_value_canonical"] == original

        # Lo que ve el paciente al leer la extracción es lo mismo
        r = client.get(f"/clinical-tests/{ct}/extraction", headers=headers_p)
        assert r.status_code == 200
        assert hemo(r.json())["value_canonical"] == 13.0

        # Serie del clínico: un único punto vigente con el valor corregido
        points = _hemoglobin_points(client, patient_id, headers_c)
        assert len(points) == 1 and points[0]["value"] == 13.0


def test_clinical_rejection_does_not_fail_and_invalidates_markers(users):
    """El rechazo clínico responde 200 (antes terminaba en 500), invalida los marcadores y no se puede repetir."""
    headers_p, headers_c, patient_id = users["headers_p"], users["headers_c"], users["patient_id"]

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        ct = _upload_and_confirm(client, headers_p)
        assert len(_hemoglobin_points(client, patient_id, headers_c)) == 1

        r = _validate(client, ct, headers_c, [], validation_status="rejected")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "rejected"

        # Los marcadores del examen rechazado ya no están vigentes
        assert _hemoglobin_points(client, patient_id, headers_c) == []

        # El examen ya no está en estado "confirmed": no se puede validar de nuevo
        r = _validate(client, ct, headers_c, [GOOD])
        assert r.status_code == 409


def test_validation_without_corrections_does_not_recompute_score(users):
    """§7.4.4: solo las correcciones del clínico disparan un recálculo; validar sin correcciones no crea snapshot."""
    headers_p, headers_c, patient_id = users["headers_p"], users["headers_c"], users["patient_id"]

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        ct = _upload_and_confirm(client, headers_p)
        before = client.get(f"/patients/{patient_id}/lab-score", headers=headers_c).json()["current_snapshot"]
        assert before["trigger"] == "extraction_confirmed"

        r = _validate(client, ct, headers_c, [])
        assert r.status_code == 200
        assert r.json()["status"] == "clinically_validated"

        after = client.get(f"/patients/{patient_id}/lab-score?history=true", headers=headers_c).json()
        assert after["current_snapshot"]["snapshot_id"] == before["snapshot_id"]
        assert not after["history"]