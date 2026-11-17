"""Connection only: schema/index changes are an explicit administrative operation."""
import logging
from pymongo import MongoClient
from fastapi import HTTPException
from app.config import settings
from app.tenancy import TenantDatabase

logger = logging.getLogger(__name__)
class MongoDB:
    client = None
    db = None
mongodb = MongoDB()

def connect_to_mongo():
    settings.validate_identity()
    mongodb.client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000,
                                 connectTimeoutMS=5000, tz_aware=False)
    mongodb.db = mongodb.client[settings.MONGODB_DB]
    hello = mongodb.client.admin.command("hello")
    if not hello.get("setName") and hello.get("msg") != "isdbgrid":
        raise RuntimeError("Replica set or sharded MongoDB required for clinical transactions")
    for collection, indexes in REQUIRED_INDEXES.items():
        found = mongodb.db[collection].index_information()
        expected = dict(INDEXES[collection])
        if any(name not in found or found[name].get("unique") is not True
               or list(found[name]["key"]) != expected[name] for name in indexes):
            raise RuntimeError("Tenant schema/index provisioning required; no automatic migration")
    logger.info("Database connection verified")

def close_mongo_connection():
    if mongodb.client is not None:
        mongodb.client.close()
        mongodb.db = None

def get_database():
    from app.dependencies.auth import current_identity
    user = current_identity.get()
    if user is None:
        raise HTTPException(401, detail={"code": "UNAUTHORIZED", "message": "Identity required"})
    if mongodb.db is None:
        raise HTTPException(503, detail={"code": "DATABASE_UNAVAILABLE", "message": "Database unavailable"})
    return TenantDatabase(mongodb.db, user.client_id)

# Compound tenant indexes replace historical global unique indexes only under a reviewed migration.
INDEXES = {
    "clinical_tests": [("tenant_test", [("client_id", 1), ("clinical_test_id", 1)]),
                       ("tenant_upload", [("client_id", 1), ("upload.upload_id", 1)]),
                       ("tenant_client_upload", [("client_id", 1), ("patient_id", 1), ("upload.client_upload_id", 1)]),
                       ("tenant_initiation_key", [("client_id", 1), ("patient_id", 1), ("upload.idempotency_key", 1)])],
    "clinical_test_extractions": [("tenant_extraction", [("client_id", 1), ("extraction_id", 1)])],
    "score_snapshots": [("tenant_snapshot", [("client_id", 1), ("snapshot_id", 1)])],
    "patient_access": [("tenant_patient", [("client_id", 1), ("patient_id", 1)])],
    "marker_catalog": [("tenant_catalog", [("client_id", 1), ("catalog_version", 1), ("marker_code", 1)])],
    "lab_report_exports": [("tenant_export", [("client_id", 1), ("export_id", 1)]),
                           ("tenant_export_idempotency", [("client_id", 1), ("patient_id", 1), ("clinician_id", 1), ("idempotency_key", 1)])],
    "request_limits": [("tenant_limit", [("client_id", 1), ("key", 1)])],
    "demo_objects": [("tenant_demo_object", [("client_id", 1), ("object_key", 1)]),
                      ("tenant_demo_capability", [("client_id", 1), ("capability_id", 1)])],
}
REQUIRED_INDEXES = {c: [name for name, _ in items] for c, items in INDEXES.items()}

def init_indexes(db):
    """Only for a new empty database. Never invoked at application startup."""
    if any(db[c].count_documents({}) for c in db.list_collection_names()):
        raise RuntimeError("Nonempty database: reviewed migration and backup required")
    from app.tenancy import COLLECTIONS
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name, validator={"$jsonSchema": {
                "bsonType": "object", "required": ["client_id"],
                "properties": {"client_id": {"bsonType": "string", "minLength": 1}}}})
    for collection, entries in INDEXES.items():
        for name, keys in entries:
            db[collection].create_index(keys, unique=True, name=name)
    db.clinical_markers.create_index([("client_id", 1), ("patient_id", 1), ("marker_code", 1), ("measured_on", -1)])
    db.score_snapshots.create_index([("client_id", 1), ("patient_id", 1), ("computed_at", -1)])

    db.request_limits.create_index("expires_at", expireAfterSeconds=0)
