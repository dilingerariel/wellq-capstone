"""Mongo embedded outbox worker. No thread/in-memory queue claims durability.

Run explicitly with python -m app.workers.processing after reviewed provisioning.
An atomic lease fences final DB writes. GCS effects use immutable generations.
"""
import time
import uuid
import logging
from datetime import datetime, timedelta
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError
from fastapi import HTTPException
from app.config import settings
from app.database import mongodb, connect_to_mongo
from app.tenancy import TenantDatabase
from app.services.storage import storage_service
from app.services.file_validation import validate_document, scanner, FileRejected
from app.services.extractor import extraction_engine
from app.services.audit import audit
from app.services.clinical_dates import ClinicalDateError

logger = logging.getLogger(__name__)

def run_once(raw_db, kind="upload", now=None, clinical_test_id=None):
    now = now or datetime.utcnow()
    field = "upload.job" if kind == "upload" else "extraction_job"
    token = uuid.uuid4().hex
    terminal = {field + ".status": "failed", field + ".error_code": "RETRY_EXHAUSTED"}
    terminal["upload.status" if kind == "upload" else "extraction.status"] = "failed" if kind == "upload" else "extraction_failed"
    expired_query = {"client_id": {"$type": "string"}, "deleted_at": None,
        field + ".status": "running", field + ".lease_until": {"$lte": now},
        field + ".attempts": {"$gte": settings.JOB_MAX_ATTEMPTS}}
    query = {"client_id": {"$type": "string"}, "deleted_at": None,
             field + ".attempts": {"$lt": settings.JOB_MAX_ATTEMPTS}, "$or": [
                {field + ".status": "pending", field + ".available_at": {"$lte": now}},
                {field + ".status": "running", field + ".lease_until": {"$lte": now}}]}
    if clinical_test_id is not None:
        expired_query["clinical_test_id"] = clinical_test_id
        query["clinical_test_id"] = clinical_test_id
    raw_db.clinical_tests.update_many(expired_query, {"$set": terminal})
    doc = raw_db.clinical_tests.find_one_and_update(query,
        {"$set": {field + ".status": "running", field + ".lease_token": token,
                   field + ".lease_until": now + timedelta(seconds=settings.JOB_LEASE_SECONDS)},
         "$inc": {field + ".attempts": 1}}, return_document=ReturnDocument.AFTER)
    if not doc:
        return False
    db = TenantDatabase(raw_db, doc["client_id"])
    fence = {"_id": doc["_id"], "deleted_at": None, field + ".lease_token": token,
             field + ".lease_until": {"$gt": datetime.utcnow()}}
    try:
        if kind == "upload":
            file = doc["file"]
            tenant_path = __import__("hashlib").sha256(db.client_id.encode()).hexdigest()
            expected = f"quarantine/clinical-tests/{tenant_path}/{doc['clinical_test_id']}/original"
            if file["gcs_object_key"] != expected:
                raise FileRejected("OBJECT_OWNERSHIP_MISMATCH")
            data, content_type, generation = storage_service.read_object(expected)
            validate_document(data, content_type, file["size_bytes"], file["sha256"])
            if content_type != file["mime_type"]:
                raise FileRejected("MIME_MISMATCH")
            scanner.scan_document(data, content_type)
            secure_key, secure_generation = storage_service.promote(expected, generation, file["sha256"])
            fence[field + ".lease_until"] = {"$gt": datetime.utcnow()}
            with db.atomic():
                if not db.clinical_tests.find_one(fence):
                    return True
                clinical_ai_enabled = bool(doc.get("ai_consent") and (
                    settings.ENVIRONMENT != "production" or (
                        settings.AI_PROVIDER_APPROVED and settings.AI_PROVIDER == "vertex_ai"
                        and settings.AI_CLINICAL_DATA_APPROVED and settings.VERTEX_AI_PROJECT_ID
                        and settings.VERTEX_AI_LOCATION and settings.VERTEX_AI_MODEL_ID)))
                fields = {"file.gcs_object_key": secure_key, "file.generation": secure_generation,
                    "file.verified_at": now, "upload.validated_at": now, "upload.status": "ready_for_review",
                    "upload.processing_status": {"malware_scan": "passed", "mime_validation": "passed"},
                    field + ".status": "done", "extraction.status": "queued" if clinical_ai_enabled else "not_applicable"}
                if clinical_ai_enabled:
                    fields["extraction_job"] = {"status": "pending", "attempts": 0, "available_at": now}
                db.clinical_tests.update_one(fence, {"$set": fields})
                audit(db, "upload_verified", "clinical_test", doc["clinical_test_id"])
        else:
            with db.atomic():
                if not db.clinical_tests.find_one(fence):
                    return True
                extraction = extraction_engine.run_extraction_pipeline(doc["clinical_test_id"], db)
                # Provider latency must not allow an expired lease to commit output.
                live = dict(fence); live[field + ".lease_until"] = {"$gt": datetime.utcnow()}
                if not db.clinical_tests.find_one(live):
                    raise RuntimeError("Extraction lease expired")
                db.clinical_tests.update_one(live, {"$set": {field + ".status": "done"},
                                                    "$unset": {field + ".error_code": "",
                                                               field + ".available_at": ""}})
                audit(db, "document_extracted", "extraction", extraction["extraction_id"])
    except Exception as exc:
        # Persist only a bounded code, never exception/provider/file content.
        rejected = isinstance(exc, FileRejected)
        job = doc["upload"]["job"] if kind == "upload" else doc["extraction_job"]
        exhausted = job["attempts"] >= settings.JOB_MAX_ATTEMPTS
        invalid_date = isinstance(exc, ClinicalDateError)
        provider_code = getattr(exc, "safe_code", None)
        provider_retryable = getattr(exc, "retryable", True)
        http_detail = exc.detail if isinstance(exc, HTTPException) and isinstance(exc.detail, dict) else {}
        storage_unavailable = http_detail.get("code") == "STORAGE_UNAVAILABLE"
        output_invalid = exc.__class__.__name__ == "ValidationError"
        extraction_unavailable = exc.__class__.__name__ == "ExtractionUnavailable"
        database_unavailable = isinstance(exc, PyMongoError)
        terminal_provider_error = provider_code is not None and not provider_retryable
        status = "failed" if (rejected or exhausted or invalid_date or terminal_provider_error
                               or output_invalid) else "pending"
        safe_codes = {"SIZE_REJECTED", "OBJECT_MISMATCH", "MIME_MISMATCH", "CONTENT_INVALID",
                      "DOCUMENT_CORRUPT", "MALWARE_DETECTED", "OBJECT_OWNERSHIP_MISMATCH"}
        if rejected:
            code = str(exc) if str(exc) in safe_codes else "FILE_REJECTED"
        elif provider_code:
            code = provider_code
        elif storage_unavailable:
            code = "STORAGE_UNAVAILABLE"
        elif database_unavailable:
            code = "DATABASE_UNAVAILABLE"
        elif extraction_unavailable:
            code = "EXTRACTION_PREREQUISITE_FAILED"
        elif output_invalid:
            code = "EXTRACTION_OUTPUT_INVALID"
        else:
            code = "DEPENDENCY_UNAVAILABLE"
        if invalid_date:
            code = "INVALID_CLINICAL_DATE"
        logger.warning("WellQ %s job failed with safe code %s and type %s",
                       kind, code, type(exc).__name__)
        changes = {field + ".status": status, field + ".error_code": code,
                   field + ".available_at": now + timedelta(seconds=min(3600, 2 ** job["attempts"]) + __import__("secrets").randbelow(3))}
        if kind == "upload" and status == "failed":
            changes["upload.status"] = "rejected" if rejected else "failed"
            changes["upload.rejection"] = {"code": "FILE_REJECTED" if rejected else "DEPENDENCY_UNAVAILABLE"}
        elif kind != "upload":
            changes["extraction.status"] = "extraction_failed" if status == "failed" else "queued"
        # A commit may have succeeded even when its acknowledgement was lost.
        # Never downgrade a committed 'done' job back to pending in that case.
        recovery = {"_id": doc["_id"], field + ".lease_token": token, field + ".status": "running"}
        if db.clinical_tests.find_one(recovery):
            db.clinical_tests.update_one(recovery, {"$set": changes})
    return True

def main():
    settings.validate_clinical_services()
    connect_to_mongo()
    try:
        while True:
            did_work = run_once(mongodb.db, "upload")
            did_work = run_once(mongodb.db, "extraction") or did_work
            if not did_work:
                time.sleep(1)
    finally:
        if mongodb.client is not None:
            mongodb.client.close()

if __name__ == "__main__":
    main()
