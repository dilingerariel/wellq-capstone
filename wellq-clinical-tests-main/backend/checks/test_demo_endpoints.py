"""Validación de endpoints dummy de vinculación (/demo) y aislamiento multi-tenant."""

from datetime import datetime
from pathlib import Path
import hashlib
import pytest
from app.routes.demo import set_demo_private_key
from app.tenancy import TenantDatabase
from app.config import settings


def test_get_clinics(env):
    client = env["client"]
    res = client.get("/api/v1/demo/clinics")
    assert res.status_code == 200
    clinics = res.json()
    assert len(clinics) >= 2
    clinic_ids = [c["id"] for c in clinics]
    assert "clinica_alemana" in clinic_ids
    assert "clinica_santa_maria" in clinic_ids
    for c in clinics:
        assert len(c["clinicians"]) > 0


def test_demo_mutations_and_login_are_opt_in(env):
    response = env["client"].post("/api/v1/demo/login", json={"role": "clinician"})
    assert response.status_code == 404
    response = env["client"].post("/api/v1/demo/link-patient", json={
        "patient_id": "paciente_ariel_demo", "clinic_id": "clinica_alemana", "clinician_id": "rene_faundez"
    })
    assert response.status_code == 404


def test_link_patient_and_multi_tenant_isolation(env):
    client = env["client"]
    raw_db = env["raw"]
    set_demo_private_key(env["key"])
    env["monkeypatch"].setattr(settings, "DEMO_AUTH_ENABLED", True)

    patient_id = "paciente_ariel_demo"
    clinic_a = "clinica_alemana"
    clinic_b = "clinica_santa_maria"
    doc_a = "rene_faundez"
    doc_b = "clinico_demo_sm"

    # 1. Vincular paciente_ariel_demo a clinica_alemana con rene_faundez
    link_res = client.post(
        "/api/v1/demo/link-patient",
        json={
            "patient_id": patient_id,
            "clinic_id": clinic_a,
            "clinician_id": doc_a,
        },
    )
    assert link_res.status_code == 200
    assert link_res.json()["status"] == "linked"

    # The fixed synthetic patient cannot be linked to a second clinic or doctor.
    denied_link = client.post("/api/v1/demo/link-patient", json={
        "patient_id": patient_id, "clinic_id": clinic_b, "clinician_id": doc_b
    })
    assert denied_link.status_code == 422
    assert raw_db.patient_access.find_one({"client_id": clinic_b, "patient_id": patient_id}) is None

    # Verificar que quedó registrado en patient_access de la base de datos
    record = raw_db.patient_access.find_one(
        {"client_id": clinic_a, "patient_id": patient_id}
    )
    assert record is not None
    assert doc_a in record.get("authorised_clinicians", [])

    # 2. Insertar un examen médico en clinica_alemana para paciente_ariel_demo
    db_a = TenantDatabase(raw_db, clinic_a)
    exam_id = "exam-demo-001"
    db_a.clinical_tests.insert_one(
        {
            "clinical_test_id": exam_id,
            "patient_id": patient_id,
            "title": "Examen sintetico de Ariel",
            "test_date": "2026-11-16",
            "status": "ready_for_review",
            "deleted_at": None,
            "created_at": datetime(2026, 11, 16),
            "updated_at": datetime(2026, 11, 16),
            "file": {
                "original_name": "examen_sangre.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
            "upload": {
                "upload_id": "upload-001",
                "client_upload_id": "cupload-001",
                "status": "initiated",
            },
        }
    )

    # 3. Tokens JWT para Médico A, Médico B y Paciente
    token_doc_a = env["token"](role="clinician", identity=doc_a, tenant=clinic_a)
    token_doc_b = env["token"](role="clinician", identity=doc_b, tenant=clinic_b)
    token_patient = env["token"](role="patient", identity=patient_id, tenant=clinic_a)

    headers_a = {"Authorization": f"Bearer {token_doc_a}"}
    headers_b = {"Authorization": f"Bearer {token_doc_b}"}
    headers_patient = {"Authorization": f"Bearer {token_patient}"}

    # 4. El paciente ve su examen en su clínica
    res_pat = client.get(f"/api/v1/clinical-tests/{exam_id}", headers=headers_patient)
    assert res_pat.status_code == 200
    assert res_pat.json()["clinical_test_id"] == exam_id

    # 5. El medico de Clinica Alemana VE al paciente y su examen
    res_doc_a = client.get(f"/api/v1/clinical-tests/{exam_id}", headers=headers_a)
    assert res_doc_a.status_code == 200, res_doc_a.text
    assert res_doc_a.json()["title"] == "Examen sintetico de Ariel"

    # También puede listar los exámenes del paciente
    list_a = client.get(f"/api/v1/patients/{patient_id}/clinical-tests", headers=headers_a)
    assert list_a.status_code == 200
    assert exam_id in [item["clinical_test_id"] for item in list_a.json()["items"]]

    # 6. AISLAMIENTO MULTI-TENANT:
    # El médico de Clínica Santa María (B) NO VE el examen (404 por aislamiento de tenant)
    res_doc_b = client.get(f"/api/v1/clinical-tests/{exam_id}", headers=headers_b)
    assert res_doc_b.status_code == 404, "El médico de la Clínica B no debe tener visibilidad del examen de la Clínica A"

    # El médico de Clínica Santa María tampoco tiene acceso a la historia clínica del paciente
    list_b = client.get(f"/api/v1/patients/{patient_id}/clinical-tests", headers=headers_b)
    assert list_b.status_code == 403, "Debe devolver 403 NO_PATIENT_ACCESS al intentar consultar un paciente no vinculado"


def test_demo_login_endpoint(env):
    client = env["client"]
    set_demo_private_key(env["key"])
    env["monkeypatch"].setattr(settings, "DEMO_AUTH_ENABLED", True)

    # 1. Login como clínico
    res_clinician = client.post(
        "/api/v1/demo/login",
        json={
            "role": "clinician",
            "client_id": "clinica_alemana",
            "clinician_id": "rene_faundez",
        },
    )
    assert res_clinician.status_code == 200
    data_c = res_clinician.json()
    assert "accessToken" in data_c
    assert data_c["role"] == "clinician"
    assert data_c["tenantId"] == "clinica_alemana"
    assert data_c["resourceId"] == "rene_faundez"

    # 2. Login como paciente
    res_patient = client.post(
        "/api/v1/demo/login",
        json={
            "role": "patient",
            "client_id": "clinica_alemana",
            "patient_id": "paciente_ariel_demo",
        },
    )
    assert res_patient.status_code == 200
    data_p = res_patient.json()
    assert "accessToken" in data_p
    assert data_p["role"] == "patient"
    assert data_p["tenantId"] == "clinica_alemana"
    assert data_p["resourceId"] == "paciente_ariel_demo"

    # Verificar que el token del paciente es aceptado por el listado de exámenes
    auth_header = {"Authorization": f"Bearer {data_p['accessToken']}"}
    denied_patient_tenant = client.post("/api/v1/demo/login", json={
        "role": "patient", "client_id": "clinica_santa_maria", "patient_id": "paciente_ariel_demo"
    })
    assert denied_patient_tenant.status_code == 422

    patient_exams = client.get("/api/v1/clinical-tests", headers=auth_header)
    assert patient_exams.status_code == 200


def test_synthetic_mobile_upload_is_saved_and_downloadable_by_authorized_clinician(env):
    """Exercise the exact sample PDF path without GCS, ClamAV, or live services."""
    client, raw = env["client"], env["raw"]
    env["monkeypatch"].setattr(settings, "DEMO_AUTH_ENABLED", True)
    env["monkeypatch"].setattr(settings, "DEMO_MONGO_STORAGE_ENABLED", True)
    set_demo_private_key(env["key"])
    pdf = (Path(__file__).resolve().parents[2] / "mobile" / "assets" / "synthetic.pdf").read_bytes()
    digest = hashlib.sha256(pdf).hexdigest()
    assert digest == "3331e1f6f50397609563dacbdf46d5c6f41d3d530c9f8e3697d136915c4907a6"

    patient_login = client.post("/api/v1/demo/login", json={
        "role": "patient", "client_id": "clinica_alemana", "patient_id": "paciente_ariel_demo"
    })
    assert patient_login.status_code == 200
    patient_headers = {"Authorization": f"Bearer {patient_login.json()['accessToken']}"}
    link = client.post("/api/v1/demo/link-patient", json={
        "patient_id": "paciente_ariel_demo", "clinic_id": "clinica_alemana", "clinician_id": "rene_faundez"
    })
    assert link.status_code == 200

    initiation = client.post("/api/v1/clinical-tests/uploads/initiate", headers={
        **patient_headers, "Idempotency-Key": "synthetic-upload-001"
    }, json={
        "client_upload_id": "synthetic-client-upload-001", "file_name": "synthetic.pdf",
        "mime_type": "application/pdf", "size_bytes": len(pdf), "sha256": digest,
        "test_type": "blood_test", "title": "Examen sintético de Ariel",
        "test_date": "2026-11-17", "ai_consent": False,
    })
    assert initiation.status_code == 201, initiation.text
    descriptor = initiation.json()["upload"]
    uploaded = client.put(descriptor["signed_url"], content=pdf, headers=descriptor["required_headers"])
    assert uploaded.status_code == 204, uploaded.text

    upload_id = initiation.json()["upload_id"]
    completed = client.post(f"/api/v1/clinical-tests/uploads/{upload_id}/complete", headers={
        **patient_headers, "Idempotency-Key": "synthetic-upload-complete-001"
    }, json={"client_upload_id": "synthetic-client-upload-001", "sha256": digest, "size_bytes": len(pdf)})
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "ready_for_review"
    assert completed.json()["local_file_can_be_deleted"] is False
    status_check = client.get(f"/api/v1/clinical-tests/uploads/{upload_id}/status", headers=patient_headers)
    assert status_check.status_code == 200
    assert status_check.json()["processing"] == {"malware_scan": "not_applicable", "mime_validation": "passed"}
    assert status_check.json()["local_file_can_be_deleted"] is True

    clinician_login = client.post("/api/v1/demo/login", json={
        "role": "clinician", "client_id": "clinica_alemana", "clinician_id": "rene_faundez"
    })
    clinician_headers = {"Authorization": f"Bearer {clinician_login.json()['accessToken']}"}
    exam_id = initiation.json()["clinical_test_id"]
    listed = client.get("/api/v1/patients/paciente_ariel_demo/clinical-tests", headers=clinician_headers)
    assert listed.status_code == 200
    assert exam_id in [item["clinical_test_id"] for item in listed.json()["items"]]
    download = client.post(f"/api/v1/clinical-tests/{exam_id}/download-url", headers=clinician_headers, json={})
    assert download.status_code == 200, download.text
    pdf_response = client.get(download.json()["url"])
    assert pdf_response.status_code == 200
    assert pdf_response.content == pdf

    clinic_b_login = client.post("/api/v1/demo/login", json={
        "role": "clinician", "client_id": "clinica_santa_maria", "clinician_id": "clinico_demo_sm"
    })
    clinic_b_headers = {"Authorization": f"Bearer {clinic_b_login.json()['accessToken']}"}
    assert client.get(f"/api/v1/clinical-tests/{exam_id}", headers=clinic_b_headers).status_code == 404
    assert client.get("/api/v1/patients/paciente_ariel_demo/clinical-tests", headers=clinic_b_headers).status_code == 403
