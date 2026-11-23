import copy
import hashlib
from datetime import datetime

import pytest
from conftest import export_precondition
from test_processing import complete, headers, initiate

from app.services.extractor import (
    ExtractionEngine,
    ExtractionUnavailable,
    ProviderOutput,
    extraction_engine,
)
from app.services.file_validation import scanner
from app.workers.processing import run_once

OUTPUT = {"schema_version": "1.0", "document_type": "blood_panel", "language": "es", "page_count": 1,
          "collection_date": datetime.utcnow().strftime("%Y-%m-%d"), "panels": [{"panel_code": "metabolic_panel",
          "panel_name_raw": "SYNTHETIC", "specimen": "blood", "markers": [{"marker_code": "glucose",
          "raw_name": "Glucose test", "value_raw": "90", "unit_raw": "mg/dL", "page": 1, "evidence": "synthetic annotation",
          "confidence": {"value": .99, "unit": .99, "reference": .99, "name": .99}}]}]}
class SyntheticProvider:
    model_id, model_version, is_test = "isolated-test", "1", True
    def extract(self, data, mime_type): return copy.deepcopy(OUTPUT)

def prepared(env, fake_storage, sample_pdf):
    init, body, doc = initiate(env, sample_pdf)
    fake_storage[doc["file"]["gcs_object_key"]] = (sample_pdf, "application/pdf", 1)
    env["monkeypatch"].setattr(scanner, "scan", lambda data: None)
    env["monkeypatch"].setattr(extraction_engine, "provider", SyntheticProvider())
    assert complete(env, init, body).status_code == 200
    assert run_once(env["raw"], "upload") and run_once(env["raw"], "extraction")
    ext = env["db"].clinical_test_extractions.find_one({})
    assert ext is not None
    return init, ext

def test_confirm_validate_report_export_delete(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    c = env["client"]; path = "/api/v1/clinical-tests/" + init["clinical_test_id"]
    payload = {"action": "confirm", "extraction_id": ext["extraction_id"]}
    assert c.patch(path + "/extraction", headers=headers(env), json=payload).status_code == 422
    payload["document_edits"] = {"identity_confirmed": True}
    response = c.patch(path + "/extraction", headers=headers(env), json=payload)
    assert response.status_code == 200, response.text
    replay = c.patch(path + "/extraction", headers=headers(env), json=payload)
    assert replay.status_code == 200
    assert env["db"].clinical_markers.count_documents({}) == 1
    env["db"].patient_access.insert_one({"patient_id": "patient-test", "authorised_clinicians": ["doctor-test"]})
    hc = headers(env, role="clinician", identity="doctor-test")
    correction = {"marker_code": "glucose", "value_raw": "95", "unit_raw": "mg/dL", "reason": "synthetic test correction"}
    response = c.post(path + "/extraction/validate", headers=hc,
        json={"expected_version": c.get(path, headers=hc).json()["clinical_version"], "marker_corrections": [correction], "clinical_note": "PRIVATE-NOTE-SENTINEL"})
    assert response.status_code == 200, response.text
    patient = c.get(path + "/extraction", headers=headers(env))
    assert "PRIVATE-NOTE-SENTINEL" not in patient.text
    stored = env["db"].clinical_test_extractions.find_one({})
    assert stored["proposal"]["panels"][0]["markers"][0]["value_canonical"] == 90
    assert stored["panels"][0]["markers"][0]["value_canonical"] == 95
    base = "/api/v1/patients/patient-test"
    score = c.get(base + "/lab-score?history=true", headers=hc)
    assert score.status_code == 200, score.text
    assert score.json()["current_snapshot"]["trigger"] == "clinician_correction"
    assert c.get(base + "/lab-score", headers=headers(env)).status_code == 403
    report = c.get(base + "/lab-report", headers=hc)
    assert report.status_code == 200 and report.json()["results"]["panels"][0]["rows"][0]["value"] == 95
    export = c.post(base + "/lab-report/export", headers=hc, json=export_precondition(env, hc, include_series=True))
    assert export.status_code == 200, export.text
    repeated = c.post(base + "/lab-report/export", headers=hc, json=export_precondition(env, hc, include_series=True))
    assert repeated.status_code == 200 and repeated.json()["export_id"] == export.json()["export_id"]
    exported = env["db"].lab_report_exports.find_one({})
    data = fake_storage[exported["object_key"]][0]
    assert data.startswith(b"%PDF") and hashlib.sha256(data).hexdigest() == exported["sha256"]
    assert c.delete(path, headers=headers(env)).status_code == 200
    assert env["db"].clinical_markers.find_one({})["invalidated_at"] is not None
    series = c.get(base + "/markers?marker_codes=glucose", headers=hc)
    assert series.status_code == 200 and series.json()["series"][0]["points"] == []
    report = c.get(base + "/lab-report", headers=hc)
    assert report.json()["results"]["panels"] == []
    logs = list(env["db"].audit_events.find())
    assert logs and all("previous_value_canonical" not in row and "new_value_canonical" not in row for row in logs)
    assert all("PRIVATE-NOTE-SENTINEL" not in str(row) for row in logs)

@pytest.mark.parametrize("mutation", ["missing", "invalid", "duplicate", "date"])
def test_provider_schema_rejects_invalid_payload(mutation):
    value = copy.deepcopy(OUTPUT)
    if mutation == "missing": del value["panels"]
    if mutation == "invalid": value["panels"][0]["markers"][0]["confidence"]["value"] = 1.1
    if mutation == "duplicate": value["unexpected"] = "forbidden"
    if mutation == "date": value["page_count"] = 0
    with pytest.raises(ValueError): ProviderOutput.model_validate(value)

def test_test_provider_forbidden_outside_tests(env):
    env["monkeypatch"].setattr(__import__("app.config", fromlist=["settings"]).settings, "ENVIRONMENT", "production")
    with pytest.raises(ExtractionUnavailable): ExtractionEngine(SyntheticProvider()).run_extraction_pipeline("none", env["db"])

def test_transaction_rollback_model(env):
    # This tests application boundary with a memory double, not Mongo atomicity.
    with pytest.raises(ValueError):
        with env["db"].atomic():
            env["db"].audit_events.insert_one({"event": "rollback-test"})
            raise ValueError()
    assert env["db"].audit_events.count_documents({}) == 0

def test_openapi_contract(env):
    from app.main import app
    schema = app.openapi()
    operations = [(path, verb, op) for path, item in schema["paths"].items()
                  for verb, op in item.items() if path.startswith("/api/v1") and not path.startswith("/api/v1/demo") and verb in ("get", "post", "patch", "delete")]
    assert len(operations) == 28
    public_account_flows = {
        ("/api/v1/auth/clinics", "get"),
        ("/api/v1/auth/catalog/clinics", "get"),
        ("/api/v1/auth/patient/register", "post"),
        ("/api/v1/auth/login", "post"),
        ("/api/v1/auth/admin/login", "post"),
    }
    for path, verb, op in operations:
        assert op.get("security") or (path, verb) in public_account_flows, (path, verb)
        if path.endswith(("/complete", "/refresh-url", "/initiate", "/reprocess", "/export")) or (path.endswith("/extraction") and verb == "patch"):
            assert any(p["name"] == "idempotency-key" and p["required"] for p in op["parameters"])

def test_reprocess_invalidates_and_replays_without_extra_proposal(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    c = env["client"]; path = "/api/v1/clinical-tests/" + init["clinical_test_id"]
    payload = {"action": "confirm", "extraction_id": ext["extraction_id"], "document_edits": {"identity_confirmed": True}}
    assert c.patch(path + "/extraction", headers=headers(env), json=payload).status_code == 200
    body = {"confirm_reprocess_confirmed": True}
    assert c.post(path + "/extraction/reprocess", headers=headers(env), json=body).status_code == 200
    assert c.post(path + "/extraction/reprocess", headers=headers(env), json=body).status_code == 200
    assert c.get(path + "/extraction", headers=headers(env)).status_code == 409
    assert env["db"].clinical_markers.find_one({})["invalidated_at"] is not None
    assert run_once(env["raw"], "extraction")
    doc = env["db"].clinical_tests.find_one({})
    assert doc["extraction"]["reprocess_count"] == 1
    assert env["db"].clinical_test_extractions.count_documents({}) == 2
    old = env["db"].clinical_test_extractions.find_one({"extraction_id": ext["extraction_id"]})
    assert old["proposal"] == ext["proposal"] and old["superseded_at"] is not None

def test_multi_panel_confirmation_and_low_confidence_ack(env, fake_storage, sample_pdf):
    output = copy.deepcopy(OUTPUT)
    marker = copy.deepcopy(output["panels"][0]["markers"][0])
    marker.update(marker_code="hemoglobin", raw_name="Synthetic hemoglobin", value_raw="14", unit_raw="g/dL")
    marker["confidence"]["value"] = .5
    output["panels"].append({"panel_code": "complete_blood_count", "panel_name_raw": "SYNTHETIC TWO", "specimen": "blood", "markers": [marker]})
    env["monkeypatch"].setattr(SyntheticProvider, "extract", lambda self, data, mime: copy.deepcopy(output))
    init, ext = prepared(env, fake_storage, sample_pdf)
    path = "/api/v1/clinical-tests/" + init["clinical_test_id"] + "/extraction"
    payload = {"extraction_id": ext["extraction_id"], "document_edits": {"identity_confirmed": True}}
    assert env["client"].patch(path, headers=headers(env), json=payload).status_code == 422
    payload["acknowledged_marker_codes"] = ["hemoglobin"]
    response = env["client"].patch(path, headers=headers(env), json=payload)
    assert response.status_code == 200, response.text
    markers = list(env["db"].clinical_markers.find())
    assert {m["marker_code"]: m["panel_code"] for m in markers} == {"glucose": "metabolic_panel", "hemoglobin": "complete_blood_count"}

def test_invalid_edit_and_changed_idempotent_body_are_rejected(env, fake_storage, sample_pdf):
    init, ext = prepared(env, fake_storage, sample_pdf)
    path = "/api/v1/clinical-tests/" + init["clinical_test_id"] + "/extraction"
    payload = {"extraction_id": ext["extraction_id"], "document_edits": {"identity_confirmed": True},
               "marker_edits": [{"op": "update", "marker_code": "missing", "value_raw": "1", "unit_raw": "mg/dL"}]}
    assert env["client"].patch(path, headers=headers(env), json=payload).status_code == 422
    assert env["db"].clinical_markers.count_documents({}) == 0
    payload["marker_edits"] = []
    assert env["client"].patch(path, headers=headers(env), json=payload).status_code == 200
    payload["action"] = "discard"
    assert env["client"].patch(path, headers=headers(env), json=payload).status_code == 409

def test_reference_ranges_and_missing_confidence_fields():
    from app.models.extraction import ReferenceRange
    for kwargs in [{"low": 2, "high": 1}, {"low": float("nan")}]:
        with pytest.raises(ValueError): ReferenceRange(**kwargs)
    output = copy.deepcopy(OUTPUT)
    output["panels"][0]["markers"][0]["confidence"] = {}
    with pytest.raises(ValueError): ProviderOutput.model_validate(output)

def test_empty_evaluation_does_not_claim_accuracy():
    from app.services.evaluation import evaluate
    metrics = evaluate([], [])
    assert metrics["value_accuracy"] is None and metrics["coverage"] is None
    expected = [{"document_id": "synthetic", "markers": [{"marker_code": "x", "value": 1, "unit": "test"}]}]
    prediction = [{"document_id": "synthetic", "markers": [{"marker_code": "unexpected", "value": 2, "unit": "test"}]}]
    metrics = evaluate(expected, prediction)
    assert metrics["coverage"] == 0 and metrics["unsupported_proposal_rate"] == 1
    assert metrics["not_a_clinical_validation"] is True
