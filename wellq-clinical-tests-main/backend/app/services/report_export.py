"""Versioned PDF saga: reserve -> external immutable object -> conditional commit.

No signed link leaves this service before the final fenced transaction commits.
External objects are not rolled back by Mongo; failed attempts retain a private
orphan reference for reviewed reconciliation, never automatic deletion/re-upload.
"""
import hashlib
import time
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from pymongo.errors import PyMongoError
from starlette.concurrency import run_in_threadpool

from app.services.report_version import conflict, fence


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def active(user):
    # A long generation/upload must not publish a link after JWT expiration.
    from app.dependencies.auth import unauthorized
    if user.expires_at is not None and time.time() >= user.expires_at:
        raise unauthorized()


def audit(db, user, patient, export_id, result, code=None):
    db.audit_events.insert_one({"event": "lab_report_export" if result == "success" else "lab_report_export_failed",
        "resource": "lab-report", "patient_id": patient, "actor_role": user.role,
        "actor_id": user.clinician_id, "export_id": export_id, "result": result,
        "code": code, "occurred_at": now()})


def fail_attempt(db, user, patient, export_id, code):
    # Separate transaction after the failed phase has aborted, so audit survives.
    with db.atomic():
        states = ["pending", "stale", "committed"] if code == "EXPORT_SOURCE_CHANGED" else ["pending", "stale"]
        db.lab_report_exports.update_one({"export_id": export_id,
            "state": {"$in": states}, "failure_recorded": {"$ne": True}},
            {"$set": {"state": "stale" if code == "EXPORT_SOURCE_CHANGED" else "failed",
                      "failure_code": code, "failure_recorded": True, "finished_at": now()}})
        audit(db, user, patient, export_id, "failed", code)


async def export(patient, body, key, user, db, read_report, build, store, sign):
    params = body.model_dump(exclude={"expected_source_version"})
    expected = body.expected_source_version
    identity = {"patient_id": patient, "clinician_id": user.clinician_id, "idempotency_key": key}
    rec = None
    reserved = False
    try:
        # Source snapshot, expected version, fence and reservation share one txn.
        with db.atomic():
            active(user)
            report = await read_report(patient_id=patient, user=user, db=db,
                include_snapshot=True, **params)
            if expected is None:
                raise HTTPException(428, detail={"code": "EXPORT_VERSION_REQUIRED",
                    "message": "Read source_version and send expected_source_version"})
            rec = db.lab_report_exports.find_one(identity)
            if rec and (rec.get("params") != params or rec.get("source_version") != expected):
                raise conflict("IDEMPOTENCY_CONFLICT")
            if report["source_version"] != expected:
                raise conflict()
            fence(db, expected)
            if rec:
                if rec.get("state") == "pending":
                    if rec["lease_until"] <= now():
                        raise conflict("EXPORT_ATTEMPT_EXPIRED")
                    raise HTTPException(409, detail={"code": "EXPORT_IN_PROGRESS", "message": "Retry the same key explicitly"},
                                        headers={"Retry-After": "1"})
                if rec.get("state") != "committed":
                    raise conflict("EXPORT_ATTEMPT_FAILED" if rec.get("state") == "failed" else "EXPORT_SOURCE_CHANGED")
            else:
                export_id = "lrx_" + uuid.uuid4().hex
                stamp = now()
                rec = {**identity, "export_id": export_id, "params": params, "source_version": expected,
                    "state": "pending", "created_at": stamp, "lease_until": stamp + timedelta(seconds=120),
                    "object_key": "private/lab-reports/" + hashlib.sha256(db.client_id.encode()).hexdigest() + "/" + export_id + ".pdf",
                    "file_name": f"lab-report_{patient}_{stamp.strftime('%Y%m%d')}.pdf"}
                db.lab_report_exports.insert_one(rec)
                reserved = True
        # No Mongo transaction/session spans CPU work, object upload or signing.
        if reserved:
            try:
                pdf = await run_in_threadpool(build, report, patient, user.clinician_id)
            except ImportError:
                raise HTTPException(503, detail={"code": "PDF_ENGINE_UNAVAILABLE", "message": "PDF engine unavailable"})
            except Exception:  # noqa: BLE001 - Bound every third-party generation/storage failure before publishing.
                raise HTTPException(503, detail={"code": "PDF_GENERATION_FAILED", "message": "PDF generation failed"})
            rec.update({"size_bytes": len(pdf), "sha256": hashlib.sha256(pdf).hexdigest(), "storage": "gcs"})
            try:
                rec["storage"] = await run_in_threadpool(store, rec["object_key"], pdf)
            except Exception:  # noqa: BLE001 - Bound every third-party generation/storage failure before publishing.
                raise HTTPException(502, detail={"code": "STORAGE_ERROR", "message": "PDF storage failed"})
            with db.atomic():
                active(user)
                fresh = await read_report(patient_id=patient, user=user, db=db, include_snapshot=True, **params)
                if fresh["source_version"] != expected:
                    raise conflict()
                fence(db, expected)
                changed = db.lab_report_exports.update_one({"export_id": rec["export_id"], "state": "pending",
                    "source_version": expected, "lease_until": {"$gt": now()}},
                    {"$set": {"state": "committed", "size_bytes": rec["size_bytes"],
                              "sha256": rec["sha256"], "storage": rec["storage"], "committed_at": now()}})
                if changed.matched_count != 1:
                    raise conflict()
                audit(db, user, patient, rec["export_id"], "success")
        response = await run_in_threadpool(sign, rec, not reserved)
        # A signature is not publication: recheck after signing, then commit.
        with db.atomic():
            active(user)
            current = await read_report(patient_id=patient, user=user, db=db, include_snapshot=True, **params)
            if current["source_version"] != expected:
                raise conflict()
            fence(db, expected)
            checked = db.lab_report_exports.update_one({"export_id": rec["export_id"],
                "state": "committed", "source_version": expected}, {"$set": {"verified_at": now()}})
            if checked.matched_count != 1:
                raise conflict()
            response.update({"source_version": expected, "verified_at": now().isoformat() + "Z"})
        return response
    except (HTTPException, PyMongoError) as exc:
        code = exc.detail.get("code", "EXPORT_FAILED") if isinstance(exc, HTTPException) and isinstance(exc.detail, dict) else "RETRYABLE_CONFLICT"
        if reserved or (rec and code == "EXPORT_ATTEMPT_EXPIRED"):
            fail_attempt(db, user, patient, rec["export_id"], code)
        else:
            # Failed preconditions and denied/in-progress attempts are observable
            # without changing an existing successful export or its success audit.
            audit(db, user, patient, rec.get("export_id") if rec else None, "failed", code)
        raise
