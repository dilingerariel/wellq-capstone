"""Clinical dates share one UTC clock; invalid dates never acquire a substitute."""
from datetime import date, datetime, timezone


class ClinicalDateError(ValueError):
    pass


def today():
    return datetime.now(timezone.utc).date()


def validate_clinical_date(value, as_of=None):
    if value is None:
        return None
    reference = as_of or today()
    if isinstance(reference, datetime):
        reference = reference.date()
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ClinicalDateError("Expected clinical date YYYY-MM-DD") from None
    if parsed.isoformat() != value or parsed > reference:
        raise ClinicalDateError("Clinical date must be YYYY-MM-DD and cannot be future")
    return value


def validate_extraction_dates(document, panels, as_of=None):
    for field in ("collection_date", "report_date"):
        validate_clinical_date(document.get(field), as_of)
    for panel in panels:
        validate_clinical_date(panel.get("collection_date"), as_of)
