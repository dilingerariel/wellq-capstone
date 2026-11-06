"""Refuse arbitrary hosts/databases before any integration write."""
import os
from pymongo import MongoClient


def environment():
    project = os.environ.get("WELLQ_INTEGRATION_PROJECT", "")
    run = os.environ.get("WELLQ_INTEGRATION_RUN", "")
    db = os.environ.get("MONGODB_DB", "")
    uri = os.environ.get("MONGODB_URI", "")
    if (os.environ.get("ENVIRONMENT") != "test" or not project.startswith("wellq-int-")
        or not run or db != "wellq_integration_" + run
        or "@mongo-int:27017/" + db + "?" not in uri
        or "replicaSet=wellqIntRs" not in uri or "authSource=" + db not in uri):
        raise RuntimeError("Integration identity/configuration mismatch; no connection permitted")
    return project, run, db, uri


def database():
    project, run, name, uri = environment()
    client = MongoClient(uri, serverSelectionTimeoutMS=4000, connectTimeoutMS=4000)
    db = client[name]
    marker = db["__integration_identity"].find_one({"_id": "ownership"})
    if not marker or marker.get("project") != project or marker.get("run") != run:
        client.close()
        raise RuntimeError("Integration database ownership not established")
    hello = client.admin.command("hello")
    if hello.get("setName") != "wellqIntRs":
        raise RuntimeError("Unexpected integration replica set")
    return db
