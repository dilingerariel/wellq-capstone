"""F01-F07 regressions recovered from the final audit, extended at HTTP boundaries.

No Docker/lifespan/live services. Mongo atomicity is the existing explicit memory
model, not evidence of replica-set isolation. Original audit files stay intact.
"""
import copy
import io
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from conftest import export_precondition
from pydantic import ValidationError
from pypdf import PdfReader

from app.config import settings
from app.models.extraction import ReferenceRange
from app.models.reporting import LabReportExportResponse
from app.services import clinical_dates
from app.services.catalog import catalog_service
from app.services.clinical_dates import ClinicalDateError, validate_clinical_date
from app.services.extractor import ExtractionEngine
from app.services.scoring import scoring_engine
from app.services.storage import storage_service
from app.routes.clinical_tests import _export_response
from app.workers.processing import run_once
from test_lifecycle import prepared, OUTPUT, SyntheticProvider
from test_processing import headers, initiate, complete


@pytest.fixture(autouse=True)
def forbid_connections(monkeypatch):
    # Windows builds asyncio's private wake-up pipe using socketpair(), which
    # internally calls connect. Allow only that scoped IPC construction.
    original_pair, original_connect = socket.socketpair, socket.socket.connect
    local = threading.local()
    def private_pair(*args, **kwargs):
        local.building_pair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            local.building_pair = False
    def deny(sock, *args, **kwargs):
        if getattr(local, "building_pair", False):
            return original_connect(sock, *args, **kwargs)
        raise AssertionError("External connections forbidden in F01-F07 checks")
    monkeypatch.setattr(socket, "socketpair", private_pair)
    monkeypatch.setattr(socket.socket, "connect", deny)


@pytest.fixture
def pipeline(env, fake_storage):
    db = env["db"]
    db.clinical_tests.insert_one({"clinical_test_id": "ct-synthetic", "patient_id": "patient-test",
        "deleted_at": None, "ai_consent": True, "upload": {"status": "ready_for_review"},
        "file": {"verified_at": "synthetic", "gcs_object_key": "private/synthetic", "generation": 1}})
    fake_storage["private/synthetic"] = (b"SYNTHETIC", "application/pdf", 1)
    output = copy.deepcopy(OUTPUT)
    class Provider:
        model_id, model_version, is_test = "audit-synthetic", "1", True
        def extract(self, data, mime):
            return copy.deepcopy(output)
    return ExtractionEngine(Provider()), db, output


def confirm(env, init, ext, **changes):
    body = {"extraction_id": ext["extraction_id"], "document_edits": {"identity_confirmed": True}}
    body.update(changes)
    return env["client"].patch("/api/v1/clinical-tests/" + init["clinical_test_id"] + "/extraction",
                               headers=headers(env), json=body)


def clinician(env):
    env["db"].patient_access.insert_one({"patient_id": "patient-test", "authorised_clinicians": ["doctor-test"]})
    return headers(env, role="clinician", identity="doctor-test")


def test_f03_invalid_field_confidence_must_be_zero(pipeline):
    engine, db, output = pipeline
    output["panels"][0]["markers"][0]["unit_raw"] = "unsupported-unit"
    result = engine.run_extraction_pipeline("ct-synthetic", db)
    marker = result["panels"][0]["markers"][0]
    assert not marker["validation"]["passed"]
    assert set(marker["confidence"].values()) == {0.0}
    assert marker["provider_confidence"]["value"] == .99
    assert result["proposal"]["provider_output"] == output
    assert marker["value_canonical"] is None


def test_f04_document_reference_must_drive_display_status(pipeline):
    engine, db, output = pipeline
    output["panels"][0]["markers"][0]["reference"] = {"low": 100, "high": 150, "unit": "mg/dL"}
    marker = engine.run_extraction_pipeline("ct-synthetic", db)["panels"][0]["markers"][0]
    assert marker["reference"]["low"] == 100
    assert marker["status"] == "low"


def test_f05_future_date_must_not_pass_deterministic_validation(pipeline):
    engine, db, output = pipeline
    output["collection_date"] = "2999-01-01"
    with pytest.raises(ClinicalDateError):
        engine.run_extraction_pipeline("ct-synthetic", db)
    assert db.clinical_test_extractions.count_documents({}) == 0


def test_f02_nullable_reference_must_not_crash_scoring():
    # The original audit asserted a number. The user explicitly forbids inventing
    # a missing bilateral bound: exclusion with a reason is the corrected contract.
    ref = ReferenceRange(high=100, unit="mg/dL").model_dump()
    assert scoring_engine.calculate_subscore("glucose", 90, ref) == (None, None)
    assert scoring_engine.exclusion_reason("glucose", ref) == "INCOMPLETE_REFERENCE_RANGE"


def test_f06_signer_failure_must_not_report_ready(monkeypatch):
    def unavailable(**kwargs):
        raise RuntimeError("synthetic unavailable")
    monkeypatch.setattr(storage_service, "generate_download_url", unavailable)
    rec = {"object_key": "private/lab-reports/synthetic", "export_id": "audit", "patient_id": "synthetic",
        "file_name": "synthetic.pdf", "size_bytes": 1, "sha256": "synthetic", "storage": "gcs",
        "created_at": "2026-11-05T00:00:00Z"}
    result = _export_response(rec, False)
    assert result["status"] == "download_pending" and result["download_url"] is None
    assert result["error_code"] == "DOWNLOAD_URL_UNAVAILABLE"
    result.update(source_version="rpt1:1:" + "a" * 64, verified_at="2026-11-05T00:00:00Z")
    assert LabReportExportResponse.model_validate(result).status == "download_pending"


def test_f07_discard_replay_must_be_idempotent(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    path = "/api/v1/clinical-tests/" + init["clinical_test_id"] + "/extraction"
    body = {"action": "discard", "extraction_id": ext["extraction_id"]}
    first = env["client"].patch(path, headers=headers(env), json=body)
    assert first.status_code == 200, first.text
    documents = copy.deepcopy(list(env["db"].clinical_test_extractions.find()))
    events = list(env["db"].audit_events.find())
    # Model the caller losing the first response and repeating the same request.
    replay = env["client"].patch(path, headers=headers(env), json=body)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert list(env["db"].clinical_test_extractions.find()) == documents
    assert list(env["db"].audit_events.find()) == events
    assert documents[0]["proposal"] == ext["proposal"]
    changed = {**body, "document_edits": {"identity_confirmed": True}}
    conflict = env["client"].patch(path, headers=headers(env), json=changed)
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_f01_unapproved_catalog_must_not_publish_subscores(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    env["monkeypatch"].setattr(settings, "ENVIRONMENT", "production")
    env["monkeypatch"].setattr(settings, "CATALOG_CLINICALLY_APPROVED", False)
    assert confirm(env, init, ext).status_code == 200
    result = env["client"].get("/api/v1/patients/patient-test/markers?marker_codes=glucose", headers=clinician(env))
    assert result.status_code == 200
    assert result.json()["series"][0]["points"][0]["subscore"] is None
    assert env["db"].clinical_markers.find_one({})["subscore"] is None


@pytest.mark.parametrize("approved", [False, True])
def test_f01_all_publication_surfaces_and_patient_denials(env, fake_storage, sample_pdf, approved):
    init, ext = prepared(env, fake_storage, sample_pdf)
    env["monkeypatch"].setattr(settings, "ENVIRONMENT", "production")
    env["monkeypatch"].setattr(settings, "CATALOG_CLINICALLY_APPROVED", approved)
    # The catalogue is intentionally incomplete in the repository. This test
    # simulates a fully approved catalogue only to exercise the publication path.
    env["monkeypatch"].setattr(catalog_service, "definition_complete", approved)
    assert confirm(env, init, ext).status_code == 200
    hc = clinician(env)
    c = env["client"]; base = "/api/v1/patients/patient-test"
    series = c.get(base + "/markers?marker_codes=glucose", headers=hc).json()
    point = series["series"][0]["points"][0]
    assert point["value"] == 90
    assert point["subscore"] == (100.0 if approved else None)
    score = c.get(base + "/lab-score?history=true", headers=hc)
    assert score.status_code == (200 if approved else 404)
    report = c.get(base + "/lab-report?include_snapshot=true&include_series=true", headers=hc).json()
    row = report["results"]["panels"][0]["rows"][0]
    assert row["subscore"] == (100.0 if approved else None)
    assert (report["score"] is not None) == approved
    if not approved:
        assert report["flags"] == [] and report["longitudinal"]["pillar_series"] == []
        assert row["subscore_blank_reason"] == "CATALOG_NOT_APPROVED"
    export = c.post(base + "/lab-report/export", headers=hc, json=export_precondition(env, hc, include_series=True))
    assert export.status_code == 200 and export.json()["status"] == "ready"
    record = env["db"].lab_report_exports.find_one({})
    assert fake_storage[record["object_key"]][0].startswith(b"%PDF")
    for suffix in ["/lab-score", "/markers?marker_codes=glucose", "/lab-report"]:
        assert c.get(base + suffix, headers=headers(env)).status_code == 403
    assert c.post(base + "/lab-report/export", headers=headers(env), json={}).status_code == 403
    patient = c.get("/api/v1/clinical-tests/" + init["clinical_test_id"] + "/extraction", headers=headers(env)).json()
    assert "subscore" not in patient["panels"][0]["markers"][0]
    assert "lab_index" not in patient


@pytest.mark.parametrize("approved", [False, True])
def test_f01_legacy_scores_never_gain_approval_by_toggling_settings(env, fake_storage, sample_pdf, approved):
    init, ext = prepared(env, fake_storage, sample_pdf)
    assert confirm(env, init, ext).status_code == 200
    env["db"].clinical_markers.update_many({}, {"$set": {"subscore": 987.6}})
    raw_snapshot = copy.deepcopy(env["db"].score_snapshots.find_one({}))
    raw_snapshot.pop("_id")
    raw_snapshot.update(snapshot_id="legacy-unapproved", lab_index=987.6, catalog_clinically_approved=False)
    env["db"].score_snapshots.insert_one(raw_snapshot)
    env["monkeypatch"].setattr(settings, "ENVIRONMENT", "production")
    env["monkeypatch"].setattr(settings, "CATALOG_CLINICALLY_APPROVED", approved)
    hc = clinician(env); base = "/api/v1/patients/patient-test"; c = env["client"]
    assert c.get(base + "/lab-score?history=true", headers=hc).status_code == 404
    report = c.get(base + "/lab-report?include_series=true", headers=hc).json()
    assert report["score"] is None and report["flags"] == []
    assert report["longitudinal"]["pillar_series"] == []
    assert report["results"]["panels"][0]["rows"][0]["subscore"] is None
    exported = c.post(base + "/lab-report/export", headers=hc, json=export_precondition(env, hc, include_series=True))
    assert exported.status_code == 200
    obj = env["db"].lab_report_exports.find_one({})["object_key"]
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(fake_storage[obj][0])).pages)
    assert "987.6" not in text
    assert env["db"].clinical_markers.find_one({})["subscore"] == 987.6
    assert env["db"].score_snapshots.find_one({"snapshot_id": "legacy-unapproved"})["lab_index"] == 987.6


def test_f01_history_filters_unapproved_snapshots_and_old_export(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    env["monkeypatch"].setattr(settings, "CATALOG_CLINICALLY_APPROVED", True)
    env["monkeypatch"].setattr(catalog_service, "definition_complete", True)
    env["monkeypatch"].setattr(settings, "ENVIRONMENT", "production")
    assert confirm(env, init, ext).status_code == 200
    snapshot = env["db"].score_snapshots.find_one({}); snapshot.pop("_id")
    snapshot.update(snapshot_id="old-unapproved", computed_at="2020-01-01T00:00:00Z", catalog_clinically_approved=False)
    env["db"].score_snapshots.insert_one(snapshot)
    hc = clinician(env); base = "/api/v1/patients/patient-test"
    score = env["client"].get(base + "/lab-score?history=true", headers=hc)
    assert score.status_code == 200 and score.json()["history"] == []
    export_body = export_precondition(env, hc)
    assert env["client"].post(base + "/lab-report/export", headers=hc, json=export_body).status_code == 200
    env["monkeypatch"].setattr(settings, "CATALOG_CLINICALLY_APPROVED", False)
    replay = env["client"].post(base + "/lab-report/export", headers=hc, json=export_body)
    assert replay.status_code == 409 and replay.json()["detail"]["code"] == "EXPORT_SOURCE_CHANGED"


@pytest.mark.parametrize("code,reference,expected", [
    ("glucose", {"low": 70, "high": 100}, 100.0),
    ("glucose", {"high": 100}, None), ("glucose", {"low": 70}, None),
    ("glucose", {}, None), ("glucose", {"low": None, "high": None}, None),
    ("cholesterol_total", {"high": 200}, 100.0),
    ("hdl_cholesterol", {"low": 40}, 86.0),
    ("hdl_cholesterol", {"high": 200}, None),
    ("glucose", {"low": 100, "high": 150}, None),
])
def test_f02_optional_bounds_follow_direction_without_inventing_limits(code, reference, expected):
    value = 170 if code == "cholesterol_total" else 48 if code == "hdl_cholesterol" else 90
    score, _ = scoring_engine.calculate_subscore(code, value, reference)
    assert score == expected
    assert (scoring_engine.exclusion_reason(code, reference) is not None) == (expected is None)


@pytest.mark.parametrize("ref", [{"low": 10, "high": 2}, {"low": 2, "high": 2},
    {"low": "not-a-number"}, {"low": float("nan")}, {"high": float("inf")}, {"high": -float("inf")}])
def test_f02_bad_ranges_rejected_by_dto_and_excluded_safely_for_legacy(ref):
    with pytest.raises(ValidationError):
        ReferenceRange(**ref)
    assert scoring_engine.calculate_subscore("glucose", 90, ref) == (None, None)
    assert scoring_engine.exclusion_reason("glucose", ref) == "INVALID_REFERENCE_RANGE"


def test_f02_http_confirmation_retains_value_and_reports_exclusion(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    response = confirm(env, init, ext, marker_edits=[{"op": "update", "marker_code": "glucose",
        "value_raw": "90", "unit_raw": "mg/dL", "reference": {"high": 100}}])
    assert response.status_code == 200, response.text
    marker = env["db"].clinical_markers.find_one({})
    assert marker["value_canonical"] == 90 and marker["subscore"] is None
    assert marker["reference"].get("low") is None
    snapshot = env["db"].score_snapshots.find_one({})
    assert {"marker_code": "glucose", "reason": "INCOMPLETE_REFERENCE_RANGE"} in snapshot["excluded_markers"]
    report = env["client"].get("/api/v1/patients/patient-test/lab-report", headers=clinician(env)).json()
    assert report["results"]["panels"][0]["rows"][0]["subscore_blank_reason"] == "INCOMPLETE_REFERENCE_RANGE"


@pytest.mark.parametrize("value,unit,reference,expected", [
    ("90", "mg/dL", {"low": 100, "high": 150, "unit": "mg/dL"}, "low"),
    ("110", "mg/dL", {"low": 100, "high": 150, "unit": "mg/dL"}, "normal"),
    ("160", "mg/dL", {"low": 100, "high": 150, "unit": "mg/dL"}, "high"),
    ("5", "mmol/L", {"low": 6, "high": 8, "unit": "mmol/L"}, "low"),
    ("90", "mg/dL", {"high": 100, "unit": "mg/dL"}, "indeterminate"),
])
def test_f04_document_ranges_and_unit_conversion(pipeline, value, unit, reference, expected):
    engine, db, output = pipeline
    output["panels"][0]["markers"][0].update(value_raw=value, unit_raw=unit, reference=reference)
    marker = engine.run_extraction_pipeline("ct-synthetic", db)["panels"][0]["markers"][0]
    assert marker["status"] == expected
    if unit == "mmol/L":
        assert marker["reference"]["low"] == round(6 * 18.016, 2)
        assert marker["reference"]["unit"] == "mg/dL"


def test_f04_patient_and_clinician_edits_preserve_document_range(env, fake_storage, sample_pdf):
    output = copy.deepcopy(OUTPUT)
    output["panels"][0]["markers"][0]["reference"] = {"low": 100, "high": 150, "unit": "mg/dL"}
    env["monkeypatch"].setattr(SyntheticProvider, "extract", lambda *a: copy.deepcopy(output))
    init, ext = prepared(env, fake_storage, sample_pdf)
    response = confirm(env, init, ext, marker_edits=[{"op": "update", "marker_code": "glucose", "value_raw": "95", "unit_raw": "mg/dL"}])
    assert response.status_code == 200 and response.json()["panels"][0]["markers"][0]["status"] == "low"
    hc = clinician(env)
    path = "/api/v1/clinical-tests/" + init["clinical_test_id"] + "/extraction/validate"
    result = env["client"].post(path, headers=hc, json={"expected_version": env["client"].get(path.removesuffix("/extraction/validate"), headers=hc).json()["clinical_version"], "marker_corrections": [{"marker_code": "glucose", "value_raw": "110", "unit_raw": "mg/dL"}]})
    assert result.status_code == 200 and result.json()["panels"][0]["markers"][0]["status"] == "normal"
    series = env["client"].get("/api/v1/patients/patient-test/markers?marker_codes=glucose", headers=hc).json()
    assert series["series"][0]["points"][0]["status"] == "normal"
    report = env["client"].get("/api/v1/patients/patient-test/lab-report", headers=hc).json()
    row = report["results"]["panels"][0]["rows"][0]
    assert row["reference"]["low"] == 100 and row["status"] == "normal"
    assert env["db"].clinical_result_history.count_documents({}) == 1


@pytest.mark.parametrize("value,ok", [("2026-11-04", True), ("2026-11-05", True),
    ("2026-11-06", False), ("2026-02-30", False), ("20261105", False)])
def test_f05_clock_injection(value, ok):
    if ok:
        assert validate_clinical_date(value, date(2026, 11, 5)) == value
    else:
        with pytest.raises(ClinicalDateError):
            validate_clinical_date(value, date(2026, 11, 5))


@pytest.mark.parametrize("field", ["collection_date", "report_date", "panel"])
def test_f05_provider_dates_use_injected_day(pipeline, field):
    engine, db, output = pipeline
    output["collection_date"] = "2026-11-05"
    if field == "panel":
        output["panels"][0]["collection_date"] = "2026-11-06"
    else:
        output[field] = "2026-11-06"
    with pytest.raises(ClinicalDateError):
        engine.run_extraction_pipeline("ct-synthetic", db, as_of=date(2026, 11, 5))


@pytest.mark.parametrize("field", ["collection_date", "report_date", "panel"])
def test_f05_stored_future_dates_cannot_be_confirmed(env, fake_storage, sample_pdf, field):
    init, ext = prepared(env, fake_storage, sample_pdf)
    if field == "panel":
        ext["panels"][0]["collection_date"] = "2999-01-01"
        changes = {"panels": ext["panels"]}
    else:
        changes = {"document." + field: "2999-01-01"}
    env["db"].clinical_test_extractions.update_one({"extraction_id": ext["extraction_id"]}, {"$set": changes})
    assert confirm(env, init, ext).status_code == 422
    assert env["db"].clinical_markers.count_documents({}) == 0
    assert env["db"].score_snapshots.count_documents({}) == 0


@pytest.mark.parametrize("field", ["collection_date", "report_date"])
def test_f05_manual_future_dates_are_422_and_valid_correction_works(env, fake_storage, sample_pdf, field):
    init, ext = prepared(env, fake_storage, sample_pdf)
    bad = confirm(env, init, ext, document_edits={"identity_confirmed": True, field: "2999-01-01"})
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "INVALID_INPUT"
    good = confirm(env, init, ext, document_edits={"identity_confirmed": True, field: clinical_dates.today().isoformat()})
    assert good.status_code == 200


def test_f05_worker_records_specific_safe_error(env, fake_storage, sample_pdf):
    output = copy.deepcopy(OUTPUT); output["report_date"] = "2999-01-01"
    env["monkeypatch"].setattr(SyntheticProvider, "extract", lambda *a: copy.deepcopy(output))
    from app.services.extractor import extraction_engine
    from app.services.file_validation import scanner
    env["monkeypatch"].setattr(extraction_engine, "provider", SyntheticProvider())
    env["monkeypatch"].setattr(scanner, "scan", lambda data: None)
    init, body, doc = initiate(env, sample_pdf)
    fake_storage[doc["file"]["gcs_object_key"]] = (sample_pdf, "application/pdf", 1)
    assert complete(env, init, body).status_code == 200
    assert run_once(env["raw"], "upload") and run_once(env["raw"], "extraction")
    stored = env["db"].clinical_tests.find_one({})
    assert stored["extraction"]["status"] == "extraction_failed"
    assert stored["extraction_job"]["error_code"] == "INVALID_CLINICAL_DATE"
    path = "/api/v1/clinical-tests/" + init["clinical_test_id"] + "/extraction"
    failure = env["client"].get(path, headers=headers(env))
    assert failure.status_code == 409 and failure.json()["detail"]["code"] == "INVALID_CLINICAL_DATE"
    status = env["client"].get("/api/v1/clinical-tests/uploads/" + init["upload_id"] + "/status", headers=headers(env))
    assert status.json()["local_file_can_be_deleted"] is True
    output["report_date"] = clinical_dates.today().isoformat()
    retry = env["client"].post(path + "/reprocess", headers=headers(env), json={})
    assert retry.status_code == 200, retry.text
    assert run_once(env["raw"], "extraction")
    assert env["client"].get(path, headers=headers(env)).json()["status"] == "awaiting_confirmation"


def test_f06_signer_recovers_with_same_export_and_no_duplicate_events(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    assert confirm(env, init, ext).status_code == 200
    hc = clinician(env); path = "/api/v1/patients/patient-test/lab-report/export"
    signer = storage_service.generate_download_url
    def broken(**kwargs):
        raise RuntimeError("test outage")
    env["monkeypatch"].setattr(storage_service, "generate_download_url", broken)
    export_body = export_precondition(env, hc)
    first = env["client"].post(path, headers=hc, json=export_body)
    assert first.status_code == 200 and first.json()["status"] == "download_pending"
    record = env["db"].lab_report_exports.find_one({})
    assert fake_storage[record["object_key"]][0].startswith(b"%PDF")
    events = list(env["db"].audit_events.find({"event": "lab_report_export"}))
    env["monkeypatch"].setattr(storage_service, "generate_download_url", signer)
    replay = env["client"].post(path, headers=hc, json=export_body)
    assert replay.status_code == 200 and replay.json()["status"] == "ready"
    assert replay.json()["export_id"] == first.json()["export_id"] and replay.json()["replayed"]
    assert replay.json()["download_url"]
    assert env["db"].lab_report_exports.count_documents({}) == 1
    assert list(env["db"].audit_events.find({"event": "lab_report_export"})) == events


def test_f06_ready_without_url_is_invalid_dto():
    with pytest.raises(ValidationError):
        LabReportExportResponse(export_id="test", patient_id="test", status="ready", file_name="test.pdf",
            download_url=None, expires_at=None, size_bytes=1, sha256="test", storage="gcs", replayed=False, generated_at="test", source_version="rpt1:1:" + "a" * 64, verified_at="test")


def test_f07_concurrent_discards_with_memory_transaction_model(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    path = "/api/v1/clinical-tests/" + init["clinical_test_id"] + "/extraction"
    body = {"action": "discard", "extraction_id": ext["extraction_id"]}
    request_headers = headers(env)
    def call(_):
        return env["client"].patch(path, headers=request_headers, json=body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(call, range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json() == results[1].json()
    assert env["db"].audit_events.count_documents({"event": "extraction_discarded"}) == 1


def test_openapi_error_envelope_matches_actual_422(env):
    from app.main import app
    from app.models.errors import ErrorResponse
    schema = app.openapi()
    clinical = [op for path, item in schema["paths"].items() if path.startswith("/api/v1") and not path.startswith("/api/v1/demo")
        for method, op in item.items() if method in ("get", "post", "patch", "delete")]
    assert len(clinical) == 28
    for op in clinical:
        for status in ("401", "403", "404", "409", "422", "429", "503"):
            assert op["responses"][status]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
        assert "WWW-Authenticate" in op["responses"]["401"]["headers"]
        assert "Retry-After" in op["responses"]["429"]["headers"]
    bad = env["client"].post("/api/v1/clinical-tests/uploads/initiate", headers=headers(env), json={})
    assert bad.status_code == 422
    assert ErrorResponse.model_validate(bad.json()).detail.code == "INVALID_INPUT"


def test_f01_clinical_correction_does_not_publish_unapproved_cache(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    assert confirm(env, init, ext).status_code == 200
    env["monkeypatch"].setattr(settings, "ENVIRONMENT", "production")
    env["monkeypatch"].setattr(settings, "CATALOG_CLINICALLY_APPROVED", False)
    hc = clinician(env)
    result = env["client"].post("/api/v1/clinical-tests/" + init["clinical_test_id"] + "/extraction/validate",
        headers=hc, json={"expected_version": env["client"].get("/api/v1/clinical-tests/" + init["clinical_test_id"], headers=hc).json()["clinical_version"], "marker_corrections": [{"marker_code": "glucose", "value_raw": "95", "unit_raw": "mg/dL"}]})
    assert result.status_code == 200, result.text
    assert env["db"].clinical_markers.find_one({})["subscore"] is None
    report = env["client"].get("/api/v1/patients/patient-test/lab-report?include_series=true", headers=hc).json()
    assert report["score"] is None and report["longitudinal"]["pillar_series"] == []
    assert report["results"]["panels"][0]["rows"][0]["value"] == 95
    assert report["results"]["panels"][0]["rows"][0]["subscore"] is None


def test_f03_invalid_provider_marker_stays_out_of_scoring(env, fake_storage, sample_pdf):
    output = copy.deepcopy(OUTPUT); output["panels"][0]["markers"][0]["unit_raw"] = "unknown-unit"
    env["monkeypatch"].setattr(SyntheticProvider, "extract", lambda *a: copy.deepcopy(output))
    init, ext = prepared(env, fake_storage, sample_pdf)
    response = confirm(env, init, ext, acknowledged_marker_codes=["glucose"])
    assert response.status_code == 200
    marker = response.json()["panels"][0]["markers"][0]
    assert marker["provider_confidence"]["value"] == .99 and marker["confidence"]["value"] == 0
    assert env["db"].clinical_markers.count_documents({}) == 0


def test_f04_patient_reference_conversion_is_shared(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    response = confirm(env, init, ext, marker_edits=[{"op": "update", "marker_code": "glucose",
        "value_raw": "5", "unit_raw": "mmol/L", "reference": {"low": 6, "high": 8, "unit": "mmol/L"}}])
    assert response.status_code == 200, response.text
    marker = response.json()["panels"][0]["markers"][0]
    assert marker["status"] == "low" and marker["reference"]["low"] == round(6 * 18.016, 2)


@pytest.mark.parametrize("operation", ["initiate", "edit"])
def test_f05_upload_metadata_future_dates_rejected(env, fake_storage, sample_pdf, operation):
    if operation == "initiate":
        from app.models.schemas import InitiateUploadRequest
        with pytest.raises(ValidationError):
            InitiateUploadRequest(client_upload_id="synthetic", file_name="test.pdf", mime_type="application/pdf",
                size_bytes=1, sha256="0" * 64, test_type="blood_test", title="Synthetic", test_date="2999-01-01")
    else:
        init, ext = prepared(env, fake_storage, sample_pdf)
        response = env["client"].patch("/api/v1/clinical-tests/" + init["clinical_test_id"],
            headers=headers(env), json={"test_date": "2999-01-01"})
        assert response.status_code == 422


@pytest.mark.parametrize("partial", [{"url": "https://storage.test.invalid/private"}, {"expires_at": "2099-01-01T00:00:00Z"}])
def test_f06_partial_signer_output_never_becomes_ready(monkeypatch, partial):
    monkeypatch.setattr(storage_service, "generate_download_url", lambda **kw: partial)
    result = _export_response({"object_key": "private/synthetic", "export_id": "synthetic", "patient_id": "synthetic",
        "file_name": "synthetic.pdf", "size_bytes": 1, "sha256": "synthetic", "storage": "gcs", "created_at": "synthetic"}, False)
    assert result["status"] == "download_pending" and result["download_url"] is None and result["expires_at"] is None


@pytest.mark.parametrize("ref", [{"low": True}, {"high": False}])
def test_f02_boolean_is_not_a_clinical_bound(ref):
    with pytest.raises(ValidationError):
        ReferenceRange(**ref)
