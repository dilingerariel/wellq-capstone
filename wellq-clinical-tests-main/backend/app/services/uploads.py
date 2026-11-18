"""Upload session operations; transaction boundary lives in routes."""
import hashlib
import json
import uuid
from datetime import datetime
from fastapi import HTTPException
from app.config import settings
from app.services.storage import storage_service
from app.services.audit import audit
from app.services.associations import verify_associations
from app.services.upload_metadata import validate_metadata

def fail(code, status=409):
    raise HTTPException(status, detail={"code": code, "message": code})

def fingerprint(request):
    return hashlib.sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()

def response(doc, signed):
    return {"upload_id": doc["upload"]["upload_id"], "clinical_test_id": doc["clinical_test_id"],
            "status": doc["upload"]["status"], "upload": signed}

def initiate(request, key, patient, db):
    validate_metadata(request)
    if request.mime_type not in settings.ALLOWED_MIME_TYPES: fail("INVALID_METADATA", 422)
    if request.size_bytes > settings.MAX_CLINICAL_FILE_BYTES: fail("FILE_TOO_LARGE", 413)
    existing = db.clinical_tests.find_one({"patient_id": patient, "upload.client_upload_id": request.client_upload_id})
    key_owner = db.clinical_tests.find_one({"patient_id": patient, "upload.idempotency_key": key})
    if key_owner and (not existing or key_owner["_id"] != existing["_id"]): fail("IDEMPOTENCY_CONFLICT")
    if existing:
        if existing.get("deleted_at") or existing["upload"].get("request_hash") != fingerprint(request): fail("UPLOAD_CONFLICT")
        verify_associations(request.case_id, request.appointment_id, patient, db)
        return response(existing, existing["upload"]["initial_response"])
    verify_associations(request.case_id, request.appointment_id, patient, db)
    if db.clinical_tests.count_documents({"patient_id": patient, "deleted_at": None,
            "upload.status": {"$in": ["initiated", "processing"]}}) >= settings.MAX_PENDING_UPLOADS:
        fail("RATE_LIMITED", 429)
    identity = uuid.uuid4().hex
    clinical_id, upload_id = "ct_" + identity, "ctu_" + identity
    tenant_path = hashlib.sha256(db.client_id.encode()).hexdigest()
    object_key = f"quarantine/clinical-tests/{tenant_path}/{clinical_id}/original"
    signed = storage_service.generate_upload_url(object_key, request.mime_type,
        client_id=db.client_id, patient_id=patient, size_bytes=request.size_bytes, sha256=request.sha256)
    now = datetime.utcnow()
    doc = {"clinical_test_id": clinical_id, "patient_id": patient, "title": request.title,
        "test_type": request.test_type.value, "test_date": request.test_date, "patient_notes": request.notes,
        "case_id": request.case_id, "appointment_id": request.appointment_id, "ai_consent": request.ai_consent,
        "file": {"original_name": request.file_name, "mime_type": request.mime_type, "size_bytes": request.size_bytes,
                 "sha256": request.sha256, "gcs_object_key": object_key, "verified_at": None},
        "upload": {"upload_id": upload_id, "client_upload_id": request.client_upload_id, "idempotency_key": key,
            "request_hash": fingerprint(request), "initial_response": signed, "status": "initiated", "refresh_count": 0,
            "expires_at": signed["expires_at"], "validated_at": None, "rejection": None,
            "processing_status": {"malware_scan": "pending", "mime_validation": "pending"}},
        "review": {"status": "not_reviewed", "private_note": None},
        "created_at": now, "updated_at": now, "deleted_at": None}
    db.clinical_tests.insert_one(doc)
    audit(db, "upload_initiated", "clinical_test", clinical_id)
    return response(doc, signed)

def owned(upload_id, patient, db):
    doc = db.clinical_tests.find_one({"upload.upload_id": upload_id, "patient_id": patient, "deleted_at": None})
    if not doc: fail("UPLOAD_NOT_FOUND", 404)
    return doc

def refresh(upload_id, request, key, patient, db):
    doc = owned(upload_id, patient, db)
    if (doc["file"]["sha256"], doc["upload"]["client_upload_id"]) != (request.sha256, request.client_upload_id):
        fail("OBJECT_MISMATCH", 400)
    verify_associations(doc.get("case_id"), doc.get("appointment_id"), patient, db)
    slot = hashlib.sha256(key.encode()).hexdigest()
    previous = doc["upload"].get("refresh_responses", {}).get(slot)
    if previous: return {"upload_id": upload_id, "status": "initiated", "upload": previous}
    if doc["upload"]["status"] != "initiated": fail("UPLOAD_NOT_REFRESHABLE")
    if doc["upload"].get("refresh_count", 0) >= settings.MAX_URL_REFRESHES_PER_UPLOAD: fail("RATE_LIMITED", 429)
    signed = storage_service.generate_upload_url(doc["file"]["gcs_object_key"], doc["file"]["mime_type"],
        client_id=db.client_id, patient_id=patient, size_bytes=doc["file"]["size_bytes"], sha256=doc["file"]["sha256"])
    db.clinical_tests.update_one({"_id": doc["_id"]}, {"$inc": {"upload.refresh_count": 1},
        "$set": {"upload.refresh_responses." + slot: signed, "upload.expires_at": signed["expires_at"]}})
    return {"upload_id": upload_id, "status": "initiated", "upload": signed}

def complete(upload_id, request, key, patient, db):
    doc = owned(upload_id, patient, db)
    if (doc["file"]["sha256"], doc["file"]["size_bytes"], doc["upload"]["client_upload_id"]) != (request.sha256, request.size_bytes, request.client_upload_id):
        fail("OBJECT_MISMATCH", 400)
    current = doc["upload"]["status"]
    if current == "initiated":
        if settings.DEMO_MONGO_STORAGE_ENABLED:
            from app.database import mongodb
            stored = mongodb.db.demo_objects.find_one({"client_id": db.client_id,
                "object_key": doc["file"]["gcs_object_key"], "sha256": doc["file"]["sha256"],
                "size_bytes": doc["file"]["size_bytes"]})
            if (not stored or db.client_id != "clinica_alemana"
                    or stored.get("patient_id") != doc["patient_id"]):
                fail("OBJECT_NOT_UPLOADED")
            secure_key, secure_generation = storage_service.promote(
                doc["file"]["gcs_object_key"], stored["generation"], stored["sha256"])
            now = datetime.utcnow()
            db.clinical_tests.update_one({"_id": doc["_id"], "upload.status": "initiated"}, {"$set": {
                "file.gcs_object_key": secure_key, "file.generation": secure_generation, "file.verified_at": now,
                "upload.status": "ready_for_review", "upload.validated_at": now,
                "upload.processing_status": {"malware_scan": "not_applicable", "mime_validation": "passed"},
                "upload.job.status": "done", "extraction.status": "not_applicable", "updated_at": now,
            }})
            audit(db, "upload_verified_synthetic_demo", "clinical_test", doc["clinical_test_id"])
            current = "ready_for_review"
        else:
            db.clinical_tests.update_one({"_id": doc["_id"], "upload.status": "initiated"}, {"$set": {
                "upload.status": "processing", "upload.complete_key": key,
                "upload.job": {"status": "pending", "attempts": 0, "available_at": datetime.utcnow()}}})
            current = "processing"
            audit(db, "upload_completed", "clinical_test", doc["clinical_test_id"])
    elif current not in ("processing", "ready_for_review"):
        fail("UPLOAD_CONFLICT")
    return {"clinical_test_id": doc["clinical_test_id"], "upload_id": upload_id, "status": current,
            "local_file_can_be_deleted": False, "status_url": f"/api/v1/clinical-tests/uploads/{upload_id}/status"}

def upload_status(upload_id, patient, db):
    doc = owned(upload_id, patient, db)
    proc = doc["upload"]["processing_status"]
    fully_scanned = proc == {"malware_scan": "passed", "mime_validation": "passed"}
    fixed_synthetic = (settings.DEMO_MONGO_STORAGE_ENABLED and doc["file"].get("sha256") ==
        "3331e1f6f50397609563dacbdf46d5c6f41d3d530c9f8e3697d136915c4907a6" and
        proc == {"malware_scan": "not_applicable", "mime_validation": "passed"})
    safe = (doc["upload"]["status"] == "ready_for_review" and bool(doc["file"].get("verified_at"))
        and bool(doc["file"].get("generation")) and (fully_scanned or fixed_synthetic))
    at = doc["upload"].get("validated_at")
    return {"clinical_test_id": doc["clinical_test_id"], "upload_id": upload_id, "status": doc["upload"]["status"],
            "processing": proc, "local_file_can_be_deleted": safe, "error": doc["upload"].get("rejection"),
            "completed_at": at.strftime("%Y-%m-%dT%H:%M:%SZ") if at else None}
