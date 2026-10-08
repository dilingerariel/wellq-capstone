"""Batería de reproducibilidad del puntaje (§13.5: mismas entradas => mismas salidas).

1. Una implementación de REFERENCIA de la fórmula del §8.2, escrita aquí desde el documento y sin
   usar el código del motor, se compara con scoring_engine.calculate_subscore sobre una rejilla de
   valores (bordes y puntos medios de cada tramo) de cada marcador del catálogo.
2. Los ejemplos de la Tabla 20 del documento validan la propia implementación de referencia.
3. Prueba de integración: recalcular con las mismas entradas produce el mismo puntaje.
"""
import os
import sys
import time
import uuid

import httpx
import jwt
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.catalog import INITIAL_MARKER_CATALOG  # noqa: E402
from app.services.scoring import scoring_engine  # noqa: E402

BASE_URL = "http://localhost:8000/api/v1"
SECRET = "your-secret-key-here"
ALGORITHM = "HS256"
TOLERANCE = 0.06  # el motor redondea; aquí se comprueba la fórmula, no el modo de redondeo


def reference_subscore(direction, v, L, H, Ol, Oh, Cl, Ch):
    """Fórmula del §8.2.1 y §8.2.2 (L, H: rango normal; Ol, Oh: zona óptima; Cl, Ch: límites críticos)."""
    if direction == "lower_better":
        if v <= Oh:
            return 100.0
        if v <= H:
            return 100 - 30 * (v - Oh) / (H - Oh)
        if v <= Ch:
            return 70 - 70 * (v - H) / (Ch - H)
        return 0.0
    if direction == "higher_better":
        if v >= Ol:
            return 100.0
        if v >= L:
            return 100 - 30 * (Ol - v) / (Ol - L)
        if v >= Cl:
            return 70 - 70 * (L - v) / (L - Cl)
        return 0.0
    # two_sided
    if v < Cl or v > Ch:
        return 0.0
    if Ol <= v <= Oh:
        return 100.0
    if L <= v < Ol:
        return 100 - 30 * (Ol - v) / (Ol - L)
    if Oh < v <= H:
        return 100 - 30 * (v - Oh) / (H - Oh)
    if Cl <= v < L:
        return 70 - 70 * (L - v) / (L - Cl)
    return 70 - 70 * (v - H) / (Ch - H)  # H < v <= Ch


# ---------------------------------------------------------------- 2. Tabla 20 del documento
# (direction, valor, L, H, Ol, Oh, Cl, Ch, subscore esperado según la tabla)
TABLE_20 = [
    ("lower_better", 212, 0, 200, 0, 180, 0, 300, 61.6),     # colesterol total
    ("higher_better", 48, 40, 200, 55, 200, 25, 300, 86.0),   # HDL
    ("lower_better", 138, 0, 130, 0, 100, 0, 220, 63.8),      # LDL
    ("lower_better", 96, 0, 150, 0, 100, 0, 400, 100.0),      # triglicéridos
    ("lower_better", 5.4, 4.0, 5.7, 0, 5.4, 0, 9.0, 100.0),   # HbA1c
    ("higher_better", 22, 30, 100, 40, 60, 10, 150, 42.0),    # vitamina D
    ("lower_better", 4.1, 0, 5, 0, 1, 0, 30, 76.75),          # PCR (la tabla redondea a 76,8 / 76,7)
]


@pytest.mark.parametrize("direction,v,L,H,Ol,Oh,Cl,Ch,expected", TABLE_20)
def test_reference_implementation_matches_table_20(direction, v, L, H, Ol, Oh, Cl, Ch, expected):
    assert reference_subscore(direction, v, L, H, Ol, Oh, Cl, Ch) == pytest.approx(expected, abs=TOLERANCE)


# ---------------------------------------------------------------- 1. motor vs referencia
def _grid(item):
    ref, opt, crit = item["default_reference"], item["optimal_range"], item["critical_range"]
    L, H = ref["low"], ref["high"]
    Ol, Oh = opt["low"], opt["high"]
    Cl, Ch = crit["low"], crit["high"]
    points = [Cl - 1, Cl, (Cl + L) / 2, L, (L + Ol) / 2, Ol, (Ol + Oh) / 2, Oh,
              (Oh + H) / 2, H, (H + Ch) / 2, Ch, Ch + 1]
    return sorted({round(p, 3) for p in points if p >= 0}), (L, H, Ol, Oh, Cl, Ch)


CASES = [
    (item["marker_code"], item["directionality"], value)
    for item in INITIAL_MARKER_CATALOG
    for value in _grid(item)[0]
]


@pytest.mark.parametrize("marker_code,direction,value", CASES)
def test_engine_matches_reference_formula(marker_code, direction, value):
    item = next(i for i in INITIAL_MARKER_CATALOG if i["marker_code"] == marker_code)
    _, params = _grid(item)
    expected = reference_subscore(direction, value, *params)
    actual, _flag = scoring_engine.calculate_subscore(marker_code, value)
    assert actual == pytest.approx(expected, abs=TOLERANCE), f"{marker_code} v={value}"


def test_same_input_gives_same_output():
    """Determinismo: la batería completa, ejecutada dos veces, da exactamente lo mismo."""
    def run():
        return [scoring_engine.calculate_subscore(code, value)[0] for code, _d, value in CASES]
    assert run() == run()


def test_subscore_is_always_between_0_and_100():
    for code, _direction, value in CASES:
        score, _ = scoring_engine.calculate_subscore(code, value)
        assert 0.0 <= score <= 100.0, f"{code} v={value} => {score}"


# ---------------------------------------------------------------- 3. integración
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


def test_recomputing_with_the_same_inputs_gives_the_same_score(ctx):
    """El clínico "corrige" la hemoglobina al mismo valor que ya tenía: se genera un snapshot nuevo
    (trigger clinician_correction) cuyo puntaje debe ser idéntico al anterior."""
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    hc = {"Authorization": f"Bearer {ctx['token_c']}"}

    with httpx.Client(base_url=BASE_URL, timeout=40) as client:
        client_upload_id = f"upl_rep_{uuid.uuid4().hex[:8]}"
        r = client.post("/clinical-tests/uploads/initiate", json={
            "client_upload_id": client_upload_id, "file_name": "analitica.pdf", "mime_type": "application/pdf",
            "size_bytes": 1024000, "sha256": sha, "test_type": "blood_test",
            "title": "Analítica reproducibilidad", "test_date": "2026-09-28", "notes": "x",
        }, headers=_hp(ctx))
        assert r.status_code == 201
        upload_id, ct = r.json()["upload_id"], r.json()["clinical_test_id"]
        r = client.post(f"/clinical-tests/uploads/{upload_id}/complete", json={
            "client_upload_id": client_upload_id, "sha256": sha, "size_bytes": 1024000,
        }, headers=_hp(ctx))
        assert r.status_code == 200

        r = None
        for _ in range(40):
            time.sleep(0.5)
            r = client.get(f"/clinical-tests/{ct}/extraction", headers=_hp(ctx))
            if r.status_code != 409:
                break
        assert r.status_code == 200
        r = client.patch(f"/clinical-tests/{ct}/extraction", json={
            "action": "confirm", "extraction_id": r.json()["extraction_id"], "marker_edits": [],
        }, headers=_hp(ctx))
        assert r.status_code == 200

        r = client.post(f"/clinical-tests/{ct}/extraction/validate", json={
            "validation_status": "validated",
            "marker_corrections": [{"marker_code": "hemoglobin", "value_raw": "14.2", "unit_raw": "g/dL"}],
        }, headers=hc)
        assert r.status_code == 200

        r = client.get(f"/patients/{ctx['patient_id']}/lab-score?history=true", headers=hc)
        assert r.status_code == 200
        body = r.json()
        current, previous = body["current_snapshot"], body["history"][0]
        assert current["trigger"] == "clinician_correction"
        assert previous["trigger"] == "extraction_confirmed"
        assert current["snapshot_id"] != previous["snapshot_id"]

        for field in ("lab_index", "base_score", "penalty_applied", "scoring_version", "catalog_version"):
            assert current[field] == previous[field], field
        for name, pillar in current["pillars"].items():
            before = previous["pillars"][name]
            for field in ("score", "coverage", "confidence", "status"):
                assert pillar[field] == before[field], f"{name}.{field}"
            assert pillar["contributions"] == before["contributions"], f"{name}.contributions"