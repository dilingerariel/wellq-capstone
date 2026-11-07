"""Focused precondition regressions; real replica-set races live in the HTTP suite."""
from datetime import datetime, timedelta

from pymongo.errors import OperationFailure

from app.main import database_error
from app.services.clinical_version import clinical_version
from checks.test_edit_review import create


def test_snapshot_detects_changes_below_public_timestamp_precision(env, fake_storage):
    cid = create(env, True)
    db = env["db"]
    doc = db.clinical_tests.find_one({"clinical_test_id": cid})
    first = clinical_version(db, doc)
    db.clinical_tests.update_one({"clinical_test_id": cid}, {"$set": {"updated_at": datetime(2026, 1, 1)}})
    doc = db.clinical_tests.find_one({"clinical_test_id": cid})
    second = clinical_version(db, doc)
    db.clinical_tests.update_one({"clinical_test_id": cid}, {"$set": {"updated_at": doc["updated_at"] + timedelta(milliseconds=1)}})
    assert first != second != clinical_version(db, db.clinical_tests.find_one({"clinical_test_id": cid}))


def test_missing_and_stale_precondition_do_not_write(env, fake_storage):
    cid = create(env, True)
    client, db = env["client"], env["db"]
    headers = {"Authorization": "Bearer " + env["token"]("clinician", "doctor-1")}
    path = "/api/v1/clinical-tests/" + cid
    version = client.get(path, headers=headers).json()["clinical_version"]
    before = db.clinical_tests.find_one({"clinical_test_id": cid})
    assert client.patch(path + "/review", headers=headers, json={}).status_code == 428
    assert db.clinical_tests.find_one({"clinical_test_id": cid}) == before
    db.clinical_tests.update_one({"clinical_test_id": cid}, {"$set": {"title": "SYNTHETIC CHANGED"}})
    before = db.clinical_tests.find_one({"clinical_test_id": cid})
    assert client.patch(path + "/review", headers=headers, json={"expected_version": version}).status_code == 409
    assert db.clinical_tests.find_one({"clinical_test_id": cid}) == before
    assert db.audit_events.count_documents({"event": "clinical_test_reviewed"}) == 0


async def test_transient_mongo_write_conflict_is_http_conflict():
    error = OperationFailure("Synthetic write conflict", code=112, details={"errorLabels": ["TransientTransactionError"]})
    assert (await database_error(None, error)).status_code == 409
    assert (await database_error(None, OperationFailure("Synthetic dependency failure"))).status_code == 503
