import jwt
import uuid
import time
import httpx
import pytest

BASE_URL = "http://localhost:8000/api/v1"
SECRET = "your-secret-key-here"
ALGORITHM = "HS256"

@pytest.fixture
def test_users():
    patient_id = f"P_EXT_{uuid.uuid4().hex[:6]}"
    clinician_id = f"DOC_EXT_{uuid.uuid4().hex[:6]}"

    token_p = jwt.encode(
        {"sub": f"usr_{patient_id}", "role": "patient", "patient_id": patient_id},
        SECRET,
        algorithm=ALGORITHM
    )
    token_c = jwt.encode(
        {"sub": f"usr_{clinician_id}", "role": "clinician", "clinician_id": clinician_id},
        SECRET,
        algorithm=ALGORITHM
    )

    return {
        "headers_patient": {
            "Authorization": f"Bearer {token_p}",
            "Idempotency-Key": f"idem_{uuid.uuid4().hex[:8]}"
        },
        "headers_clinician": {
            "Authorization": f"Bearer {token_c}"
        },
        "patient_id": patient_id,
        "clinician_id": clinician_id,
    }

def test_complete_extraction_and_confirmation_flow(test_users):
    headers_p = test_users["headers_patient"]
    headers_c = test_users["headers_clinician"]
    patient_id = test_users["patient_id"]

    client_upload_id = f"upl_ext_{uuid.uuid4().hex[:8]}"
    sha256_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    with httpx.Client(base_url=BASE_URL, timeout=12) as client:
        # ============ 1. TEST ENDPOINT #16: GET /marker-catalog ============
        r_cat = client.get("/marker-catalog", headers=headers_p)
        assert r_cat.status_code == 200
        catalog = r_cat.json()
        assert len(catalog) >= 5
        catalog_codes = [c["marker_code"] for c in catalog]
        assert "cholesterol_total" in catalog_codes
        assert "glucose" in catalog_codes

        # ============ 2. SUBIDA INICIAL (Componente A) ============
        init_payload = {
            "client_upload_id": client_upload_id,
            "file_name": "perfil_lipidico_anual.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024000,
            "sha256": sha256_hash,
            "test_type": "blood_test",
            "title": "Perfil Lipídico Laboratorio",
            "test_date": "2026-09-25",
            "notes": "Muestra en ayunas"
        }
        r_init = client.post("/clinical-tests/uploads/initiate", json=init_payload, headers=headers_p)
        assert r_init.status_code == 201
        upload_id = r_init.json()["upload_id"]
        clinical_test_id = r_init.json()["clinical_test_id"]

        # Completar subida -> dispara escaneo y extracción automática (Componente B)
        r_comp = client.post(
            f"/clinical-tests/uploads/{upload_id}/complete",
            json={"client_upload_id": client_upload_id, "sha256": sha256_hash, "size_bytes": 1024000},
            headers=headers_p
        )
        assert r_comp.status_code == 200

        # Esperar 3 segundos para que la tarea en segundo plano finalice escaneo y extracción
        time.sleep(3)

        # ============ 3. TEST ENDPOINT #12: GET /extraction ============
        r_ext = client.get(f"/clinical-tests/{clinical_test_id}/extraction", headers=headers_p)
        assert r_ext.status_code == 200
        ext_data = r_ext.json()
        assert ext_data["clinical_test_id"] == clinical_test_id
        extraction_id = ext_data["extraction_id"]
        assert ext_data["status"] == "awaiting_confirmation"
        assert len(ext_data["panels"]) >= 1
        markers = ext_data["panels"][0]["markers"]
        assert len(markers) >= 3
        # Verificar que trajo confianzas por campo
        assert "confidence" in markers[0]
        assert markers[0]["confidence"]["value"] >= 0.9

        # ============ 4. TEST VALIDACIONES EN ENDPOINT #13 ============
        # A) Extraction ID desalineado -> 409 EXTRACTION_SUPERSEDED
        bad_confirm = {
            "action": "confirm",
            "extraction_id": "cte_fake_outdated_id",
            "marker_edits": []
        }
        r_bad_id = client.patch(
            f"/clinical-tests/{clinical_test_id}/extraction",
            json=bad_confirm,
            headers={"Authorization": headers_p["Authorization"], "Idempotency-Key": "id_1"}
        )
        assert r_bad_id.status_code == 409
        assert r_bad_id.json()["detail"]["code"] == "EXTRACTION_SUPERSEDED"

        # B) Marcador inexistente -> 422 UNKNOWN_MARKER
        bad_marker = {
            "action": "confirm",
            "extraction_id": extraction_id,
            "marker_edits": [
                {"op": "add", "marker_code": "non_existent_marker_xyz", "value_raw": "50", "unit_raw": "mg/dL"}
            ]
        }
        r_bad_m = client.patch(
            f"/clinical-tests/{clinical_test_id}/extraction",
            json=bad_marker,
            headers={"Authorization": headers_p["Authorization"], "Idempotency-Key": "id_2"}
        )
        assert r_bad_m.status_code == 422
        assert r_bad_m.json()["detail"]["code"] == "UNKNOWN_MARKER"

        # C) Unidad no admitida -> 422 UNIT_NOT_SUPPORTED
        bad_unit = {
            "action": "confirm",
            "extraction_id": extraction_id,
            "marker_edits": [
                {"op": "update", "marker_code": "cholesterol_total", "value_raw": "200", "unit_raw": "litros"}
            ]
        }
        r_bad_u = client.patch(
            f"/clinical-tests/{clinical_test_id}/extraction",
            json=bad_unit,
            headers={"Authorization": headers_p["Authorization"], "Idempotency-Key": "id_3"}
        )
        assert r_bad_u.status_code == 422
        assert r_bad_u.json()["detail"]["code"] == "UNIT_NOT_SUPPORTED"

        # ============ 5. TEST ENDPOINT #13: CONFIRMACIÓN EXITOSA POR EL PACIENTE ============
        valid_confirm = {
            "action": "confirm",
            "extraction_id": extraction_id,
            "document_edits": {
                "collection_date": "2026-09-25",
                "document_type": "blood_panel"
            },
            "marker_edits": [
                {"op": "update", "marker_code": "cholesterol_total", "value_raw": "215", "unit_raw": "mg/dL"}
            ]
        }
        r_conf = client.patch(
            f"/clinical-tests/{clinical_test_id}/extraction",
            json=valid_confirm,
            headers={"Authorization": headers_p["Authorization"], "Idempotency-Key": "id_confirm"}
        )
        assert r_conf.status_code == 200
        conf_data = r_conf.json()
        assert conf_data["status"] == "confirmed"
        assert conf_data["confirmation"]["status"] == "confirmed"

        # Verificar que el marcador editado refleja el nuevo valor
        updated_markers = conf_data["panels"][0]["markers"]
        m_chol = next(m for m in updated_markers if m["marker_code"] == "cholesterol_total")
        assert m_chol["value_raw"] == "215.0" or m_chol["value_raw"] == "215"
        assert m_chol["edited"] is True

        # ============ 6. TEST ENDPOINT #15: VALIDACIÓN CLÍNICA (MÉDICO) ============
        clin_val = {
            "validation_status": "validated",
            "marker_corrections": [
                {"marker_code": "ldl_cholesterol", "value_raw": "135", "unit_raw": "mg/dL"}
            ],
            "clinical_note": "Ajuste validado por médico tratante."
        }
        r_val = client.post(
            f"/clinical-tests/{clinical_test_id}/extraction/validate",
            json=clin_val,
            headers=headers_c
        )
        assert r_val.status_code == 200
        val_data = r_val.json()
        assert val_data["status"] == "clinically_validated"
        assert val_data["confirmation"]["status"] == "clinically_validated"

        # ============ 7. TEST ENDPOINT #14: REPROCESAR EXTRACCIÓN ============
        r_reproc = client.post(
            f"/clinical-tests/{clinical_test_id}/extraction/reprocess",
            headers={"Authorization": headers_p["Authorization"], "Idempotency-Key": "id_reproc"}
        )
        assert r_reproc.status_code == 200
        reproc_data = r_reproc.json()
        assert reproc_data["extraction_id"] != extraction_id
        assert reproc_data["status"] == "awaiting_confirmation"
