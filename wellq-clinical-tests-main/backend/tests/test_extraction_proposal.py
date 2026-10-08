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
SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


@pytest.fixture
def ctx(grant_access):
    patient_id = f"P_SCORE_{uuid.uuid4().hex[:6]}"
    clinician_id = f"DOC_SCORE_{uuid.uuid4().hex[:6]}"
    grant_access(patient_id, clinician_id)
    token_p = jwt.encode({"sub": f"usr_{patient_id}", "role": "patient", "patient_id": patient_id},
                         SECRET, algorithm=ALGORITHM)
    token_c = jwt.encode({"sub": f"usr_{clinician_id}", "role": "clinician", "clinician_id": clinician_id},
                         SECRET, algorithm=ALGORITHM)
    return {"patient_id": patient_id, "token_p": token_p, "token_c": token_c}


def _hp(ctx):
    return {"Authorization": f"Bearer {ctx['token_p']}", "Idempotency-Key": f"k_{uuid.uuid4().hex[:10]}"}


def _hc(ctx):
    return {"Authorization": f"Bearer {ctx['token_c']}"}


def _upload(client, ctx, title):
    client_upload_id = f"upl_prp_{uuid.uuid4().hex[:8]}"
    r = client.post("/clinical-tests/uploads/initiate", json={
        "client_upload_id": client_upload_id, "file_name": "documento.pdf", "mime_type": "application/pdf",
        "size_bytes": 1024000, "sha256": SHA, "test_type": "blood_test",
        "title": title, "test_date": "2026-09-28", "notes": "test",
    }, headers=_hp(ctx))
    assert r.status_code == 201
    upload_id, ct = r.json()["upload_id"], r.json()["clinical_test_id"]
    r = client.post(f"/clinical-tests/uploads/{upload_id}/complete",
                    json={"client_upload_id": client_upload_id, "sha256": SHA, "size_bytes": 1024000},
                    headers=_hp(ctx))
    assert r.status_code == 200
    return ct


def _wait(client, ctx, ct):
    r = None
    for _ in range(40):
        time.sleep(0.5)
        r = client.get(f"/clinical-tests/{ct}/extraction", headers=_hp(ctx))
        if r.status_code != 409:
            break
    assert r.status_code == 200, r.text
    return r.json()


def _marker(panels, code):
    return next(m for p in panels for m in p["markers"] if m["marker_code"] == code)


# ============ §7.3: bloque proposal inmutable ============

def test_proposal_block_is_immutable(ctx, mongo_test_db):
    with httpx.Client(base_url=BASE_URL, timeout=40) as client:
        ct = _upload(client, ctx, "Analítica proposal")
        ext = _wait(client, ctx, ct)
        extraction_id = ext["extraction_id"]

        stored = mongo_test_db.clinical_test_extractions.find_one({"extraction_id": extraction_id})
        assert "proposal" in stored
        original = _marker(stored["proposal"]["panels"], "hemoglobin")["value_canonical"]
        assert original == pytest.approx(14.2)

        # El paciente edita la hemoglobina y confirma
        r = client.patch(f"/clinical-tests/{ct}/extraction", json={
            "action": "confirm", "extraction_id": extraction_id,
            "marker_edits": [{"op": "update", "marker_code": "hemoglobin", "value_raw": "13.5", "unit_raw": "g/dL"}],
        }, headers=_hp(ctx))
        assert r.status_code == 200

        # El clínico la corrige otra vez
        r = client.post(f"/clinical-tests/{ct}/extraction/validate", json={
            "validation_status": "validated",
            "marker_corrections": [{"marker_code": "hemoglobin", "value_raw": "13.0", "unit_raw": "g/dL"}],
        }, headers=_hc(ctx))
        assert r.status_code == 200

        stored = mongo_test_db.clinical_test_extractions.find_one({"extraction_id": extraction_id})
        # proposal: exactamente lo que devolvió el modelo
        assert _marker(stored["proposal"]["panels"], "hemoglobin")["value_canonical"] == pytest.approx(14.2)
        assert _marker(stored["proposal"]["panels"], "hemoglobin")["edited"] is False
        # confirmed: resultado de la edición del paciente
        assert _marker(stored["confirmed"]["panels"], "hemoglobin")["value_canonical"] == pytest.approx(13.5)
        assert stored["confirmed"]["confirmed_by"] == ctx["patient_id"]
        # panels: valor vigente tras la corrección del clínico
        assert _marker(stored["panels"], "hemoglobin")["value_canonical"] == pytest.approx(13.0)
        assert _marker(stored["panels"], "hemoglobin")["edited_by"] == "clinician"


def test_reprocess_creates_a_new_proposal_and_keeps_the_old_one(ctx, mongo_test_db):
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        ct = _upload(client, ctx, "Analítica reproceso proposal")
        ext = _wait(client, ctx, ct)
        r = client.patch(f"/clinical-tests/{ct}/extraction",
                         json={"action": "discard", "extraction_id": ext["extraction_id"]}, headers=_hp(ctx))
        assert r.status_code == 200
        r = client.post(f"/clinical-tests/{ct}/extraction/reprocess", json={}, headers=_hp(ctx))
        assert r.status_code == 200
        new_id = r.json()["extraction_id"]

        old = mongo_test_db.clinical_test_extractions.find_one({"extraction_id": ext["extraction_id"]})
        new = mongo_test_db.clinical_test_extractions.find_one({"extraction_id": new_id})
        assert old["superseded_at"] is not None and "proposal" in old
        assert new["superseded_at"] is None and "proposal" in new


# ============ §3.3.2 / §13.8: carta clínica => not_applicable ============

def test_clinical_letter_is_not_applicable_but_downloadable(ctx, mongo_test_db):
    with httpx.Client(base_url=BASE_URL, timeout=40) as client:
        ct = _upload(client, ctx, "Carta clínica de seguimiento")
        ext = _wait(client, ctx, ct)

        assert ext["status"] == "not_applicable"
        assert ext["panels"] == []
        assert any(f["code"] == "not_applicable" for f in ext["flags"])
        assert ext["document"]["description"]

        # Paciente y clínico ven el estado (tabla 8)
        r = client.get(f"/clinical-tests/{ct}/extraction", headers=_hc(ctx))
        assert r.status_code == 200
        assert r.json()["status"] == "not_applicable"

        # Se almacena y es descargable por paciente y clínico
        r = client.post(f"/clinical-tests/{ct}/download-url", headers=_hp(ctx))
        assert r.status_code == 200 and r.json()["url"]
        r = client.post(f"/clinical-tests/{ct}/download-url", headers=_hc(ctx))
        assert r.status_code == 200 and r.json()["url"]

        # No genera marcadores ni puntaje
        assert mongo_test_db.clinical_markers.count_documents({"patient_id": ctx["patient_id"]}) == 0
        r = client.get(f"/patients/{ctx['patient_id']}/lab-score", headers=_hc(ctx))
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "NO_SCORE_AVAILABLE"

        # No se puede confirmar ni validar
        r = client.patch(f"/clinical-tests/{ct}/extraction", json={
            "action": "confirm", "extraction_id": ext["extraction_id"], "marker_edits": [],
        }, headers=_hp(ctx))
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "INVALID_EXTRACTION_STATE"
        r = client.post(f"/clinical-tests/{ct}/extraction/validate",
                        json={"validation_status": "validated"}, headers=_hc(ctx))
        assert r.status_code == 409