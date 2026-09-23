import jwt
import uuid
import time
import httpx
import pytest

BASE_URL = "http://localhost:8000/api/v1"
SECRET = "your-secret-key-here"
ALGORITHM = "HS256"

@pytest.fixture
def patient_auth():
    patient_id = f"P_{uuid.uuid4().hex[:6]}"
    token = jwt.encode(
        {"sub": f"usr_{patient_id}", "role": "patient", "patient_id": patient_id},
        SECRET,
        algorithm=ALGORITHM
    )
    return {
        "headers": {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"idem_{uuid.uuid4().hex[:8]}"
        },
        "patient_id": patient_id,
    }

@pytest.fixture
def clinician_auth():
    clinician_id = f"DOC_{uuid.uuid4().hex[:6]}"
    token = jwt.encode(
        {"sub": f"usr_{clinician_id}", "role": "clinician", "clinician_id": clinician_id},
        SECRET,
        algorithm=ALGORITHM
    )
    return {
        "headers": {
            "Authorization": f"Bearer {token}"
        },
        "clinician_id": clinician_id,
    }

def test_endpoints_5_to_11_lifecycle(patient_auth, clinician_auth):
    headers_p = patient_auth["headers"]
    patient_id = patient_auth["patient_id"]
    headers_c = clinician_auth["headers"]
    clinician_id = clinician_auth["clinician_id"]

    client_upload_id = f"upl_{uuid.uuid4().hex[:8]}"
    sha256_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        # Pre-requisito: Iniciar y completar examen para que pase a ready_for_review
        init_payload = {
            "client_upload_id": client_upload_id,
            "file_name": "perfil_lipidico.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 500000,
            "sha256": sha256_hash,
            "test_type": "blood_test",
            "title": "Perfil Lipídico Inicial",
            "test_date": "2026-09-20",
            "notes": "En ayunas de 12 horas"
        }
        r_init = client.post("/clinical-tests/uploads/initiate", json=init_payload, headers=headers_p)
        assert r_init.status_code == 201
        upload_id = r_init.json()["upload_id"]
        clinical_test_id = r_init.json()["clinical_test_id"]

        # Completar
        r_comp = client.post(
            f"/clinical-tests/uploads/{upload_id}/complete",
            json={"client_upload_id": client_upload_id, "sha256": sha256_hash, "size_bytes": 500000},
            headers=headers_p
        )
        assert r_comp.status_code == 200

        # Esperar validación
        time.sleep(3)

        # ============ TEST ENDPOINT 5: GET /clinical-tests (Listar paciente) ============
        r_list = client.get("/clinical-tests", headers=headers_p)
        assert r_list.status_code == 200
        list_data = r_list.json()
        assert len(list_data["items"]) >= 1
        found = any(item["clinical_test_id"] == clinical_test_id for item in list_data["items"])
        assert found, "El examen creado debe estar en la lista del paciente"

        # ============ TEST ENDPOINT 6: GET /clinical-tests/{id} (Detalle) ============
        r_detail = client.get(f"/clinical-tests/{clinical_test_id}", headers=headers_p)
        assert r_detail.status_code == 200
        assert r_detail.json()["clinical_test_id"] == clinical_test_id
        assert r_detail.json()["patient_id"] == patient_id
        assert r_detail.json()["title"] == "Perfil Lipídico Inicial"

        # ============ TEST ENDPOINT 7: PATCH /clinical-tests/{id} (Editar metadatos) ============
        edit_payload = {
            "title": "Perfil Lipídico Completo y Corregido",
            "notes": "Actualizado: muestra tomada a las 8:00 AM"
        }
        r_edit = client.patch(f"/clinical-tests/{clinical_test_id}", json=edit_payload, headers=headers_p)
        assert r_edit.status_code == 200
        assert r_edit.json()["title"] == "Perfil Lipídico Completo y Corregido"
        assert r_edit.json()["notes"] == "Actualizado: muestra tomada a las 8:00 AM"

        # ============ TEST ENDPOINT 9: POST /clinical-tests/{id}/download-url ============
        r_down = client.post(f"/clinical-tests/{clinical_test_id}/download-url", headers=headers_p)
        assert r_down.status_code == 200
        assert "url" in r_down.json()
        assert r_down.json()["file_name"] == "perfil_lipidico.pdf"

        # ============ TEST ENDPOINT 10: GET /patients/{id}/clinical-tests (Clínico) ============
        r_clin_list = client.get(f"/patients/{patient_id}/clinical-tests", headers=headers_c)
        assert r_clin_list.status_code == 200
        assert len(r_clin_list.json()["items"]) >= 1

        # ============ TEST ENDPOINT 11: PATCH /clinical-tests/{id}/review (Revisión) ============
        rev_payload = {
            "review_status": "reviewed",
            "review_note": "Valores dentro del rango esperado para el paciente."
        }
        r_rev = client.patch(f"/clinical-tests/{clinical_test_id}/review", json=rev_payload, headers=headers_c)
        assert r_rev.status_code == 200
        rev_data = r_rev.json()
        assert rev_data["review"]["status"] == "reviewed"
        assert rev_data["review"]["reviewed_by"] == clinician_id

        # ============ TEST REGLA CRÍTICA: NO EDITAR METADATOS TRAS REVISIÓN ============
        # Intentar editar de nuevo debe dar 409 ALREADY_REVIEWED
        r_edit_after_review = client.patch(
            f"/clinical-tests/{clinical_test_id}",
            json={"title": "Intento de cambio prohibido"},
            headers=headers_p
        )
        assert r_edit_after_review.status_code == 409
        assert r_edit_after_review.json()["detail"]["code"] == "ALREADY_REVIEWED"

        # ============ TEST ENDPOINT 8: DELETE /clinical-tests/{id} (Soft Delete) ============
        r_del = client.delete(f"/clinical-tests/{clinical_test_id}", headers=headers_p)
        assert r_del.status_code == 200
        assert r_del.json()["status"] == "deleted"

        # Comprobar que tras borrado suave ya no aparece como activo (404)
        r_after_del = client.get(f"/clinical-tests/{clinical_test_id}", headers=headers_p)
        assert r_after_del.status_code == 404
