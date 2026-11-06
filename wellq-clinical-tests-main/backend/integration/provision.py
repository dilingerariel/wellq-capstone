import os
import secrets
import base64
import re
import sys
import time
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from integration.guard import environment


def files():
    assert os.environ.get("WELLQ_INTEGRATION_PROJECT", "").startswith("wellq-int-")
    key = Path("/mongo-key/keyfile")
    if not key.exists() or not re.fullmatch(r"[A-Za-z0-9+/=\s]+", key.read_text()):
        key.write_text(base64.b64encode(secrets.token_bytes(512)).decode())
    os.chown(key, 999, 999)
    key.chmod(0o400)
    Path("/synthetic-store").mkdir(exist_ok=True)
    os.chown("/synthetic-store", 10001, 10001)
    print("Exclusive integration file volumes prepared")


def provision():
    project, run, name, _ = environment()
    client = MongoClient("mongodb://mongo-int:27017/?directConnection=true", username="integration_root",
                         password=os.environ["WELLQ_ROOT_PASSWORD"], authSource="admin", serverSelectionTimeoutMS=2000)
    for attempt in range(90):
        try:
            client.admin.command("ping")
            break
        except PyMongoError:
            time.sleep(1)
    else:
        raise RuntimeError("New integration Mongo did not become available")
    hello = client.admin.command("hello")
    if not hello.get("setName"):
        client.admin.command("replSetInitiate", {"_id": "wellqIntRs", "members": [{"_id": 0, "host": "mongo-int:27017"}]})
    for attempt in range(90):
        if client.admin.command("hello").get("isWritablePrimary"):
            break
        time.sleep(1)
    else:
        raise RuntimeError("Integration primary election failed")
    db = client[name]
    marker = db["__integration_identity"].find_one({"_id": "ownership"})
    if marker:
        if marker.get("project") != project or marker.get("run") != run:
            raise RuntimeError("Non-owned database; refusing provisioning")
        print("Owned integration DB already provisioned; no schema changes applied")
        return
    if db.list_collection_names():
        raise RuntimeError("Integration DB is not empty; refusing any migration")
    from app.database import init_indexes
    init_indexes(db)
    db.command("createUser", "integration_app", pwd=os.environ["WELLQ_APP_PASSWORD"], roles=[{"role": "readWrite", "db": name}])
    db["__integration_identity"].insert_one({"_id": "ownership", "project": project, "run": run})
    print("NEW empty integration DB: replica set, validators, indexes and test account provisioned")


if __name__ == "__main__":
    files() if sys.argv[1] == "files" else provision()
