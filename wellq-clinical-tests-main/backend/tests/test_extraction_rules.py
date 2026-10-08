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


def _hp(ctx, key=None):
    return {"Authorization": f"Bearer {ctx['token_p']}", "Idempotency-Key": key or f"k_{uuid.uuid4().hex[:10]}"}


def _hc(ctx):
    return {"Authorization": f"Bearer {ctx['token_c']}"}


def _start_upload(client, ctx):
    """Sube y completa un examen. Devuelve (clinical_test_id, respuesta_de_complete)."""
    client_upload_id = f"upl_rul_{uuid.uuid4().hex[:8]}"
    r = client.post("/clinical-tests/uploads/initiate", json={
        "client_upload_id": client_upload_id, "file_name": "analitica.pdf", "mime_type": "application/pdf",
        "size_bytes": 1024000, "sha256": SHA, "test_type": "blood_test",
        "title": "Analítica reglas", "test_date": "2026-09-28", "notes": "test reglas",
    }, headers=_hp(ctx))
    assert r.status_code == 201
    upload_id, ct = r.json()["upload_id"], r.json()["clinical_test_id"]
    r = client.post(f"/clinical-tests/uploads/{upload_id}/complete", json={
        "client_upload_id": client_upload_id, "sha256": SHA, "size_bytes": 1024000,
    }, headers=_hp(ctx))
    assert r.status_code == 200
    return ct


def _wait_extraction(client, ctx, ct):
    r = None
    for _ in range(40):
        time.sleep(0.5)
        r = client.get(f"/clinical-tests/{ct}/extraction", headers=_hp(ctx))
        if r.status_code != 409:
            break
    assert r.status_code == 200, r.text
    return r.json()


def _ready_exam(client, ctx):
    ct = _start_upload(client, ctx)
    return ct, _wait_extraction(client, ctx, ct)


def _patch(client, ctx, ct, body, key=None):
    return client.patch(f"/clinical-tests/{ct}/extraction", json=body, headers=_hp(ctx, key))


def _reprocess(client, ctx, ct, body=None, key=None):
    return client.post(f"/clinical-tests/{ct}/extraction/reprocess", json=body or {}, headers=_hp(ctx, key))


# ============ ENDPOINT 12 (§7.4.1) ============

def test_get_extraction_rules(ctx):
    with httpx.Client(base_url=BASE_URL, timeout=40) as client:
        ct = _start_upload(client, ctx)

        # En cola / procesando: 409 EXTRACTION_NOT_READY (el GET ya no lanza el extractor)
        r = client.get(f"/clinical-tests/{ct}/extraction", headers=_hp(ctx))
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "EXTRACTION_NOT_READY"

        ext = _wait_extraction(client, ctx, ct)
        assert ext["status"] == "awaiting_confirmation"

        # El clínico solo ve extracciones confirmed / clinically_validated
        r = client.get(f"/clinical-tests/{ct}/extraction", headers=_hc(ctx))
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "EXTRACTION_NOT_READY"

        # Tras la confirmación del paciente (con una edición), el clínico la ve con el indicador de edición
        r = _patch(client, ctx, ct, {
            "action": "confirm", "extraction_id": ext["extraction_id"],
            "marker_edits": [{"op": "update", "marker_code": "hemoglobin", "value_raw": "13.5", "unit_raw": "g/dL"}],
        })
        assert r.status_code == 200
        r = client.get(f"/clinical-tests/{ct}/extraction", headers=_hc(ctx))
        assert r.status_code == 200
        hemo = next(m for p in r.json()["panels"] for m in p["markers"] if m["marker_code"] == "hemoglobin")
        assert hemo["edited"] is True
        assert hemo["edited_by"] == "patient"


# ============ ENDPOINT 13 (§7.4.2) ============

def test_confirm_rules_state_idempotency_and_summary(ctx):
    with httpx.Client(base_url=BASE_URL, timeout=40) as client:
        ct, ext = _ready_exam(client, ctx)
        body = {
            "action": "confirm", "extraction_id": ext["extraction_id"],
            "marker_edits": [{"op": "update", "marker_code": "hemoglobin", "value_raw": "13.5", "unit_raw": "g/dL"}],
        }
        key = f"confirm_{uuid.uuid4().hex[:8]}"

        r1 = _patch(client, ctx, ct, body, key)
        assert r1.status_code == 200
        conf = r1.json()["confirmation"]
        # §7.4.2: resumen de ediciones aplicadas e identificador del score_snapshot
        assert conf["edits_applied"] == [{"op": "update", "marker_code": "hemoglobin"}]
        assert conf["score_snapshot_id"]
        assert "idempotency_key" not in conf

        # Reintento con la misma Idempotency-Key: mismo resultado, sin error de estado
        r2 = _patch(client, ctx, ct, body, key)
        assert r2.status_code == 200
        assert r2.json()["extraction_id"] == r1.json()["extraction_id"]
        assert r2.json()["confirmation"]["score_snapshot_id"] == conf["score_snapshot_id"]

        # Otra clave: ya no está en awaiting_confirmation => 409
        r3 = _patch(client, ctx, ct, body, f"otra_{uuid.uuid4().hex[:8]}")
        assert r3.status_code == 409
        assert r3.json()["detail"]["code"] == "INVALID_EXTRACTION_STATE"

        # Solo hubo un snapshot (el reintento no recalculó)
        r = client.get(f"/patients/{ctx['patient_id']}/lab-score?history=true", headers=_hc(ctx))
        assert r.status_code == 200
        assert not r.json()["history"]


def test_value_implausible_is_rejected(ctx):
    """§7.4.2: un valor fuera del intervalo de plausibilidad devuelve 422 VALUE_IMPLAUSIBLE."""
    with httpx.Client(base_url=BASE_URL, timeout=40) as client:
        ct, ext = _ready_exam(client, ctx)
        r = _patch(client, ctx, ct, {
            "action": "confirm", "extraction_id": ext["extraction_id"],
            "marker_edits": [{"op": "update", "marker_code": "hemoglobin", "value_raw": "9999", "unit_raw": "g/dL"}],
        })
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "VALUE_IMPLAUSIBLE"


# ============ ENDPOINT 14 (§7.4.3) ============

def test_reprocess_rules(ctx):
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        ct, ext = _ready_exam(client, ctx)

        # Desde awaiting_confirmation no se permite
        r = _reprocess(client, ctx, ct)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "REPROCESS_NOT_ALLOWED"

        # Desde discarded sí
        r = _patch(client, ctx, ct, {"action": "discard", "extraction_id": ext["extraction_id"]})
        assert r.status_code == 200
        key = f"rp_{uuid.uuid4().hex[:8]}"
        r = _reprocess(client, ctx, ct, key=key)
        assert r.status_code == 200, r.text
        new_id = r.json()["extraction_id"]
        assert new_id != ext["extraction_id"]

        # Idempotente: misma clave => misma extracción (no reprocesa otra vez)
        r = _reprocess(client, ctx, ct, key=key)
        assert r.status_code == 200
        assert r.json()["extraction_id"] == new_id

        # Desde confirmed: exige confirmación explícita
        r = _patch(client, ctx, ct, {"action": "confirm", "extraction_id": new_id, "marker_edits": []})
        assert r.status_code == 200
        r = _reprocess(client, ctx, ct)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "CONFIRMATION_REQUIRED"

        r = _reprocess(client, ctx, ct, {"confirm_reprocess_confirmed": True})
        assert r.status_code == 200, r.text
        assert r.json()["extraction_id"] != new_id

        # La extracción anterior se archivó y sus marcadores dejaron de ser vigentes
        r = client.get(f"/patients/{ctx['patient_id']}/markers?marker_codes=hemoglobin", headers=_hc(ctx))
        assert r.status_code == 200
        assert r.json()["series"][0]["points"] == []


def test_reprocess_limit_per_exam(ctx):
    """§7.4.3 (propuesto): máximo 5 reprocesamientos por examen => 429."""
    with httpx.Client(base_url=BASE_URL, timeout=120) as client:
        ct, ext = _ready_exam(client, ctx)
        current = ext["extraction_id"]

        for n in range(5):
            r = _patch(client, ctx, ct, {"action": "discard", "extraction_id": current})
            assert r.status_code == 200, f"descarte {n + 1}: {r.text}"
            r = _reprocess(client, ctx, ct)
            assert r.status_code == 200, f"reproceso {n + 1}: {r.text}"
            current = r.json()["extraction_id"]

        r = _patch(client, ctx, ct, {"action": "discard", "extraction_id": current})
        assert r.status_code == 200
        r = _reprocess(client, ctx, ct)
        assert r.status_code == 429
        assert r.json()["detail"]["code"] == "RATE_LIMITED"