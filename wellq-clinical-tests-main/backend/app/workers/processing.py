"""Mongo embedded outbox worker. No thread/in-memory queue claims durability.

Run explicitly with python -m app.workers.processing after reviewed provisioning.
An atomic lease fences final DB writes. GCS effects use immutable generations.
"""
import time
import uuid
from datetime import datetime, timedelta
from pymongo import ReturnDocument
from app.config import settings
from app.database import mongodb, connect_to_mongo
from app.tenancy import TenantDatabase
from app.services.storage import storage_service
from app.services.file_validation import validate_document, scanner, FileRejected
from app.services.extractor import extraction_engine
from app.services.audit import audit
from app.services.clinical_dates import ClinicalDateError

def run_once(raw_db, kind="upload", now=None):
    now = now or datetime.utcnow()
    field = "upload.job" if kind == "upload" else "extraction_job"
    token = uuid.uuid4().hex
    terminal = {field + ".status": "failed", field + ".error_code": "RETRY_EXHAUSTED"}
    terminal["upload.status" if kind == "upload" else "extraction.status"] = "failed" if kind == "upload" else "extraction_failed"
    raw_db.clinical_tests.update_many({"client_id": {"$type": "string"}, "deleted_at": None,
        field + ".status": "running", field + ".lease_until": {"$lte": now},
        field + ".attempts": {"$gte": settings.JOB_MAX_ATTEMPTS}}, {"$set": terminal})
    query = {"client_id": {"$type": "string"}, "deleted_at": None,
             field + ".attempts": {"$lt": settings.JOB_MAX_ATTEMPTS}, "$or": [
                {field + ".status": "pending", field + ".available_at": {"$lte": now}},
                {field + ".status": "running", field + ".lease_until": {"$lte": now}}]}
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
            scanner.scan(data)
            secure_key, secure_generation = storage_service.promote(expected, generation, file["sha256"])
            fence[field + ".lease_until"] = {"$gt": datetime.utcnow()}
            with db.atomic():
                if not db.clinical_tests.find_one(fence):
                    return True
                fields = {"file.gcs_object_key": secure_key, "file.generation": secure_generation,
                    "file.verified_at": now, "upload.validated_at": now, "upload.status": "ready_for_review",
                    "upload.processing_status": {"malware_scan": "passed", "mime_validation": "passed"},
                    field + ".status": "done", "extraction.status": "queued" if doc.get("ai_consent") else "not_applicable"}
                if doc.get("ai_consent"):
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
                db.clinical_tests.update_one(live, {"$set": {field + ".status": "done"}})
                audit(db, "document_extracted", "extraction", extraction["extraction_id"])
    except Exception as exc:
        # Persist only a bounded code, never exception/provider/file content.
        rejected = isinstance(exc, FileRejected)
        job = doc["upload"]["job"] if kind == "upload" else doc["extraction_job"]
        exhausted = job["attempts"] >= settings.JOB_MAX_ATTEMPTS
        invalid_date = isinstance(exc, ClinicalDateError)
        status = "failed" if rejected or exhausted or invalid_date else "pending"
        safe_codes = {"SIZE_REJECTED", "OBJECT_MISMATCH", "MIME_MISMATCH", "CONTENT_INVALID",
                      "DOCUMENT_CORRUPT", "MALWARE_DETECTED", "OBJECT_OWNERSHIP_MISMATCH"}
        code = str(exc) if rejected and str(exc) in safe_codes else "FILE_REJECTED" if rejected else "DEPENDENCY_UNAVAILABLE"
        if invalid_date:
            code = "INVALID_CLINICAL_DATE"
        changes = {field + ".status": status, field + ".error_code": code,
                   field + ".available_at": now + timedelta(seconds=min(3600, 2 ** job["attempts"]) + __import__("secrets").randbelow(3))}
        if kind == "upload" and status == "failed":
            changes["upload.status"] = "rejected" if rejected else "failed"
            changes["upload.rejection"] = {"code": "FILE_REJECTED" if rejected else "DEPENDENCY_UNAVAILABLE"}
        elif kind != "upload":
            changes["extraction.status"] = "extraction_failed" if status == "failed" else "queued"
        # A commit may have succeeded even when its acknowledgement was lost.
        # Never downgrade a committed 'done' job back to pending in that case.
        db.clinical_tests.update_one({"_id": doc["_id"], field + ".lease_token": token,
                                     field + ".status": "running"}, {"$set": changes})
    return True

def main():
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
