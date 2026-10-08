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
    patient_id = f"P_MARK_{uuid.uuid4().hex[:6]}"
    clinician_id = f"DOC_MARK_{uuid.uuid4().hex[:6]}"
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


def _upload_and_confirm(client, headers_p):
    """Sube un examen, espera la extracción y lo confirma como paciente. Devuelve clinical_test_id."""
    client_upload_id = f"upl_mark_{uuid.uuid4().hex[:8]}"
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    r = client.post("/clinical-tests/uploads/initiate", json={
        "client_upload_id": client_upload_id,
        "file_name": "analitica.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1024000,
        "sha256": sha,
        "test_type": "blood_test",
        "title": "Analítica para serie",
        "test_date": "2026-09-28",
        "notes": "test serie",
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


def test_marker_series_endpoint_17(users):
    headers_p, headers_c, patient_id = users["headers_p"], users["headers_c"], users["patient_id"]

    with httpx.Client(base_url=BASE_URL, timeout=20) as client:
        ct_id = _upload_and_confirm(client, headers_p)

        # 1. Clínico obtiene la serie; el orden de la respuesta respeta el pedido
        r = client.get(f"/patients/{patient_id}/markers?marker_codes=hemoglobin,codigo_inexistente", headers=headers_c)
        assert r.status_code == 200
        data = r.json()
        assert data["patient_id"] == patient_id
        assert data["only_confirmed"] is True
        assert [s["marker_code"] for s in data["series"]] == ["hemoglobin", "codigo_inexistente"]

        hemo = data["series"][0]
        assert len(hemo["points"]) >= 1
        p = hemo["points"][0]
        for key in ("measured_on", "value", "unit", "reference", "status", "subscore", "clinical_test_id"):
            assert key in p
        assert p["clinical_test_id"] == ct_id

        # 2. Un código desconocido devuelve serie vacía, no error
        assert data["series"][1]["points"] == []

        # 3. Filtro por fechas: rango futuro => sin puntos
        r = client.get(f"/patients/{patient_id}/markers?marker_codes=hemoglobin&from=2030-01-01", headers=headers_c)
        assert r.status_code == 200
        assert r.json()["series"][0]["points"] == []

        # 4. Control de acceso: el paciente (incluso el dueño) recibe 403
        r = client.get(f"/patients/{patient_id}/markers?marker_codes=hemoglobin", headers=headers_p)
        assert r.status_code == 403


def test_marker_series_validation(users):
    headers_c, patient_id = users["headers_c"], users["patient_id"]
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        # Más de 20 códigos => 422
        many = ",".join(f"m{i}" for i in range(21))
        r = client.get(f"/patients/{patient_id}/markers?marker_codes={many}", headers=headers_c)
        assert r.status_code == 422

        # Fecha inválida => 422
        r = client.get(f"/patients/{patient_id}/markers?marker_codes=hemoglobin&from=ayer", headers=headers_c)
        assert r.status_code == 422

        # Sin marker_codes => 422
        r = client.get(f"/patients/{patient_id}/markers", headers=headers_c)
        assert r.status_code == 422