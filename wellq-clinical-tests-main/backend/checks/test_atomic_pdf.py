"""Contract/saga regressions. Memory rollback model, NOT Mongo isolation evidence.

Real replica-set/HTTP races live in frontend/scripts/atomic_pdf_live.py.
"""
import copy
from datetime import UTC, datetime, timedelta

import pytest
from conftest import export_precondition
from test_final_defects import clinician, confirm
from test_lifecycle import prepared

BASE = "/api/v1/patients/patient-test/lab-report"


@pytest.fixture
def ready(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    assert confirm(env, init, ext).status_code == 200
    hc = clinician(env)
    return env, hc, export_precondition(env, hc), init["clinical_test_id"]


def post(ready, body=None, key=None):
    env, hc, original, _ = ready
    return env["client"].post(BASE + "/export", headers={**hc, **({"Idempotency-Key": key} if key else {})},
                              json=original if body is None else body)


@pytest.mark.parametrize("body,status,code", [
    ({}, 428, "EXPORT_VERSION_REQUIRED"),
    ({"expected_source_version": None}, 428, "EXPORT_VERSION_REQUIRED"),
    ({"expected_source_version": "invalid"}, 422, "VALIDATION_ERROR"),
    ({"expected_source_version": "rpt1:999:" + "a" * 64}, 409, "EXPORT_SOURCE_CHANGED"),
])
def test_precondition_fails_closed(ready, body, status, code):
    result = post(ready, body)
    assert result.status_code == status
    if status != 422:
        assert result.json()["detail"]["code"] == code
    assert ready[0]["db"].lab_report_exports.count_documents({}) == 0


def test_projection_and_generated_time_do_not_change_source(ready):
    env, hc, body, _ = ready
    for series in (True, False):
        for snapshot in (True, False):
            result = env["client"].get(BASE, headers=hc, params={"include_series": series, "include_snapshot": snapshot})
            assert result.json()["source_version"] == body["expected_source_version"]
    assert post(ready).status_code == 200
    assert export_precondition(env, hc) == body  # export checks never advance source


def test_monotonic_aba_and_historical_snapshot_preservation(ready):
    env, hc, body, cid = ready
    before = list(env["db"].score_snapshots.find({}))
    old = env["db"].clinical_tests.find_one({"clinical_test_id": cid})["title"]
    exported = post(ready)
    assert exported.status_code == 200
    for title in ("SYNTHETIC B", old):
        env["db"].clinical_tests.update_one({"clinical_test_id": cid}, {"$set": {"title": title}})
    assert export_precondition(env, hc) != body
    assert post(ready).status_code == 409
    assert env["db"].lab_report_exports.find_one({})["state"] == "stale"
    assert list(env["db"].score_snapshots.find({})) == before
    # Refreshing the source must never silently change the old key's meaning.
    assert post(ready, export_precondition(env, hc)).json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert post(ready, export_precondition(env, hc), "synthetic-fresh-key").status_code == 200


@pytest.mark.parametrize("stage", ["_build_lab_report_pdf", "_store_export_pdf", "_export_response"])
def test_change_at_each_external_boundary_never_returns_link(ready, stage):
    from app.routes import clinical_tests as routes
    env, _, _, cid = ready
    old = getattr(routes, stage)
    def changed(*args, **kwargs):
        result = old(*args, **kwargs)
        env["db"].clinical_tests.update_one({"clinical_test_id": cid}, {"$set": {"title": "SYNTHETIC CHANGED"}})
        return result
    env["monkeypatch"].setattr(routes, stage, changed)
    result = post(ready)
    assert result.status_code == 409 and "download_url" not in result.text
    assert env["db"].lab_report_exports.find_one({})["state"] == "stale"
    assert env["db"].audit_events.count_documents({"event": "lab_report_export_failed"}) == 1


@pytest.mark.parametrize("stage,expected", [("_store_export_pdf", 502), ("_build_lab_report_pdf", 503)])
def test_failed_effect_never_repeats_upload_for_same_key(ready, stage, expected):
    from app.routes import clinical_tests as routes
    env = ready[0]
    calls = []
    def failed(*args):
        calls.append(True)
        raise RuntimeError("synthetic dependency failure")
    env["monkeypatch"].setattr(routes, stage, failed)
    assert post(ready).status_code == expected
    assert env["db"].lab_report_exports.find_one({})["state"] == "failed"
    assert post(ready).json()["detail"]["code"] == "EXPORT_ATTEMPT_FAILED"
    assert len(calls) == 1
    assert env["db"].audit_events.count_documents({"event": "lab_report_export"}) == 0


def test_expired_pending_attempt_is_terminal(ready):
    env, _, body, _ = ready
    env["db"].lab_report_exports.insert_one({"patient_id": "patient-test", "clinician_id": "doctor-test",
        "idempotency_key": ready[1]["Idempotency-Key"], "export_id": "synthetic-expired",
        "params": {"clinical_test_id": None, "window_months": 12, "include_series": True},
        "source_version": body["expected_source_version"], "state": "pending",
        "lease_until": datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)})
    result = post(ready)
    assert result.status_code == 409 and result.json()["detail"]["code"] == "EXPORT_ATTEMPT_EXPIRED"
    assert env["db"].lab_report_exports.find_one({})["state"] == "failed"


def test_tenant_isolation_and_same_key_immutable_proof(ready):
    from app.tenancy import TenantDatabase
    env, hc, body, _ = ready
    first = post(ready)
    assert first.status_code == 200
    record = copy.deepcopy(env["db"].lab_report_exports.find_one({}))
    other = TenantDatabase(env["raw"], "synthetic-other")
    other.clinical_tests.insert_one({"clinical_test_id": "synthetic", "title": "synthetic"})
    assert export_precondition(env, hc) == body
    replay = post(ready)
    assert replay.status_code == 200 and replay.json()["replayed"]
    for name in ("export_id", "sha256", "size_bytes", "source_version", "generated_at"):
        assert replay.json()[name] == first.json()[name]
    assert env["db"].lab_report_exports.find_one({})["object_key"] == record["object_key"]
    assert env["db"].lab_report_exports.count_documents({}) == 1
    assert env["db"].audit_events.count_documents({"event": "lab_report_export"}) == 1


def test_openapi_declares_precondition_errors(ready):
    from app.main import app
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/patients/{patient_id}/lab-report/export"]["post"]
    assert {"409", "428"}.issubset(operation["responses"])
    assert "expected_source_version" in schema["components"]["schemas"]["LabReportExportRequest"]["properties"]
