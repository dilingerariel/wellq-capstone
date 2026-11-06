"""Offline metrics for an authorized reference corpus; does not call a model.

Inputs must be reviewed annotations, not generated clinical truth. No corpus is
bundled. A denominator of zero is reported as None, never perfect accuracy.
"""
def evaluate(reference, predictions):
    expected = {(d["document_id"], m["marker_code"]): m for d in reference for m in d["markers"]}
    proposed = {(d["document_id"], m["marker_code"]): m for d in predictions for m in d["markers"]}
    if len(expected) != sum(len(d["markers"]) for d in reference) or len(proposed) != sum(len(d["markers"]) for d in predictions):
        raise ValueError("Duplicate annotation keys")
    overlap = expected.keys() & proposed.keys()
    exact_values = sum(expected[k]["value"] == proposed[k]["value"] for k in overlap)
    exact_units = sum(expected[k]["unit"] == proposed[k]["unit"] for k in overlap)
    unsupported = len(proposed.keys() - expected.keys())
    def ratio(n, d): return n / d if d else None
    return {"expected_markers": len(expected), "proposed_markers": len(proposed),
            "coverage": ratio(len(overlap), len(expected)), "value_accuracy": ratio(exact_values, len(overlap)),
            "unit_accuracy": ratio(exact_units, len(overlap)),
            "unsupported_proposal_rate": ratio(unsupported, len(proposed)),
            "not_a_clinical_validation": True}
