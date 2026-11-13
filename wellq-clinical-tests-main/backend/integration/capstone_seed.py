"""Provision only NEW owned demo databases; never used by historical startup."""

import json
import os
from pathlib import Path

from integration.guard import database
from integration.provision import provision


def seed(config_path="/demo/gateway.json"):
    config = json.loads(Path(config_path).read_text())
    project = os.environ.get("WELLQ_INTEGRATION_PROJECT", "")
    if not project.startswith("wellq-int-capstone-") or config["project"] != project:
        raise RuntimeError("Historical or unknown database denied")
    expected = {}
    for p in config["profiles"]:
        if (
            p["role"] not in {"patient", "clinician"}
            or not p["tenant"].startswith("synthetic-local-demo-")
            or not p["resource"].startswith("synthetic-local-")
        ):
            raise RuntimeError("Invalid synthetic profile")
        expected.setdefault(p["tenant"], {})[p["role"]] = p["resource"]
    if len(expected) != 2 or any(
        set(v) != {"patient", "clinician"} for v in expected.values()
    ):
        raise RuntimeError("Two complete synthetic clinic profiles required")
    provision()
    db = database()
    # Never repair/replace pre-existing relationship data automatically.
    marker = db["__integration_identity"].find_one({"_id": "ownership"})
    if not marker.get("demo_seeded") and db.patient_access.count_documents({}):
        raise RuntimeError("Nonempty unseeded demo access table; inspect manually")
    for tenant, identities in expected.items():
        query = {"client_id": tenant, "patient_id": identities["patient"]}
        old = db.patient_access.find_one(query)
        if old:
            if old.get("authorised_clinicians") != [identities["clinician"]]:
                raise RuntimeError("Existing demo relationship differs")
        else:
            if marker.get("demo_seeded"):
                raise RuntimeError(
                    "Previously provisioned demo relationship is missing"
                )
            db.patient_access.insert_one(
                {**query, "authorised_clinicians": [identities["clinician"]]}
            )
    db["__integration_identity"].update_one(
        {"_id": "ownership"}, {"$set": {"demo_seeded": True}}
    )
    print("New isolated synthetic relationships verified")


if __name__ == "__main__":
    seed()
