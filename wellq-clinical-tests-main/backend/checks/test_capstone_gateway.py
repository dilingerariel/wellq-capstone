"""Gateway contracts in-process; backend/object HTTP transport explicitly doubled."""

import hashlib
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from integration.capstone_gateway import (
    AUDIENCE,
    ISSUER,
    Authority,
    create_app,
    validate_origin,
)


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    config = {
        "environment": "test",
        "project": "wellq-int-capstone-fixture",
        "origin": "https://demo.example",
        "catalog_clinically_approved": False,
        "expires_at": int(time.time()) + 3600,
        "profiles": [
            {
                "subject": "demo:patient-a",
                "role": "patient",
                "tenant": "synthetic-local-demo-a",
                "resource": "synthetic-local-patient-demo-a",
                "code_hash": hashlib.sha256(b"synthetic-access").hexdigest(),
            }
        ],
    }
    (tmp_path / "index.html").write_text(
        "<html><head></head><body>COMPILED SYNTHETIC</body></html>"
    )
    (tmp_path / "private.pem").write_text("DENIED")
    (tmp_path / "store").mkdir()
    (tmp_path / "object.key").write_bytes(b"synthetic-signer-test-material")
    monkeypatch.setenv("INTEGRATION_STORE", str(tmp_path / "store"))
    monkeypatch.setenv("INTEGRATION_SIGNING_KEY", str(tmp_path / "object.key"))
    sent = []

    def backend(request):
        sent.append(request)
        return httpx.Response(
            200,
            json={
                "signed_url": "http://objects-int:8080/object/quarantine/clinical-tests/synthetic?signature=test"
            },
        )

    app = create_app(config, pem, tmp_path, httpx.MockTransport(backend))
    return (
        TestClient(app, base_url="https://demo.example"),
        app.state.authority,
        config,
        pem,
        sent,
    )


def login(client):
    r = client.post("/__wellq_demo/session", json={"accessCode": "synthetic-access"})
    assert r.status_code == 200
    return r.json()["accessToken"]


def test_login_claims_renewal_revocation_and_logout(gateway):
    c, a, _, _, sent = gateway
    token = login(c)
    h = {"Authorization": "Bearer " + token}
    claims = jwt.decode(
        token, a.public, algorithms=["RS256"], issuer=ISSUER, audience=AUDIENCE
    )
    assert (
        claims["role"] == "patient"
        and claims["patient_id"] == "synthetic-local-patient-demo-a"
    )
    assert c.get("/api/v1/clinical-tests", headers=h).status_code == 200
    assert sent[-1].url.host == "api-int"
    r = c.post("/__wellq_demo/refresh", headers=h)
    assert r.status_code == 200
    assert c.get("/api/v1/clinical-tests", headers=h).status_code == 401
    h = {"Authorization": "Bearer " + r.json()["accessToken"]}
    assert c.post("/__wellq_demo/logout", headers=h).status_code == 200
    assert c.get("/api/v1/clinical-tests", headers=h).status_code == 401
    assert c.post("/__wellq_demo/refresh", headers=h).status_code == 401


def test_missing_bad_expired_and_foreign_credentials_are_not_forwarded(gateway):
    c, _a, _, pem, sent = gateway
    assert c.get("/api/v1/clinical-tests").status_code == 401
    for raw in ["invalid", jwt.encode({"sub": "x", "exp": 1}, pem, algorithm="RS256")]:
        assert (
            c.get(
                "/api/v1/clinical-tests", headers={"Authorization": "Bearer " + raw}
            ).status_code
            == 401
        )
    token = login(c)
    claims = jwt.decode(token, options={"verify_signature": False})
    claims["client_id"] = "another-tenant"
    bad = jwt.encode(claims, pem, algorithm="RS256")
    assert (
        c.get(
            "/api/v1/clinical-tests", headers={"Authorization": "Bearer " + bad}
        ).status_code
        == 401
    )
    claims["exp"] = 1
    expired = jwt.encode(claims, pem, algorithm="RS256")
    assert (
        c.get(
            "/api/v1/clinical-tests", headers={"Authorization": "Bearer " + expired}
        ).status_code
        == 401
    )
    assert not sent


def test_no_role_selection_cross_origin_or_credential_files(gateway):
    c, *_ = gateway
    assert (
        c.post(
            "/__wellq_demo/session",
            json={"accessCode": "synthetic-access", "role": "clinician"},
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/__wellq_demo/session",
            json={"accessCode": "synthetic-access"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    for path in [
        "/__wellq_local/adapter.js",
        "/private.pem",
        "/.runtime/access.json",
        "/docs",
        "/openapi.json",
    ]:
        assert c.get(path).status_code == 404
    r = c.get("/clinical")
    assert (
        r.status_code == 200
        and "WellQ DEMO" in r.text
        and "__wellq_demo/adapter.js" in r.text
    )
    js = c.get("/__wellq_demo/adapter.js").text
    assert (
        "localStorage" not in js and "private.pem" not in js and "session = null" in js
    )


def test_rate_limit_and_invitation_expiry(gateway):
    c, a, *_ = gateway
    for _ in range(5):
        assert (
            c.post("/__wellq_demo/session", json={"accessCode": "wrong"}).status_code
            == 401
        )
    r = c.post("/__wellq_demo/session", json={"accessCode": "wrong"})
    assert r.status_code == 429 and r.headers["retry-after"] == "60"
    a.expires = int(time.time()) - 1
    with pytest.raises(HTTPException) as exc:
        a.access("synthetic-access")
    assert exc.value.status_code == 401


def test_gateway_restart_invalidates_old_public_session(gateway):
    c, a, *_ = gateway
    token = login(c)
    a.epoch = "new-boot-epoch"
    assert (
        c.get(
            "/api/v1/clinical-tests", headers={"Authorization": "Bearer " + token}
        ).status_code
        == 401
    )


def test_signed_urls_rewritten_and_unsigned_objects_denied(gateway):
    c, _, _, _, sent = gateway
    r = c.get("/api/v1/clinical-tests", headers={"Authorization": "Bearer " + login(c)})
    assert r.json()["signed_url"].startswith("https://demo.example/object/")
    before = len(sent)
    assert (
        c.put(
            "/object/quarantine/clinical-tests/test", content=b"SYNTHETIC"
        ).status_code
        == 403
    )
    assert len(sent) == before
    from integration.adapters import sign

    signed = sign("quarantine/clinical-tests/synthetic", "PUT")
    path = signed.split("http://objects-int:8080", 1)[1]
    assert (
        c.put(
            path, content=b"SYNTHETIC", headers={"x-goog-if-generation-match": "0"}
        ).status_code
        == 200
    )
    assert sent[-1].url.host == "objects-int"
    assert (
        c.put(path.replace("synthetic", "changed"), content=b"SYNTHETIC").status_code
        == 403
    )


@pytest.mark.parametrize(
    "change",
    [
        {"environment": "production"},
        {"project": "wellq-int-39706292db88"},
        {"catalog_clinically_approved": True},
        {"origin": "http://evil.example"},
    ],
)
def test_incomplete_or_historical_configuration_fails_closed(gateway, change):
    _, _, config, pem, _ = gateway
    with pytest.raises(ValueError):
        Authority({**config, **change}, pem)


@pytest.mark.parametrize(
    "origin",
    [
        "https://u:p@demo.example",
        "https://demo.example/path",
        "https://demo.example?q=secret",
    ],
)
def test_invalid_origins(origin):
    with pytest.raises(ValueError):
        validate_origin(origin)


def test_gateway_to_real_fastapi_routes_with_in_memory_database(env, tmp_path):
    """Real ASGI authorization and Mongo facade; no real socket/Mongo service."""
    from datetime import datetime

    from app.config import settings
    from app.main import app as backend
    from app.tenancy import TenantDatabase

    profiles = []
    for clinic in ("a", "b"):
        for role in ("patient", "clinician"):
            profiles.append(
                {
                    "subject": f"demo:{role}:{clinic}",
                    "role": role,
                    "tenant": "synthetic-local-demo-" + clinic,
                    "resource": (
                        "synthetic-local-patient-demo-shared"
                        if role == "patient"
                        else "synthetic-local-clinician-demo-" + clinic
                    ),
                    "code_hash": hashlib.sha256((role + clinic).encode()).hexdigest(),
                }
            )
    pem = env["key"].private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    config = {
        "environment": "test",
        "project": "wellq-int-capstone-asgi",
        "origin": "https://demo.example",
        "catalog_clinically_approved": False,
        "expires_at": int(time.time()) + 600,
        "profiles": profiles,
    }
    env["monkeypatch"].setattr(settings, "JWT_ISSUER", ISSUER)
    env["monkeypatch"].setattr(settings, "JWT_AUDIENCE", AUDIENCE)
    for clinic in ("a", "b"):
        db = TenantDatabase(env["raw"], "synthetic-local-demo-" + clinic)
        db.patient_access.insert_one(
            {
                "patient_id": "synthetic-local-patient-demo-shared",
                "authorised_clinicians": ["synthetic-local-clinician-demo-" + clinic],
            }
        )
        db.clinical_tests.insert_one(
            {
                "clinical_test_id": "exam-" + clinic,
                "patient_id": "synthetic-local-patient-demo-shared",
                "title": "SYNTHETIC " + clinic,
                "test_date": "2026-11-12",
                "created_at": datetime(2026, 11, 12),
                "updated_at": datetime(2026, 11, 12),
                "deleted_at": None,
                "file": {
                    "original_name": "synthetic.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 100,
                },
                "upload": {
                    "upload_id": clinic,
                    "client_upload_id": clinic,
                    "status": "initiated",
                },
            }
        )
    c = TestClient(
        create_app(config, pem, tmp_path, httpx.ASGITransport(app=backend)),
        base_url="https://demo.example",
    )

    def h(code):
        r = c.post("/__wellq_demo/session", json={"accessCode": code})
        assert r.status_code == 200
        return {"Authorization": "Bearer " + r.json()["accessToken"]}

    patient_a, doctor_a, doctor_b = h("patienta"), h("cliniciana"), h("clinicianb")
    assert [
        x["clinical_test_id"]
        for x in c.get("/api/v1/clinical-tests", headers=patient_a).json()["items"]
    ] == ["exam-a"]
    assert c.get("/api/v1/clinical-tests/exam-a", headers=doctor_a).status_code == 200
    assert c.get("/api/v1/clinical-tests/exam-a", headers=doctor_b).status_code == 404
    assert c.get("/api/v1/clinical-tests/exam-b", headers=patient_a).status_code == 404
    assert (
        c.get(
            "/api/v1/patients/synthetic-local-patient-demo-shared/lab-report",
            headers=patient_a,
        ).status_code
        == 403
    )


def test_fixture_provisioning_rejects_historical_and_preserves_existing_relations(
    env, tmp_path
):
    import json

    from integration import capstone_seed

    profiles = []
    for clinic in ("a", "b"):
        for role in ("patient", "clinician"):
            profiles.append(
                {
                    "tenant": "synthetic-local-demo-" + clinic,
                    "role": role,
                    "resource": "synthetic-local-" + role + "-demo-" + clinic,
                }
            )
    project = "wellq-int-capstone-seed-test"
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"project": project, "profiles": profiles}))
    called = []
    env["monkeypatch"].setattr(capstone_seed, "provision", lambda: called.append(True))
    env["monkeypatch"].setattr(capstone_seed, "database", lambda: env["raw"])
    env["monkeypatch"].setenv("WELLQ_INTEGRATION_PROJECT", "wellq-int-39706292db88")
    with pytest.raises(RuntimeError):
        capstone_seed.seed(path)
    assert not called
    env["monkeypatch"].setenv("WELLQ_INTEGRATION_PROJECT", project)
    env["raw"]["__integration_identity"].insert_one(
        {"_id": "ownership", "project": project}
    )
    capstone_seed.seed(path)
    capstone_seed.seed(path)
    assert env["raw"].patient_access.count_documents({}) == 2
    frozen = list(env["raw"].patient_access.find())
    env["raw"].patient_access.update_one(
        {}, {"$set": {"authorised_clinicians": ["SYNTHETIC-MISMATCH"]}}
    )
    with pytest.raises(RuntimeError):
        capstone_seed.seed(path)
    assert env["raw"].patient_access.count_documents({}) == len(frozen)


def test_browser_identity_adapter_ram_login_refresh_logout_contract():
    import subprocess

    from integration.capstone_gateway import ADAPTER

    script = r"""
import vm from 'node:vm';
import assert from 'node:assert/strict';
let source=''; for await (const c of process.stdin) source+=c;
const calls=[];
const session={accessToken:'synthetic-wire-token',role:'clinician',resourceId:'synthetic-local-clinician-demo-a',tenantId:'synthetic-local-demo-a',permissions:[],capabilities:[],expiresAt:Math.floor(Date.now()/1000)+100};
const window={prompt:()=> 'synthetic-invitation'};
Object.defineProperty(window,'localStorage',{get(){throw Error('No credential persistence');}});
const fetch=async(path,options)=>{calls.push([path,options]);return {ok:true,json:async()=>session};};
vm.runInNewContext(source,{window,fetch,Date,Error});
assert.equal(await window.wellqIdentity.getSession(),null);
assert.equal(calls.length,0);
await window.wellqIdentity.signIn();
assert.equal((await window.wellqIdentity.getSession()).role,'clinician');
assert.deepEqual(JSON.parse(calls[0][1].body),{accessCode:'synthetic-invitation'});
await window.wellqIdentity.refreshSession();
assert.equal(calls[1][1].headers.Authorization,'Bearer synthetic-wire-token');
await window.wellqIdentity.signOut();
assert.equal(await window.wellqIdentity.getSession(),null);
assert.equal(calls[2][0],'/__wellq_demo/logout');
assert.equal(calls.length,3);
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=ADAPTER,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
