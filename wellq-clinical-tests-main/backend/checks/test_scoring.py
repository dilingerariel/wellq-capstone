import importlib.util
from pathlib import Path
from datetime import datetime
import pytest
from app.services.catalog import catalog_service
from app.services.scoring import scoring_engine

# Reuse existing pure reference tests without importing their live-DB conftest.
def load(name):
    spec = importlib.util.spec_from_file_location("legacy_" + name, Path(__file__).parents[1] / "tests" / (name + ".py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
units = load("test_normalizer_units")
reference = load("test_scoring_reproducibility")

@pytest.mark.parametrize("args", units.EXPECTED_FACTORS)
def test_preserved_conversion_factors(args): units.test_conversion_factor(*args)

@pytest.mark.parametrize("args", units.TYPICAL_VALUES)
def test_preserved_conversion_values(args): units.test_typical_value_in_alternative_unit_is_converted(*args)

@pytest.mark.parametrize("args", reference.CASES)
def test_preserved_reference_formula(args): reference.test_engine_matches_reference_formula(*args)

@pytest.mark.parametrize("value", ["NaN", "inf", "-inf", "Infinity"])
def test_nonfinite_normalization_rejected(value):
    assert catalog_service.validate_and_convert("glucose", value, "mg/dL")["valid"] is False
    with pytest.raises(ValueError): scoring_engine.calculate_subscore("glucose", float(value))

def seed(db, identity, day, value=90, **extra):
    db.clinical_tests.insert_one({"clinical_test_id": identity, "patient_id": "patient-test", "deleted_at": None,
        "upload": {"upload_id": identity, "client_upload_id": identity, "idempotency_key": identity}})
    doc = {"clinical_test_id": identity, "patient_id": "patient-test", "marker_code": "glucose",
        "extraction_id": "ext-" + identity, "measured_on": day, "value_canonical": value, "unit_canonical": "mg/dL",
        "confirmation_level": "patient", "status": "normal", "invalidated_at": None, "updated_at": datetime(2026,11,5)}
    doc.update(extra); db.clinical_markers.insert_one(doc)

def test_calendar_window_and_most_recent_valid_measurement(env):
    db = env["db"]
    seed(db, "too-old", "2025-11-04", 140)
    seed(db, "boundary", "2025-11-05", 95)
    seed(db, "current", "2026-11-04", 90)
    seed(db, "future", "2026-11-06", 170)
    seed(db, "invalidated", "2026-11-05", 150, invalidated_at=datetime(2026,11,5))
    seed(db, "unconfirmed", "2026-11-05", 150, confirmation_level="proposed")
    seed(db, "deleted", "2026-11-05", 150)
    db.clinical_tests.update_one({"clinical_test_id": "deleted"}, {"$set": {"deleted_at": datetime(2026,11,5)}})
    score = scoring_engine.compute_patient_score("patient-test", db, as_of=datetime(2026,11,5))
    contribution = score["pillars"]["cardio"]["contributions"][0]
    assert contribution["clinical_test_id"] == "current" and contribution["value"] == 90
    assert {m["clinical_test_id"] for m in score["input_markers"]} == {"boundary", "current"}
    assert score["window"]["from"] == "2025-11-05"

def test_ties_reproducibility_versions_and_snapshot_preservation(env):
    db = env["db"]
    seed(db, "one", "2026-11-05", 90)
    seed(db, "two", "2026-11-05", 100)
    a = scoring_engine.compute_patient_score("patient-test", db, as_of=datetime(2026,11,5))
    b = scoring_engine.compute_patient_score("patient-test", db, as_of=datetime(2026,11,5))
    assert a["pillars"] == b["pillars"] and a["lab_index"] == b["lab_index"]
    assert a["source_digest"] == b["source_digest"] and a["catalog_hash"] == b["catalog_hash"]
    assert db.score_snapshots.count_documents({}) == 2
    assert a["pillars"]["cardio"]["contributions"][0]["clinical_test_id"] == "two"
    with pytest.raises(ValueError): scoring_engine.compute_patient_score("patient-test", db, scoring_version_override="invented")
    assert db.score_snapshots.count_documents({}) == 2
    frozen = catalog_service.list_catalog(); frozen[0]["pillar_weights"] = {"cardio": 999}
    assert catalog_service.list_catalog()[0]["pillar_weights"] != {"cardio": 999}

def test_unapproved_catalogue_does_not_publish_in_development(env):
    env["monkeypatch"].setattr(__import__("app.config", fromlist=["settings"]).settings, "ENVIRONMENT", "development")
    assert scoring_engine.compute_patient_score("patient-test", env["db"]) is None
    assert env["db"].score_snapshots.count_documents({}) == 0

def test_dry_run_has_no_writes(env):
    db = env["db"]; seed(db, "test", "2026-11-05")
    before = list(db.clinical_markers.find())
    scoring_engine.compute_patient_score("patient-test", db, persist=False, as_of=datetime(2026,11,5))
    assert list(db.clinical_markers.find()) == before
    assert db.score_snapshots.count_documents({}) == 0


def test_snapshots_keep_subsecond_order_across_client_object_ids(env):
    """Real integration found same-second snapshots sorted by process ObjectId."""
    db = env["db"]
    seed(db, "temporal-order", "2026-11-05")
    first = scoring_engine.compute_patient_score("patient-test", db, as_of=datetime(2026, 11, 5, 10, 0, 0, 100000))
    second = scoring_engine.compute_patient_score("patient-test", db, as_of=datetime(2026, 11, 5, 10, 0, 0, 200000))
    assert first["computed_at"] < second["computed_at"]
    assert db.score_snapshots.find_one({}, sort=[("computed_at", -1)])["snapshot_id"] == second["snapshot_id"]


def test_same_values_keep_contribution_order_after_correction(env):
    from datetime import timedelta
    db = env["db"]
    seed(db, "stable-contributions", "2026-11-05")
    base = db.clinical_markers.find_one({})
    base.pop("_id")
    base.update(marker_code="hemoglobin", value_canonical=14.2, unit_canonical="g/dL")
    db.clinical_markers.insert_one(base)
    first = scoring_engine.compute_patient_score("patient-test", db, as_of=datetime(2026, 11, 5))
    db.clinical_markers.update_one({"marker_code": "glucose"}, {"$set": {"updated_at": datetime(2026,11,5)+timedelta(hours=1)}})
    second = scoring_engine.compute_patient_score("patient-test", db, as_of=datetime(2026, 11, 5))
    assert first["pillars"] == second["pillars"]
