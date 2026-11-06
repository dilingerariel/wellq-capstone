import time
import jwt
import pytest
from fastapi import HTTPException
from app.dependencies.auth import verify_token
from app.config import settings
from app.tenancy import TenantDatabase

@pytest.mark.parametrize("overrides", [
    {"exp": 1}, {"nbf": 1, "iat": 1, "exp": 2}, {"iss": "untrusted"}, {"aud": "wrong"},
    {"patient_id": "other"}, {"clinician_id": "mixed"}, {"role": "admin"}, {"client_id": ""},
    {"iat": True}, {"exp": int(time.time()) + 100000}, {"permissions": "clinical:read"}])
def test_reject_invalid_claims(env, overrides):
    with pytest.raises(HTTPException) as e: verify_token(env["token"](**overrides))
    assert e.value.status_code == 401

@pytest.mark.parametrize("claim", ["exp", "iat", "nbf", "iss", "aud", "sub", "client_id", "resource_id", "role", "permissions", "capabilities"])
def test_required_claims(env, claim):
    payload = jwt.decode(env["token"](), options={"verify_signature": False})
    del payload[claim]
    token = jwt.encode(payload, env["key"], algorithm="RS256")
    with pytest.raises(HTTPException): verify_token(token)

def test_no_browser_hmac_or_foreign_signer(env):
    fabricated = jwt.encode({"role": "patient"}, "isolated-untrusted-signing-material", algorithm="HS256")
    with pytest.raises(HTTPException): verify_token(fabricated)
    from cryptography.hazmat.primitives.asymmetric import rsa
    foreign = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    payload = jwt.decode(env["token"](), options={"verify_signature": False})
    with pytest.raises(HTTPException): verify_token(jwt.encode(payload, foreign, algorithm="RS256"))

def test_missing_identity_configuration_fails_closed(env):
    token = env["token"]()
    env["monkeypatch"].setattr(settings, "JWT_ISSUER", None)
    with pytest.raises(HTTPException) as e: verify_token(token)
    assert e.value.status_code == 503

def test_tenant_facade_reads_and_writes(env):
    a = env["db"]; b = TenantDatabase(env["raw"], "tenant-b")
    a.clinical_tests.insert_one({"clinical_test_id": "same", "patient_id": "same", "upload": {"upload_id": "a", "client_upload_id": "a"}})
    b.clinical_tests.insert_one({"clinical_test_id": "same", "patient_id": "same", "upload": {"upload_id": "b", "client_upload_id": "b"}})
    assert a.clinical_tests.count_documents({}) == b.clinical_tests.count_documents({}) == 1
    assert a.clinical_tests.update_many({"client_id": "tenant-b"}, {"$set": {"leak": True}}).modified_count == 0
    with pytest.raises(ValueError): a.clinical_tests.insert_one({"client_id": "tenant-b"})
    with pytest.raises(ValueError): a.clinical_tests.update_one({}, {"$set": {"client_id": "tenant-b"}})
    with pytest.raises(AttributeError): a.clinical_tests.aggregate([])
    env["raw"].clinical_tests.insert_one({"clinical_test_id": "legacy"})
    assert not a.clinical_tests.find_one({"clinical_test_id": "legacy"})

def test_anonymous_and_private_paths(env):
    c = env["client"]
    assert c.get("/api/v1/clinical-tests").status_code == 401
    for path in ["/exports/known.pdf", "/dashboard/", "/demo"]:
        assert c.get(path).status_code == 404
    h = {"Authorization": "Bearer " + env["token"](permissions=[])}
    assert c.get("/api/v1/clinical-tests", headers=h).status_code == 403

def test_other_patient_tenant_and_role(env):
    db = env["db"]
    db.clinical_tests.insert_one({"clinical_test_id": "ct_known", "patient_id": "patient-other", "deleted_at": None,
        "upload": {"upload_id": "u", "client_upload_id": "u"}})
    c = env["client"]
    def h(**kw): return {"Authorization": "Bearer " + env["token"](**kw)}
    assert c.get("/api/v1/clinical-tests/ct_known", headers=h()).status_code == 403
    assert c.get("/api/v1/clinical-tests/ct_known", headers=h(tenant="tenant-b")).status_code == 404
    assert c.get("/api/v1/patients/patient-other/lab-report", headers=h()).status_code == 403
    assert c.get("/api/v1/clinical-tests/ct_known", headers=h(role="clinician", identity="doctor-test")).status_code == 403
    assert c.post("/api/v1/patients/patient-other/lab-report/export", headers=h(role="clinician", capabilities=[])).status_code == 403

def test_validation_errors_do_not_reflect_clinical_body(env):
    response = env["client"].post("/api/v1/clinical-tests/uploads/initiate", headers={"Authorization": "Bearer " + env["token"]()},
                                  json={"private_sentinel": "DO-NOT-REFLECT"})
    assert response.status_code == 422
    assert "DO-NOT-REFLECT" not in response.text

def test_rate_limit_is_shared_and_retry_after_is_present(env):
    env["monkeypatch"].setattr(settings, "MAX_REQUESTS_PER_MINUTE", 1)
    h = {"Authorization": "Bearer " + env["token"]()}
    assert env["client"].get("/api/v1/marker-catalog", headers=h).status_code == 200
    response = env["client"].get("/api/v1/marker-catalog", headers=h)
    assert response.status_code == 429 and response.headers["Retry-After"] == "60"

def test_append_only_application_boundary(env):
    for name in ["score_snapshots", "clinical_result_history", "audit_events", "audit_logs"]:
        with pytest.raises(ValueError): env["db"][name].update_many({}, {"$set": {"modified": True}})

def test_cors_has_no_wildcard_and_private_cache_is_disabled(env):
    r = env["client"].options("/api/v1/clinical-tests", headers={"Origin": "https://untrusted.invalid",
            "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "Authorization"})
    assert r.status_code == 400 and "access-control-allow-origin" not in r.headers
    assert r.headers["cache-control"] == "no-store"
