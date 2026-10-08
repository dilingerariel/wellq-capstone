"""Pruebas unitarias del extractor (sin API): clasificación del documento (§5.2.3, §3.3.2) y
conservación de los marcadores que no superan la validación determinista (§5.2.5, §5.5.2)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.extractor import extraction_engine  # noqa: E402


@pytest.mark.parametrize("title", [
    "Carta clínica de seguimiento",
    "carta medica del cardiólogo",
    "Informe de alta hospitalaria",
    "Epicrisis 2026",
])
def test_clinical_letters_are_not_applicable(title):
    assert extraction_engine.classify_document({"title": title}) == "clinical_letter"


@pytest.mark.parametrize("title", [
    "Analítica Integral de Rutina",
    "Perfil Lipídico Inicial",
    "Hemograma Completo",
    "",
])
def test_lab_reports_are_applicable(title):
    assert extraction_engine.classify_document({"title": title}) is None


def test_valid_marker_is_normalized():
    m = extraction_engine.build_marker("hemoglobin", "Hemoglobina", "140", "g/L", 0.99, None, 1)
    assert m["validation"] == {"passed": True, "errors": []}
    assert m["value_raw"] == "140" and m["unit_raw"] == "g/L"      # se conservan los dos valores
    assert m["value_canonical"] == pytest.approx(14.0)
    assert m["unit_canonical"] == "g/dL"
    assert m["conversion_factor"] == pytest.approx(0.1)
    assert m["mapping_status"] == "mapped"


def test_unknown_unit_is_kept_unconverted_and_not_scored():
    """§5.5.2: unidad fuera de la tabla => no se convierte, no se puntúa, se muestra con su literal."""
    m = extraction_engine.build_marker("glucose", "Glucosa", "5.5", "litros", 0.98, None, 1)
    assert m["validation"]["passed"] is False
    assert m["validation"]["errors"] == ["UNIT_NOT_SUPPORTED"]
    assert m["value_raw"] == "5.5" and m["unit_raw"] == "litros"
    assert m["value_canonical"] is None and m["unit_canonical"] is None
    assert m["conversion_factor"] == 1.0
    assert m["confidence"] == {"value": 0.0, "unit": 0.0, "reference": 0.0, "name": 0.0}


def test_unmapped_marker_is_kept_with_its_literal_name():
    """§5.5.1: lo que no resuelve al catálogo queda unmapped, con su nombre literal."""
    m = extraction_engine.build_marker("no_existe_xyz", "Marcador raro", "7", "U/L", 0.9, None, 3)
    assert m["mapping_status"] == "unmapped"
    assert m["raw_name"] == "Marcador raro"
    assert m["validation"]["errors"] == ["UNKNOWN_MARKER"]
    assert m["value_canonical"] is None


def test_implausible_value_is_kept_and_flagged_not_dropped():
    m = extraction_engine.build_marker("hemoglobin", "Hemoglobina", "140", "g/dL", 0.9, None, 1)
    assert m["validation"]["errors"] == ["VALUE_IMPLAUSIBLE"]
    assert m["value_raw"] == "140"
    assert m["value_canonical"] is None