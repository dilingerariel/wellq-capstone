"""Tenant-scoped monotonic source fence plus full report digest.

The existing unique (client_id, key) index in request_limits is reused; the fence
has no expires_at, so its TTL index never removes it. No schema migration.
"""
import hashlib
import json

from fastapi import HTTPException

SOURCE_KEY = "report-source-v1"
SOURCE_COLLECTIONS = frozenset({"clinical_tests", "clinical_test_extractions", "clinical_markers",
                                "score_snapshots", "marker_catalog", "patient_access"})


def revision(db):
    return (db.request_limits.find_one({"key": SOURCE_KEY}) or {}).get("revision", 0)


def publication_stamp():
    from app.services.catalog import catalog_service
    from app.services.scoring import scoring_engine
    return {"allowed": scoring_engine.publication_allowed(), "catalog_hash": catalog_service.content_hash(),
            "scoring_version": scoring_engine.scoring_version}


def version(db, report, publication):
    payload = {k: v for k, v in report.items() if k not in {"generated_at", "source_version"}}
    digest = hashlib.sha256(json.dumps({"tenant": db.client_id, "report": payload, "publication": publication},
                                     sort_keys=True, default=str).encode()).hexdigest()
    return f"rpt1:{revision(db)}:{digest}"


def conflict(code="EXPORT_SOURCE_CHANGED"):
    return HTTPException(409, detail={"code": code, "message": "Refresh the report before another export"})


def fence(db, expected):
    """Must run in the same transaction as the export's conditional write.

    This is an actual write, not a snapshot read. Concurrent clinical writes
    update the same document and cause a Mongo write conflict at one participant.
    Publication checks never advance the source revision or invalidate readers.
    """
    wanted = int(expected.split(":")[1])
    db.request_limits.update_one({"key": SOURCE_KEY}, {"$setOnInsert": {"revision": 0}}, upsert=True)
    result = db.request_limits.update_one({"key": SOURCE_KEY, "revision": wanted},
                                         {"$inc": {"publication_checks": 1}})
    if result.matched_count != 1:
        raise conflict()
