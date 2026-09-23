import jwt
import uuid
import time
import httpx
import pytest

BASE_URL = "http://localhost:8000/api/v1"
SECRET = "your-secret-key-here"
ALGORITHM = "HS256"

@pytest.fixture
def patient_headers():
    token = jwt.encode(
        {"sub": "usr_patient_test", "role": "patient", "patient_id": "P-1001"},
        SECRET,
        algorithm=ALGORITHM
    )
    return {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"idem_{uuid.uuid4().hex[:8]}"
    }

def test_full_upload_flow(patient_headers):
    client_upload_id = f"upl_{uuid.uuid4().hex[:8]}"
    sha256_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        # 1. Initiate Upload
        init_payload = {
            "client_upload_id": client_upload_id,
            "file_name": "hemograma_anual.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024000,
            "sha256": sha256_hash,
            "test_type": "blood_test",
            "title": "Hemograma Completo",
            "test_date": "2026-09-20",
            "notes": "Control preventivo"
        }
        r_init = client.post("/clinical-tests/uploads/initiate", json=init_payload, headers=patient_headers)
        assert r_init.status_code == 201
        data_init = r_init.json()
        upload_id = data_init["upload_id"]
        assert data_init["status"] == "initiated"
        assert "signed_url" in data_init["upload"]

        # 2. Idempotencia
        r_idem = client.post("/clinical-tests/uploads/initiate", json=init_payload, headers=patient_headers)
        assert r_idem.status_code == 201
        assert r_idem.json()["upload_id"] == upload_id

        # 3. Refresh URL
        ref_payload = {
            "client_upload_id": client_upload_id,
            "sha256": sha256_hash
        }
        r_ref = client.post(f"/clinical-tests/uploads/{upload_id}/refresh-url", json=ref_payload, headers=patient_headers)
        assert r_ref.status_code == 200
        assert "signed_url" in r_ref.json()["upload"]

        # 4. Complete Upload
        comp_payload = {
            "client_upload_id": client_upload_id,
            "sha256": sha256_hash,
            "size_bytes": 1024000
        }
        r_comp = client.post(f"/clinical-tests/uploads/{upload_id}/complete", json=comp_payload, headers=patient_headers)
        assert r_comp.status_code == 200
        data_comp = r_comp.json()
        assert data_comp["status"] == "processing"
        assert data_comp["local_file_can_be_deleted"] is False

        # 5. Background scan validation (esperar 3 segundos)
        time.sleep(3)

        # 6. Status Polling
        r_stat = client.get(f"/clinical-tests/uploads/{upload_id}/status", headers=patient_headers)
        assert r_stat.status_code == 200
        data_stat = r_stat.json()
        assert data_stat["status"] == "ready_for_review"
        assert data_stat["processing"]["malware_scan"] == "passed"
        assert data_stat["local_file_can_be_deleted"] is True
