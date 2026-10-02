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
def test_users():
    patient_id = f"P_SCORE_{uuid.uuid4().hex[:6]}"
    other_patient_id = f"P_OTHER_{uuid.uuid4().hex[:6]}"
    clinician_id = f"DOC_SCORE_{uuid.uuid4().hex[:6]}"

    token_p = jwt.encode(
        {"sub": f"usr_{patient_id}", "role": "patient", "patient_id": patient_id},
        SECRET,
        algorithm=ALGORITHM
    )
    token_other = jwt.encode(
        {"sub": f"usr_{other_patient_id}", "role": "patient", "patient_id": other_patient_id},
        SECRET,
        algorithm=ALGORITHM
    )
    token_c = jwt.encode(
        {"sub": f"usr_{clinician_id}", "role": "clinician", "clinician_id": clinician_id},
        SECRET,
        algorithm=ALGORITHM
    )

    return {
        "headers_p": {
            "Authorization": f"Bearer {token_p}",
            "Idempotency-Key": f"idem_{uuid.uuid4().hex[:8]}"
        },
        "headers_other": {
            "Authorization": f"Bearer {token_other}"
        },
        "headers_c": {
            "Authorization": f"Bearer {token_c}"
        },
        "patient_id": patient_id,
        "clinician_id": clinician_id,
    }

def test_scoring_mathematical_functions():
    """Validar cálculo de subscores unitario según fórmulas de §8.2"""
    from app.services.scoring import scoring_engine

    # 1. Colesterol Total: lower_better, optimal <= 180, normal <= 200, crit <= 300
    # Caso dentro de óptimo: 170 -> 100.0
    s_opt, f_opt = scoring_engine.calculate_subscore("cholesterol_total", 170.0)
    assert s_opt == 100.0
    assert f_opt is None

    # Caso en el borde normal: 200 -> 70.0
    s_norm, f_norm = scoring_engine.calculate_subscore("cholesterol_total", 200.0)
    assert s_norm == 70.0

    # Caso fuera de rango normal: 212 -> 70 - 70*(212-200)/(300-200) = 70 - 8.4 = 61.6
    s_high, f_high = scoring_engine.calculate_subscore("cholesterol_total", 212.0)
    assert s_high == 61.6

    # Caso crítico: 320 -> 0.0 + bandera crítica
    s_crit, f_crit = scoring_engine.calculate_subscore("cholesterol_total", 320.0)
    assert s_crit == 0.0
    assert f_crit is not None
    assert f_crit.severity.value == "critical"

    # 2. HDL: higher_better, optimal >= 55, normal >= 40, crit low = 25
    # Caso 48 mg/dL: 100 - 30*(55-48)/(55-40) = 100 - 14.0 = 86.0 (ejemplo exacto de la tabla 20)
    s_hdl, _ = scoring_engine.calculate_subscore("hdl_cholesterol", 48.0)
    assert s_hdl == 86.0

def test_full_scoring_flow_and_endpoint_18(test_users):
    """
    Flujo de integración completo:
    1. Carga de examen y extracción automática
    2. Confirmación del paciente -> dispara cálculo de subscores y score_snapshot
    3. Endpoint #18: GET /api/v1/patients/{patient_id}/lab-score
    4. Validación de control de acceso
    5. Validación clínica con corrección médica -> recalcula score_snapshot y consulta con ?history=true
    """
    headers_p = test_users["headers_p"]
    headers_other = test_users["headers_other"]
    headers_c = test_users["headers_c"]
    patient_id = test_users["patient_id"]

    client_upload_id = f"upl_score_{uuid.uuid4().hex[:8]}"
    sha256_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        # 1. Iniciar y completar subida
        init_payload = {
            "client_upload_id": client_upload_id,
            "file_name": "perfil_lipidico_anual.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024000,
            "sha256": sha256_hash,
            "test_type": "blood_test",
            "title": "Analítica Integral de Rutina",
            "test_date": "2026-09-28",
            "notes": "Ayunas completas",
        }
        res_init = client.post("/clinical-tests/uploads/initiate", json=init_payload, headers=headers_p)
        assert res_init.status_code == 201
        data_init = res_init.json()
        upload_id = data_init["upload_id"]
        clinical_test_id = data_init["clinical_test_id"]

        complete_payload = {
            "client_upload_id": client_upload_id,
            "sha256": sha256_hash,
            "size_bytes": 1024000,
        }
        res_comp = client.post(f"/clinical-tests/uploads/{upload_id}/complete", json=complete_payload, headers=headers_p)
        assert res_comp.status_code == 200

        # Esperar 3s a que la extracción en background termine
        time.sleep(3)

        # Obtener extracción propuesta
        res_ext = client.get(f"/clinical-tests/{clinical_test_id}/extraction", headers=headers_p)
        assert res_ext.status_code == 200
        ext_data = res_ext.json()
        extraction_id = ext_data["extraction_id"]

        # 2. Confirmación por el paciente (persiste marcadores y dispara cálculo de score)
        confirm_payload = {
            "action": "confirm",
            "extraction_id": extraction_id,
            "marker_edits": [],
        }
        res_conf = client.patch(
            f"/clinical-tests/{clinical_test_id}/extraction",
            json=confirm_payload,
            headers={"Authorization": headers_p["Authorization"], "Idempotency-Key": f"idemp_{uuid.uuid4().hex[:8]}"}
        )
        assert res_conf.status_code == 200

        # 3. ENDPOINT #18: GET /api/v1/patients/{patient_id}/lab-score (como paciente)
        res_score = client.get(f"/patients/{patient_id}/lab-score", headers=headers_p)
        assert res_score.status_code == 200
        score_data = res_score.json()

        current_snap = score_data["current_snapshot"]
        assert current_snap["patient_id"] == patient_id
        assert current_snap["scoring_version"] == "score-v1.0"
        assert current_snap["lab_index"] is not None
        assert current_snap["lab_index"] > 0
        assert "pillars" in current_snap
        assert "cardio" in current_snap["pillars"]
        assert "bone" in current_snap["pillars"]
        assert "muscle" in current_snap["pillars"]
        assert "joint" in current_snap["pillars"]

        # Verificar explicabilidad: desglose de contribuciones
        cardio = current_snap["pillars"]["cardio"]
        assert cardio["coverage"] > 0
        assert len(cardio["contributions"]) > 0
        first_contrib = cardio["contributions"][0]
        assert "subscore" in first_contrib
        assert first_contrib["subscore"] >= 0

        # 4. Control de acceso: otro paciente no puede acceder
        res_forbidden = client.get(f"/patients/{patient_id}/lab-score", headers=headers_other)
        assert res_forbidden.status_code == 403

        # Clínico accede al puntaje con su relación clínica
        res_doc_score = client.get(f"/patients/{patient_id}/lab-score", headers=headers_c)
        assert res_doc_score.status_code == 200

        # 5. Validación clínica con corrección médica -> genera un segundo snapshot inmutable
        val_payload = {
            "validation_status": "validated",
            "marker_corrections": [
                {
                    "marker_code": "cholesterol_total",
                    "value_raw": "165.0",
                    "unit_raw": "mg/dL",
                    "reason": "transcription_error"
                }
            ],
            "clinical_note": "Ajuste verificado con laboratorio."
        }
        res_val = client.post(
            f"/clinical-tests/{clinical_test_id}/extraction/validate",
            json=val_payload,
            headers=headers_c
        )
        assert res_val.status_code == 200

        # Consultar score con history=true
        res_history = client.get(f"/patients/{patient_id}/lab-score?history=true", headers=headers_c)
        assert res_history.status_code == 200
        hist_data = res_history.json()
        assert hist_data["current_snapshot"]["trigger"] == "clinician_correction"
        assert hist_data["history"] is not None
        assert len(hist_data["history"]) >= 1
