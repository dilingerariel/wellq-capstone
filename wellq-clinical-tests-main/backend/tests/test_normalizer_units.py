"""Pruebas unitarias del normalizador (§5.5, criterio §13.3: "pruebas unitarias que cubren cada factor
de conversión del catálogo"). No usan la API: llaman directamente a catalog_service.

Los factores esperados están escritos aquí, independientes del código:
  - SPEC: los del §5.5.2 del Documento Maestro (colesterol 38,67; glucosa 18,016; vitamina D 0,4; hemoglobina 0,1)
    y el ejemplo de catálogo del §6 (vitamina D: ug/L = 1,0).
  - CATALOGO_V1: el resto de factores del catálogo v1, pendientes de validación clínica (se fijan aquí
    para que cualquier cambio sea deliberado y quede en revisión).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.catalog import INITIAL_MARKER_CATALOG, catalog_service  # noqa: E402

SPEC = "spec"
CATALOGO_V1 = "catalogo_v1"

# (marker_code, unidad, factor esperado, origen)
EXPECTED_FACTORS = [
    ("cholesterol_total", "mg/dL", 1.0, SPEC),
    ("cholesterol_total", "mmol/L", 38.67, SPEC),
    ("ldl_cholesterol", "mg/dL", 1.0, CATALOGO_V1),
    ("ldl_cholesterol", "mmol/L", 38.67, CATALOGO_V1),
    ("hdl_cholesterol", "mg/dL", 1.0, CATALOGO_V1),
    ("hdl_cholesterol", "mmol/L", 38.67, CATALOGO_V1),
    ("triglycerides", "mg/dL", 1.0, CATALOGO_V1),
    ("triglycerides", "mmol/L", 88.57, CATALOGO_V1),
    ("glucose", "mg/dL", 1.0, SPEC),
    ("glucose", "mmol/L", 18.016, SPEC),
    ("creatinine", "mg/dL", 1.0, CATALOGO_V1),
    ("creatinine", "umol/L", 0.0113, CATALOGO_V1),
    ("creatinine", "µmol/L", 0.0113, CATALOGO_V1),
    ("hemoglobin", "g/dL", 1.0, SPEC),
    ("hemoglobin", "g/L", 0.1, SPEC),
    ("vitamin_d", "ng/mL", 1.0, SPEC),
    ("vitamin_d", "ug/L", 1.0, SPEC),
    ("vitamin_d", "nmol/L", 0.4, SPEC),
    ("calcium", "mg/dL", 1.0, CATALOGO_V1),
    ("calcium", "mmol/L", 4.0, CATALOGO_V1),
    ("crp_high_sensitivity", "mg/L", 1.0, CATALOGO_V1),
    ("crp_high_sensitivity", "mg/dL", 10.0, CATALOGO_V1),
]


def test_every_catalog_factor_has_a_test_and_vice_versa():
    """Si alguien agrega o quita un factor en el catálogo sin tocar estas pruebas, esta prueba falla."""
    in_catalog = {
        (item["marker_code"], unit)
        for item in INITIAL_MARKER_CATALOG
        for unit in item["unit_conversions"]
    }
    in_tests = {(code, unit) for code, unit, _, _ in EXPECTED_FACTORS}
    assert in_catalog == in_tests

    # y todas las unidades admitidas tienen factor de conversión declarado
    for item in INITIAL_MARKER_CATALOG:
        assert set(item["supported_units"]) == set(item["unit_conversions"]), item["marker_code"]


@pytest.mark.parametrize("code,unit,factor,origin", EXPECTED_FACTORS)
def test_conversion_factor(code, unit, factor, origin):
    marker = catalog_service.get_marker(code)
    assert marker["unit_conversions"][unit] == pytest.approx(factor, rel=1e-9), f"{code} {unit} ({origin})"


# Valores típicos en unidad alternativa: deben convertirse y NO rechazarse como implausibles
# (la plausibilidad se evalúa sobre el valor ya convertido a la unidad canónica).
# (marker_code, valor, unidad, valor canónico esperado)
TYPICAL_VALUES = [
    ("cholesterol_total", "5.2", "mmol/L", 201.08),
    ("ldl_cholesterol", "3.4", "mmol/L", 131.48),
    ("hdl_cholesterol", "1.3", "mmol/L", 50.27),
    ("triglycerides", "1.7", "mmol/L", 150.57),
    ("glucose", "5.5", "mmol/L", 99.09),
    ("creatinine", "88", "umol/L", 0.99),
    ("creatinine", "88", "µmol/L", 0.99),
    ("hemoglobin", "140", "g/L", 14.0),
    ("vitamin_d", "75", "nmol/L", 30.0),
    ("vitamin_d", "32.5", "ug/L", 32.5),
    ("calcium", "2.4", "mmol/L", 9.6),
    ("crp_high_sensitivity", "0.5", "mg/dL", 5.0),
]


@pytest.mark.parametrize("code,value,unit,expected", TYPICAL_VALUES)
def test_typical_value_in_alternative_unit_is_converted(code, value, unit, expected):
    r = catalog_service.validate_and_convert(code, value, unit)
    assert r["valid"] is True, r
    assert r["value_canonical"] == pytest.approx(expected, abs=0.01)
    assert r["unit_canonical"] == catalog_service.get_marker(code)["canonical_unit"]
    assert r["conversion_factor"] == catalog_service.get_marker(code)["unit_conversions"][unit]
    assert r["value_raw"] == str(float(value))  # se conserva el valor literal
    assert r["unit_raw"] == unit                # y la unidad literal


def test_decimal_comma_is_accepted():
    r = catalog_service.validate_and_convert("cholesterol_total", "5,2", "mmol/L")
    assert r["valid"] is True
    assert r["value_canonical"] == pytest.approx(201.08, abs=0.01)


def test_unit_outside_conversion_table_is_not_converted():
    """§5.5.2 regla estricta: una unidad que no está en la tabla no se convierte ni se puntúa."""
    for unit in ("litros", "mg/dl", "mmol", ""):
        r = catalog_service.validate_and_convert("glucose", "5.5", unit)
        assert r["valid"] is False
        assert r["error_code"] == "UNIT_NOT_SUPPORTED"
        assert "value_canonical" not in r


def test_unknown_marker_is_rejected():
    r = catalog_service.validate_and_convert("no_existe_xyz", "1", "mg/dL")
    assert r["valid"] is False
    assert r["error_code"] == "UNKNOWN_MARKER"


@pytest.mark.parametrize("code,value,unit", [
    ("hemoglobin", "9999", "g/dL"),
    ("hemoglobin", "0.5", "g/dL"),
    ("glucose", "5000", "mg/dL"),
    ("cholesterol_total", "50", "mmol/L"),   # 50 mmol/L = 1933 mg/dL: implausible tras convertir
])
def test_implausible_values_are_rejected(code, value, unit):
    r = catalog_service.validate_and_convert(code, value, unit)
    assert r["valid"] is False
    assert r["error_code"] == "VALUE_IMPLAUSIBLE"


def test_non_numeric_value_is_rejected():
    r = catalog_service.validate_and_convert("glucose", "abc", "mg/dL")
    assert r["valid"] is False
    assert r["error_code"] == "VALUE_INVALID_FORMAT"


@pytest.mark.parametrize("code,value,unit,censoring,limit", [
    ("crp_high_sensitivity", "< 0,3", "mg/L", "left", 0.3),
    ("crp_high_sensitivity", "<0.3", "mg/L", "left", 0.3),
    ("cholesterol_total", "> 500", "mg/dL", "right", 500.0),
    ("cholesterol_total", ">500", "mg/dL", "right", 500.0),
])
def test_censored_values_keep_the_limit_and_the_censoring(code, value, unit, censoring, limit):
    """§5.4: «< 0,3» / «> 500» se guardan con el límite y censoring left | right."""
    r = catalog_service.validate_and_convert(code, value, unit)
    assert r["valid"] is True, r
    assert r["censoring"] == censoring
    assert r["value_canonical"] == pytest.approx(limit, abs=0.01)


def test_uncensored_value_has_no_censoring():
    r = catalog_service.validate_and_convert("glucose", "92", "mg/dL")
    assert r["valid"] is True
    assert r["censoring"] is None


def test_reference_comes_from_the_catalog_with_its_source():
    """§5.5.3: sin rango impreso en el documento, se usa el del catálogo y se registra la fuente."""
    r = catalog_service.validate_and_convert("hemoglobin", "14.2", "g/dL")
    assert r["reference"]["source"] == "catalog"
    assert (r["reference"]["low"], r["reference"]["high"]) == (12.0, 17.5)
    assert r["reference"]["unit"] == "g/dL"
    assert r["status"] == "normal"


@pytest.mark.parametrize("code,value,unit,status", [
    ("hemoglobin", "11.0", "g/dL", "low"),
    ("hemoglobin", "14.0", "g/dL", "normal"),
    ("hemoglobin", "18.5", "g/dL", "high"),
])
def test_status_against_reference_range(code, value, unit, status):
    assert catalog_service.validate_and_convert(code, value, unit)["status"] == status