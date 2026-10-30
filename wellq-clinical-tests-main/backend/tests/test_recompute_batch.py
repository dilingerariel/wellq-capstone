import os
import sys
import uuid
import time
import jwt
import httpx
import pytest
from pymongo import MongoClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from scripts.recompute_scoring import calculate_stats, run_bulk_recompute

BASE_URL = "http://localhost:8000/api/v1"
SECRET = "your-secret-key-here"
ALGORITHM = "HS256"

def test_calculate_stats_math():
    """Validar exactitud matemática de estadísticas descriptivas y percentiles."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    stats = calculate_stats(values)

    assert stats["count"] == 5
    assert stats["mean"] == 30.0
    assert stats["median"] == 30.0
    assert stats["min"] == 10.0
    assert stats["max"] == 50.0
    assert stats["p25"] == 20.0
    assert stats["p75"] == 40.0
    assert stats["std"] > 0

    # Lista vacía
    empty_stats = calculate_stats([])
    assert empty_stats["count"] == 0
    assert empty_stats["mean"] is None

def test_bulk_recompute_dry_run_vs_apply(grant_access, mongo_test_db):
    """
    Prueba completa del procedimiento (§13.5 y §8.8):
    1. Paciente con analítica confirmada y snapshot baseline.
    2. --dry-run: compara estadísticas y NO persiste ningún snapshot nuevo.
    3. --apply: persiste el nuevo snapshot inmutable con trigger='recompute' y preserva el histórico.
    4. Consulta de Endpoint #18 con ?history=true.
    """
    patient_id = f"P_RECOMP_{uuid.uuid4().hex[:6]}"
    clinician_id = f"DOC_RECOMP_{uuid.uuid4().hex[:6]}"

    token_p = jwt.encode(
        {"sub": f"usr_{patient_id}", "role": "patient", "patient_id": patient_id},
        SECRET, algorithm=ALGORITHM
    )
    token_c = jwt.encode(
        {"sub": f"usr_{clinician_id}", "role": "clinician", "clinician_id": clinician_id},
        SECRET, algorithm=ALGORITHM
    )
    grant_access(patient_id, clinician_id)

    headers_p = {"Authorization": f"Bearer {token_p}", "Idempotency-Key": f"idemp_{uuid.uuid4().hex[:8]}"}
    headers_c = {"Authorization": f"Bearer {token_c}"}

    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        # Cargar y confirmar examen
        client_upload_id = f"upl_rec_{uuid.uuid4().hex[:8]}"
        sha256_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        init_payload = {
            "client_upload_id": client_upload_id,
            "file_name": "analitica_batch.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024000,
            "sha256": sha256_hash,
            "test_type": "blood_test",
            "title": "Perfil Integral",
            "test_date": "2026-09-28",
        }
        res_init = client.post("/clinical-tests/uploads/initiate", json=init_payload, headers=headers_p)
        assert res_init.status_code == 201
        upload_id = res_init.json()["upload_id"]
        clinical_test_id = res_init.json()["clinical_test_id"]

        res_comp = client.post(
            f"/clinical-tests/uploads/{upload_id}/complete",
            json={"client_upload_id": client_upload_id, "sha256": sha256_hash, "size_bytes": 1024000},
            headers=headers_p
        )
        assert res_comp.status_code == 200

        # Esperar a que la extracción termine
        for _ in range(40):
            time.sleep(0.5)
            r_ext = client.get(f"/clinical-tests/{clinical_test_id}/extraction", headers=headers_p)
            if r_ext.status_code != 409:
                break
        assert r_ext.status_code == 200
        extraction_id = r_ext.json()["extraction_id"]

        # Confirmación paciente -> genera snapshot baseline
        res_conf = client.patch(
            f"/clinical-tests/{clinical_test_id}/extraction",
            json={"action": "confirm", "extraction_id": extraction_id, "marker_edits": []},
            headers=headers_p
        )
        assert res_conf.status_code == 200

        # Verificar snapshot baseline inicial
        initial_snapshots = list(mongo_test_db.score_snapshots.find({"patient_id": patient_id}))
        assert len(initial_snapshots) == 1
        baseline_snap_id = initial_snapshots[0]["snapshot_id"]

        # -------------------------------------------------------------
        # 1. EJECUCIÓN EN MODO DRY-RUN (--dry-run)
        # -------------------------------------------------------------
        dry_summary = run_bulk_recompute(
            db=mongo_test_db,
            scoring_version="score-v1.1-test",
            apply=False,
            target_patient_id=patient_id,
        )
        assert dry_summary["mode"].startswith("DRY-RUN")
        assert dry_summary["patients_recalculated"] >= 1

        # En dry-run la base de datos NO debe tener ningún snapshot adicional
        snapshots_after_dry = list(mongo_test_db.score_snapshots.find({"patient_id": patient_id}))
        assert len(snapshots_after_dry) == 1
        assert snapshots_after_dry[0]["snapshot_id"] == baseline_snap_id

        # -------------------------------------------------------------
        # 2. EJECUCIÓN EN MODO APPLY (--apply)
        # -------------------------------------------------------------
        time.sleep(1.05)  # Garantiza timestamp computed_at estrictamente posterior al baseline
        apply_summary = run_bulk_recompute(
            db=mongo_test_db,
            scoring_version="score-v1.1-test",
            apply=True,
            target_patient_id=patient_id,
        )
        assert apply_summary["mode"].startswith("APPLY")

        # En apply debe existir un segundo snapshot inmutable
        snapshots_after_apply = list(mongo_test_db.score_snapshots.find({"patient_id": patient_id}).sort([("computed_at", -1), ("_id", -1)]))
        assert len(snapshots_after_apply) == 2

        new_snapshot = snapshots_after_apply[0]
        assert new_snapshot["trigger"] == "recompute"
        assert new_snapshot["scoring_version"] == "score-v1.1-test"
        assert new_snapshot["snapshot_id"] != baseline_snap_id

        # El baseline sigue existiendo intacto
        old_snapshot = snapshots_after_apply[1]
        assert old_snapshot["snapshot_id"] == baseline_snap_id

        # Auditoría registrada
        audit_entry = mongo_test_db.audit_logs.find_one({"event_type": "bulk_scoring_recompute"})
        assert audit_entry is not None
        assert audit_entry["scoring_version"] == "score-v1.1-test"

        # -------------------------------------------------------------
        # 3. VERIFICAR ENDPOINT #18 CON ?history=true
        # -------------------------------------------------------------
        res_score = client.get(f"/patients/{patient_id}/lab-score?history=true", headers=headers_c)
        assert res_score.status_code == 200
        score_body = res_score.json()
        assert score_body["current_snapshot"]["trigger"] == "recompute"
        assert score_body["current_snapshot"]["scoring_version"] == "score-v1.1-test"
        assert score_body["history"] is not None
        assert len(score_body["history"]) >= 1
