"""Opaque precondition over the existing document and current extraction snapshot."""
import hashlib

from bson.json_util import dumps
from fastapi import HTTPException


def clinical_version(db, doc, extraction=None):
    extraction_id = (doc.get("extraction") or {}).get("extraction_id")
    if extraction is None and extraction_id:
        extraction = db.clinical_test_extractions.find_one({"extraction_id": extraction_id})
    # Sorted BSON JSON preserves the stored millisecond timestamp precision.
    # No migration or timestamp truncation; workers and older document edits also
    # invalidate the token. The snapshot itself never leaves the server here.
    encoded = dumps({"document": doc, "extraction": extraction}, sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def require_clinical_version(db, doc, expected, extraction=None):
    if expected is None:
        raise HTTPException(428, detail={"code": "CLINICAL_VERSION_REQUIRED",
                                       "message": "Read the current clinical version before writing"})
    if expected != clinical_version(db, doc, extraction):
        raise HTTPException(409, detail={"code": "CLINICAL_VERSION_CONFLICT",
                                       "message": "Clinical data changed; read the current version"})
