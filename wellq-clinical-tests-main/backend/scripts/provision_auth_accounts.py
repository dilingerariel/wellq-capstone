"""Safely add the account collection/index to an already-provisioned demo DB.

Does not change clinical collections or existing records. Atlas URI is hidden.
"""
import getpass
from pymongo import MongoClient


def main() -> None:
    uri = getpass.getpass("Paste the dedicated Atlas app-user URI (input is hidden): ")
    if not uri.startswith("mongodb+srv://"):
        raise SystemExit("Refusing: expected an authenticated Atlas mongodb+srv URI")
    client = MongoClient(uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
    try:
        db = client["wellq_demo"]
        client.admin.command("ping")
        if "user_accounts" not in db.list_collection_names():
            db.create_collection("user_accounts", validator={"$jsonSchema": {
                "bsonType": "object", "required": ["client_id", "email", "role", "active"],
                "properties": {"client_id": {"bsonType": "string", "minLength": 1},
                               "email": {"bsonType": "string"},
                               "role": {"enum": ["patient", "clinician"]},
                               "active": {"bsonType": "bool"}}}})
        db.user_accounts.create_index([("email", 1)], unique=True, name="tenant_email")
        info = db.user_accounts.index_information()
        if "tenant_email" not in info or info["tenant_email"].get("unique") is not True:
            raise RuntimeError("Could not verify unique email index")
        print("Account collection and unique-email index are ready; clinical data was not modified.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
