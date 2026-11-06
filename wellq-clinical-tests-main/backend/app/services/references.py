"""Resolve the actual reference without filling missing clinical bounds."""
import math
from copy import deepcopy


def effective_reference(catalog_item, reference=None):
    if reference is None:
        ref = {**deepcopy(catalog_item.get("default_reference") or {}),
               "unit": catalog_item.get("canonical_unit"), "source": "catalog"}
    else:
        if not isinstance(reference, dict):
            return {}, "INVALID_REFERENCE_RANGE"
        ref = deepcopy(reference)
    for key in ("low", "high"):
        value = ref.get(key)
        if value is not None:
            if isinstance(value, bool):
                return ref, "INVALID_REFERENCE_RANGE"
            try:
                value = float(value)
            except (TypeError, ValueError, OverflowError):
                return ref, "INVALID_REFERENCE_RANGE"
            if not math.isfinite(value):
                return ref, "INVALID_REFERENCE_RANGE"
            ref[key] = value
    if ref.get("low") is not None and ref.get("high") is not None and ref["low"] >= ref["high"]:
        return ref, "INVALID_REFERENCE_RANGE"
    if ref.get("unit") not in (None, catalog_item.get("canonical_unit")):
        return ref, "REFERENCE_UNIT_MISMATCH"
    if ref.get("source") == "none" or (ref.get("low") is None and ref.get("high") is None):
        return ref, "NO_REFERENCE_RANGE"
    return ref, None


def canonical_document_reference(reference, raw_unit, canonical_unit, factor):
    ref = deepcopy(reference)
    unit = ref.get("unit") or canonical_unit
    if unit not in (raw_unit, canonical_unit) or not canonical_unit:
        raise ValueError("REFERENCE_UNIT_MISMATCH")
    if unit == raw_unit and raw_unit != canonical_unit:
        for bound in ("low", "high"):
            if ref.get(bound) is not None:
                ref[bound] = round(ref[bound] * factor, 2)
    ref.update(unit=canonical_unit, source="document")
    return ref


def reference_status(value, catalog_item, reference=None):
    ref, error = effective_reference(catalog_item, reference)
    if error or value is None:
        return "indeterminate"
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return "indeterminate"
    if not math.isfinite(value):
        return "indeterminate"
    if ref.get("low") is not None and value < ref["low"]:
        return "low"
    if ref.get("high") is not None and value > ref["high"]:
        return "high"
    # A missing side is uncertainty, not evidence of normality.
    return "normal" if ref.get("low") is not None and ref.get("high") is not None else "indeterminate"
