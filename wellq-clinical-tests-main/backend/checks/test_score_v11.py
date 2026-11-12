"""Documented technical proposals only; no live DB or clinical approval."""

from copy import deepcopy
from datetime import datetime

import pytest
from test_scoring import seed

from app.config import settings
from app.models.scoring import FlagSeverity, ScoreFlag
from app.services.catalog import catalog_service
from app.services.scoring import scoring_engine


def flag(severity):
    return ScoreFlag(
        code="synthetic",
        severity=severity,
        marker_code="synthetic",
        value=1,
        message="SYNTHETIC",
    )


@pytest.mark.parametrize(
    "coverage,confidence",
    [
        (0.349, "insufficient"),
        (0.350, "medium"),
        (0.599, "medium"),
        (0.600, "high"),
        (0.349999, "insufficient"),
        (0.599999, "medium"),
    ],
)
def test_weighted_boundary_without_rounding(env, coverage, confidence):
    cat = catalog_service.list_catalog()
    glucose = next(i for i in cat if i["marker_code"] == "glucose")
    glucose["pillar_weights"] = {"cardio": coverage * 10}
    other = next(i for i in cat if i["marker_code"] == "ldl_cholesterol")
    other["pillar_weights"] = {"cardio": 10 - coverage * 10}
    env["monkeypatch"].setattr(
        catalog_service,
        "catalog_by_code",
        {i["marker_code"]: i for i in [glucose, other]},
    )
    seed(env["db"], "boundary", "2026-11-05")
    result = scoring_engine.compute_patient_score(
        "patient-test", env["db"], persist=False, as_of=datetime(2026, 11, 5)
    )
    pillar = result["pillars"]["cardio"]
    assert pillar["coverage"] == pytest.approx(coverage)
    assert pillar["confidence"] == confidence
    assert (pillar["score"] is None) == (coverage < 0.35)


def test_documented_global_example_and_penalty_cap():
    inputs = [(0.95, 78.4), (0.5, 79.1), (0.5, 86.2), (0.55, 71.3)]
    assert scoring_engine.aggregate_index(inputs, [flag(FlagSeverity.HIGH)]) == (
        78.5,
        5,
        73.5,
    )
    assert (
        scoring_engine.aggregate_index(inputs, [flag(FlagSeverity.CRITICAL)] * 4)[1]
        == 20
    )
    assert (
        scoring_engine.aggregate_index([(0.6, 3)], [flag(FlagSeverity.CRITICAL)])[-1]
        == 0
    )
    assert scoring_engine.aggregate_index([], []) == (None, 0, None)
    assert (
        scoring_engine.aggregate_index([(0.35, 71.349), (0.60, 89.946)], [])[-1] == 83.1
    )


def test_partial_catalogue_remains_blocked_even_with_flag(env):
    assert catalog_service.definition_complete is False
    env["monkeypatch"].setattr(settings, "CATALOG_CLINICALLY_APPROVED", True)
    env["monkeypatch"].setattr(settings, "ENVIRONMENT", "production")
    assert not scoring_engine.publication_allowed()
    assert scoring_engine.compute_patient_score("patient-test", env["db"]) is None


@pytest.mark.parametrize("weight", [0, -1, float("nan"), float("inf")])
def test_invalid_or_zero_denominator_never_publishes(env, weight):
    item = catalog_service.get_marker("glucose")
    item["pillar_weights"] = {"cardio": weight}
    env["monkeypatch"].setattr(catalog_service, "catalog_by_code", {"glucose": item})
    seed(env["db"], "invalid-weight", "2026-11-05")
    result = scoring_engine.compute_patient_score(
        "patient-test", env["db"], persist=False, as_of=datetime(2026, 11, 5)
    )
    assert result["lab_index"] is None
    assert result["pillars"]["cardio"]["score"] is None


def test_new_version_preserves_old_snapshot_and_excludes_wrong_units(env):
    old = {
        "snapshot_id": "legacy",
        "patient_id": "patient-test",
        "scoring_version": "score-v1.0",
    }
    env["db"].score_snapshots.insert_one(deepcopy(old))
    seed(env["db"], "valid-old", "2026-11-04")
    seed(env["db"], "invalid-new", "2026-11-05", unit_canonical="wrong")
    result = scoring_engine.compute_patient_score(
        "patient-test", env["db"], as_of=datetime(2026, 11, 5)
    )
    assert result["scoring_version"] == "score-v1.1"
    assert result["parameters"]["technical_only"] is True
    assert result["parameters"]["catalog_definition_complete"] is False
    assert result["input_markers"][0]["clinical_test_id"] == "valid-old"
    stored = env["db"].score_snapshots.find_one({"snapshot_id": "legacy"})
    assert all(stored[k] == v for k, v in old.items())
    assert env["db"].score_snapshots.count_documents({}) == 2


@pytest.mark.parametrize(
    "direction,value", [("lower_better", -10), ("higher_better", 1000)]
)
def test_directionality_does_not_penalize_opposite_side(direction, value):
    item = catalog_service.get_marker("glucose")
    item["directionality"] = direction
    subscore, warning = scoring_engine.calculate_subscore(
        "glucose", value, catalog_item=item
    )
    assert subscore == 100 and warning is None
