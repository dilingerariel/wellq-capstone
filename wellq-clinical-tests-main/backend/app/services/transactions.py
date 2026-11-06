"""Transaction boundary for existing clinical write handlers."""
from functools import wraps
from datetime import datetime


def atomic_write(handler):
    @wraps(handler)
    async def wrapped(*args, **kwargs):
        db = kwargs["db"]
        with db.atomic():
            # Conflicting requests for a patient serialize via this write. A
            # transaction conflict is returned as retryable, never silently rerun
            # around external side effects such as signed URLs or PDF writes.
            from app.dependencies.auth import current_identity
            user = current_identity.get()
            patient = user.patient_id or kwargs.get("patient_id")
            if patient is None and kwargs.get("clinical_test_id"):
                doc = db.clinical_tests.find_one({"clinical_test_id": kwargs["clinical_test_id"], "deleted_at": None})
                patient = doc.get("patient_id") if doc else user.clinician_id
            key = "write:" + (patient or user.clinician_id)
            db.request_limits.update_one({"key": key}, {"$inc": {"revision": 1}}, upsert=True)
            return await handler(*args, **kwargs)
    return wrapped
