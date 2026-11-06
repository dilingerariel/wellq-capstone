"""Historical live suites are blocked before any sentinel/network write.
Their HS256 identities and synthetic production pipeline must be ported to the
trusted identity contract and an independently provisioned test replica set.
No environment variable bypasses this guard. Pure reference rules are reused by checks/.
"""
import os
import uuid

import httpx
import jwt
import pytest
from pymongo import MongoClient

API_URL = "http://localhost:8000/api/v1"
JWT_SECRET = "your-secret-key-here"
JWT_ALGORITHM = "HS256"
EXPECTED_DB = os.getenv("WELLQ_TEST_DB", "wellq_test")
MONGO_URI = os.getenv("WELLQ_TEST_MONGO_URI", "mongodb://test-configuration-required.invalid/wellq_test")
SYSTEM_DBS = {"admin", "config", "local"}

FIX_HINT = (
    "Levanta la API en modo test y vuelve a correr:\n"
    "  docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --force-recreate fastapi\n"
    "  docker exec wellq-api printenv MONGODB_DB     (debe decir wellq_test)"
)


@pytest.fixture(scope="session", autouse=True)
def api_must_use_test_database():
    pytest.skip("Legacy live integration setup requires migration to RS256, tenant identities and an isolated replica set. Run checks/ for in-process synthetic regressions. No sentinel was written.")
    yield


# ---------------------------------------------------------------------------
# Relación asistencial para los tests (app/dependencies/access.py exige una relación real)
# ---------------------------------------------------------------------------
ACCESS_COLLECTION = os.getenv("WELLQ_ACCESS_COLLECTION", "patient_access")


@pytest.fixture(scope="session")
def mongo_test_db():
    """Conexión directa a la base de pruebas (solo para preparar y comprobar datos)."""
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)[EXPECTED_DB]


@pytest.fixture
def grant_access(mongo_test_db):
    """grant_access(patient_id, clinician_id, via="authorised"|"care") crea la relación asistencial."""
    def _grant(patient_id: str, clinician_id: str, via: str = "authorised"):
        if via == "care":
            update = {"$set": {"care_clinician_id": clinician_id}}
        else:
            update = {"$addToSet": {"authorised_clinicians": clinician_id}}
        mongo_test_db[ACCESS_COLLECTION].update_one({"patient_id": patient_id}, update, upsert=True)
    return _grant