"""Minimal clinical audit metadata; clinical values and tokens are never accepted."""
from datetime import datetime, timezone
from app.dependencies.auth import current_identity

ALLOWED_DETAILS = frozenset({"marker_code", "previous_status", "previous_extraction_id", "reprocess_number",
                             "corrections", "edit_count", "reason", "export_id", "metadata_changes"})

def audit(db, action, resource, resource_id, result="success", **details):
    user = current_identity.get()
    db.audit_events.insert_one({
        "event": action, "resource": resource, "resource_id": resource_id,
        "actor_id": user.sub if user else "worker", "actor_role": user.role if user else "system",
        "occurred_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "source": "api" if user else "worker", "result": result,
        **{k: v for k, v in details.items() if k in ALLOWED_DETAILS and k != "reason"},
    })
