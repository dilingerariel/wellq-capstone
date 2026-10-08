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
    """Sube un examen, espera la extracción y lo confirma como paciente. Devuelve clinical_test_id."""
    client_upload_id = f"upl_rep_{uuid.uuid4().hex[:8]}"
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    r = client.post("/clinical-tests/uploads/initiate", json={
        "client_upload_id": client_upload_id,
        "file_name": "analitica.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1024000,
        "sha256": sha,
        "test_type": "blood_test",
        "title": "Analítica para reporte",
        "test_date": test_date,
        "notes": "test reporte",
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


def _all_rows(report):
    return [row for p in report["results"]["panels"] for row in p["rows"]]


def test_lab_report_endpoint_19(users):
    headers_p, headers_c, patient_id = users["headers_p"], users["headers_c"], users["patient_id"]

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        ct1 = _upload_and_confirm(client, headers_p, "2026-09-20")
        ct2 = _upload_and_confirm(client, headers_p, "2026-09-28")

        # 1. Modo "exam": solo los marcadores del documento pedido
        r = client.get(f"/patients/{patient_id}/lab-report?clinical_test_id={ct2}", headers=headers_c)
        assert r.status_code == 200
        rep = r.json()

        for key in ("header", "score", "flags", "results", "longitudinal",
                    "imaging_findings", "traceability", "actions"):
            assert key in rep
        assert rep["header"]["mode"] == "exam"
        assert rep["header"]["exam"]["clinical_test_id"] == ct2
        assert rep["header"]["exam"]["original_document"]["download_url_endpoint"].endswith(f"{ct2}/download-url")

        rows = _all_rows(rep)
        assert len(rows) >= 1
        assert all(row["origin"]["clinical_test_id"] == ct2 for row in rows)
        for key in ("marker_code", "name", "value", "unit", "reference", "status",
                    "delta", "subscore", "origin", "original"):
            assert key in rows[0]
        assert "source" in rows[0]["reference"]

        # 2. Δ anterior: el segundo examen tiene una medición previa del mismo marcador
        with_delta = [row for row in rows if row["delta"] is not None]
        assert len(with_delta) >= 1
        d = with_delta[0]["delta"]
        for key in ("absolute", "percent", "previous_value", "previous_measured_on", "previous_clinical_test_id"):
            assert key in d
        assert d["previous_clinical_test_id"] == ct1

        # 3. Puntaje del snapshot vigente, sin contribuciones por defecto
        assert rep["score"] is not None
        assert rep["score"]["lab_index"] > 0
        assert set(rep["score"]["pillars"]) >= {"cardio", "bone", "muscle", "joint"}
        assert "contributions" not in rep["score"]["pillars"]["cardio"]
        assert rep["longitudinal"] is None

        # 4. Modo "aggregate": un valor por marcador (el más reciente dentro de la ventana)
        r = client.get(f"/patients/{patient_id}/lab-report", headers=headers_c)
        assert r.status_code == 200
        agg = r.json()
        assert agg["header"]["mode"] == "aggregate"
        codes = [row["marker_code"] for row in _all_rows(agg)]
        assert len(codes) == len(set(codes)) and len(codes) >= 1
        assert {e["clinical_test_id"] for e in agg["header"]["exams"]} <= {ct1, ct2}

        # 5. Opciones: contribuciones por pilar y series longitudinales
        r = client.get(
            f"/patients/{patient_id}/lab-report?include_snapshot=true&include_series=true", headers=headers_c
        )
        assert r.status_code == 200
        full = r.json()
        assert len(full["score"]["pillars"]["cardio"]["contributions"]) > 0
        lon = full["longitudinal"]
        assert len(lon["marker_series"]) >= 1
        assert all(len(s["points"]) >= 2 for s in lon["marker_series"])
        assert len(lon["pillar_series"]) >= 2
        assert "scoring_version_changes" in lon

        # 6. Control de acceso: el paciente (incluso el dueño) recibe 403
        r = client.get(f"/patients/{patient_id}/lab-report", headers=headers_p)
        assert r.status_code == 403


def test_lab_report_validation_and_empty(users):
    headers_c, patient_id = users["headers_c"], users["patient_id"]
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        # Examen inexistente => 404
        r = client.get(f"/patients/{patient_id}/lab-report?clinical_test_id=ct_inexistente", headers=headers_c)
        assert r.status_code == 404

        # Ventana fuera de rango => 422
        r = client.get(f"/patients/{patient_id}/lab-report?window_months=0", headers=headers_c)
        assert r.status_code == 422

        # Paciente sin exámenes: 200 con tabla vacía y score nulo (no calcula al vuelo)
        r = client.get(f"/patients/{patient_id}/lab-report", headers=headers_c)
        assert r.status_code == 200
        rep = r.json()
        assert rep["score"] is None
        assert rep["flags"] == []
        assert rep["results"]["panels"] == []