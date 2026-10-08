"""Seguro de seguridad para la suite de tests.

Los tests llaman a la API real (localhost:8000). Si la API está apuntando a la base real
(wellq_clinical) en vez de a la de pruebas (wellq_test), los tests ensuciarían datos reales.

Antes de correr cualquier test, este seguro:
  1. crea un examen "centinela" por la API (con un paciente exclusivo),
  2. busca en qué base de Mongo cayó,
  3. lo borra,
  4. aborta la corrida si no cayó en la base de pruebas.

Variables opcionales:
  WELLQ_TEST_DB          base esperada (por defecto: wellq_test)
  WELLQ_TEST_MONGO_URI   URI de Mongo vista desde tu PC (por defecto: root/password en localhost)
  WELLQ_ALLOW_ANY_DB=1   desactiva el seguro (no recomendado)
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
MONGO_URI = os.getenv("WELLQ_TEST_MONGO_URI", "mongodb://root:password@localhost:27017/?authSource=admin")
SYSTEM_DBS = {"admin", "config", "local"}

FIX_HINT = (
    "Levanta la API en modo test y vuelve a correr:\n"
    "  docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --force-recreate fastapi\n"
    "  docker exec wellq-api printenv MONGODB_DB     (debe decir wellq_test)"
)


@pytest.fixture(scope="session", autouse=True)
def api_must_use_test_database():
    if os.getenv("WELLQ_ALLOW_ANY_DB") == "1":
        yield
        return

    patient_id = f"P_GUARD_{uuid.uuid4().hex[:6]}"
    token = jwt.encode(
        {"sub": f"usr_{patient_id}", "role": "patient", "patient_id": patient_id},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    payload = {
        "client_upload_id": f"upl_guard_{uuid.uuid4().hex[:8]}",
        "file_name": "guard.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1000,
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "test_type": "blood_test",
        "title": "Seguro de base de datos",
        "test_date": "2026-01-01",
    }
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": f"idem_{uuid.uuid4().hex[:8]}"}

    # 1. Examen centinela por la API
    try:
        r = httpx.post(f"{API_URL}/clinical-tests/uploads/initiate", json=payload, headers=headers, timeout=10)
    except httpx.HTTPError as e:
        pytest.exit(f"\n[SEGURO] La API no responde en {API_URL}: {e}\n{FIX_HINT}", returncode=2)
    if r.status_code != 201:
        pytest.exit(f"\n[SEGURO] No se pudo crear el examen centinela ({r.status_code}): {r.text}", returncode=2)
    clinical_test_id = r.json()["clinical_test_id"]

    # 2. Buscar en qué base cayó (y borrarlo siempre)
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        found_in = []
        for name in client.list_database_names():
            if name in SYSTEM_DBS:
                continue
            if client[name].clinical_tests.find_one({"clinical_test_id": clinical_test_id}):
                found_in.append(name)
                client[name].clinical_tests.delete_one({"clinical_test_id": clinical_test_id})
    except Exception as e:
        pytest.exit(
            f"\n[SEGURO] No pude consultar Mongo en {MONGO_URI}: {e}\n"
            "Define WELLQ_TEST_MONGO_URI con la URI correcta, o WELLQ_ALLOW_ANY_DB=1 para saltar el seguro.",
            returncode=2,
        )

    # 3. Abortar si no está en la base de pruebas
    if found_in != [EXPECTED_DB]:
        pytest.exit(
            f"\n[SEGURO] La API está escribiendo en {found_in or 'una base desconocida'}, "
            f"y se esperaba ['{EXPECTED_DB}']. NO se ejecutó ningún test.\n{FIX_HINT}",
            returncode=2,
        )

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