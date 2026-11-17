"""Provision an empty, dedicated wellq_demo database exactly once.

Run from the backend directory. The connection string is requested without echoing it.
The script refuses a nonempty database and does not modify the application's existing DB.
"""
import getpass
import sys
from pathlib import Path
from pymongo import MongoClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import init_indexes, INDEXES


def main():
    uri = getpass.getpass("Paste the dedicated Atlas app-user URI (input is hidden): ")
    if not uri.startswith("mongodb+srv://"):
        raise SystemExit("Refusing: expected an authenticated Atlas mongodb+srv URI")
    client = MongoClient(uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
    try:
        db = client["wellq_demo"]
        init_indexes(db)
        for collection, entries in INDEXES.items():
            info = db[collection].index_information()
            if any(name not in info or info[name].get("unique") is not True for name, _ in entries):
                raise RuntimeError(f"Index verification failed for {collection}")
        client.admin.command("ping")
        print("Dedicated empty wellq_demo schema and tenant indexes are ready.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
