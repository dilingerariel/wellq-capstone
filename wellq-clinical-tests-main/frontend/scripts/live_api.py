"""Opt-in real HTTP checks using an ALREADY provisioned, owned integration stack.

No Docker ports, production identity, old passwords, provisioning or data deletion.
The loopback relay transports HTTP to uvicorn; it does not synthesize responses.
Test signing keys stay in the ignored backend integration runtime, never in React.
"""

import base64
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives import serialization

FRONT = Path(__file__).resolve().parents[1]
BACK = FRONT.parent / "backend"
RUNTIME = BACK / "integration" / ".runtime"


class CommandFailure(RuntimeError):
    pass


def command(args, payload=None, timeout=40):
    result = subprocess.run(args, input=payload, capture_output=True, timeout=timeout)
    if result.returncode:
        # Docker error text can include configuration; never reflect it.
        diagnostic = result.stderr.decode(errors="replace")
        kinds = re.findall(
            r"^([A-Za-z.]+(?:Error|Exception)):", diagnostic, re.MULTILINE
        )
        locations = re.findall(r'File "<string>", line (\d+)', diagnostic)
        raise CommandFailure(
            "Command failed: "
            + args[0]
            + " "
            + args[1]
            + "; exception kinds="
            + ",".join(kinds)
            + "; inline lines="
            + ",".join(locations)
        )
    return result.stdout


def inspect(name):
    return json.loads(command(["docker", "inspect", name]))[0]


def container_python(name, code, data=None):
    return json.loads(
        command(
            ["docker", "exec", "-i", name, "python", "-B", "-c", code],
            json.dumps(data).encode() if data is not None else None,
        )
    )


RELAY = """
import base64,json,sys,urllib.request,urllib.error
p=json.load(sys.stdin)
req=urllib.request.Request('http://127.0.0.1:8000'+p['path'],headers=p['headers'])
try: response=urllib.request.urlopen(req,timeout=15)
except urllib.error.HTTPError as error: response=error
print(json.dumps({'status':response.status,'body':base64.b64encode(response.read()).decode(),
 'type':response.headers.get('Content-Type','application/json')}))
"""

PIPE_RELAY = """
import base64,json,sys,urllib.request,urllib.error
for line in sys.stdin:
 p=json.loads(line)
 req=urllib.request.Request('http://127.0.0.1:8000'+p['path'],headers=p['headers'])
 try:
  try: response=urllib.request.urlopen(req,timeout=15)
  except urllib.error.HTTPError as error: response=error
  with response:
   result={'status':response.status,'body':base64.b64encode(response.read()).decode(),
    'type':response.headers.get('Content-Type','application/json')}
 except (OSError,urllib.error.URLError): result={'transport_failure':True}
 print(json.dumps(result),flush=True)
"""

SEED = """
import json,sys,uuid
from datetime import datetime,timedelta
from integration.guard import database
p=json.load(sys.stdin); db=database()
# Ownership is checked before writes. Append only, unique synthetic tenant per run.
db.patient_access.insert_one({'client_id':p['tenant'],'patient_id':p['patient'],
 'authorised_clinicians':[p['clinician']]})
ids=[]
for index in range(7):
 identity=str(uuid.uuid4()); ids.append(identity)
 now=datetime(2026,1,7)-timedelta(days=index)
 db.clinical_tests.insert_one({'clinical_test_id':identity,'client_id':p['tenant'],
  'patient_id':p['patient'],'title':'SYNTHETIC HTTP DOCUMENT %02d'%(index+1),
  'test_type':'blood_test','test_date':now.strftime('%Y-%m-%d'),
  'created_at':now,'updated_at':now,'deleted_at':None,'patient_notes':None,
  'file':{'original_name':'synthetic-http.pdf','mime_type':'application/pdf','size_bytes':123},
  'upload':{'status':'initiated','upload_id':str(uuid.uuid4()),'client_upload_id':str(uuid.uuid4()),'idempotency_key':str(uuid.uuid4())},
  'review':{'status':'not_reviewed'}})
print(json.dumps({'ownership':True,'documents':ids}))
"""


def main():
    if not __debug__:
        raise RuntimeError(
            "Integration safety guards require Python assertions enabled"
        )
    state = json.loads((RUNTIME / "state.json").read_text(encoding="utf-8-sig"))
    project, run = state["project"], state["run"]
    assert re.fullmatch(r"wellq-int-[a-f0-9]+", project)
    assert project == "wellq-int-" + run and state["db"] == "wellq_integration_" + run
    mongo, api = project + "-mongo-int-1", project + "-api-int-1"
    before = {name: inspect(name) for name in (mongo, api)}
    # Refuse a stack shared with other running applications or unrelated mounts.
    all_ids = command(["docker", "ps", "-aq"]).decode().split()
    all_containers = json.loads(command(["docker", "inspect", *all_ids]))
    for name, details in before.items():
        assert details["Config"]["Labels"]["com.docker.compose.project"] == project
        assert not details["State"]["Running"], (
            "Integration services must initially be stopped"
        )
        assert not details["HostConfig"]["PortBindings"], "Published ports forbidden"
        assert set(details["NetworkSettings"]["Networks"]) == {project + "-net"}
        for mount in details["Mounts"]:
            if mount["Type"] == "volume":
                volume = json.loads(
                    command(["docker", "volume", "inspect", mount["Name"]])
                )[0]
                if mount["Name"].startswith(project + "-"):
                    assert volume["Labels"]["com.docker.compose.project"] == project
                else:
                    # Official mongo image auto-creates an anonymous configdb mount.
                    assert name == mongo and mount["Destination"] == "/data/configdb"
                    assert "com.docker.volume.anonymous" in volume["Labels"]
                    assert (
                        sum(
                            any(m.get("Name") == mount["Name"] for m in c["Mounts"])
                            for c in all_containers
                        )
                        == 1
                    )
            else:
                source_path = mount["Source"]
                desktop = "/run/desktop/mnt/host/"
                if os.name == "nt" and source_path.startswith(desktop):
                    source_path = (
                        source_path[len(desktop)]
                        + ":"
                        + source_path[len(desktop) + 1 :]
                    )
                assert Path(source_path).resolve().parent == RUNTIME.resolve()
                assert Path(source_path).name in ("public.pem", "gateway.key")
                assert mount["RW"] is False
    shared_volumes = {
        m["Name"] for d in before.values() for m in d["Mounts"] if m["Type"] == "volume"
    }
    for details in all_containers:
        if details["State"]["Running"]:
            assert not any(m.get("Name") in shared_volumes for m in details["Mounts"])
            assert project + "-net" not in details["NetworkSettings"]["Networks"]
    env = dict(item.split("=", 1) for item in before[api]["Config"]["Env"])
    assert env["ENVIRONMENT"] == "test" and env["WELLQ_INTEGRATION_PROJECT"] == project
    assert env["MONGODB_DB"] == state["db"] and env["WELLQ_INTEGRATION_RUN"] == run
    assert "@mongo-int:27017/" + state["db"] + "?" in env["MONGODB_URI"]
    assert env["JWT_ISSUER"] == "https://identity.wellq-integration.invalid"
    assert env["JWT_AUDIENCE"] == "wellq-integration-only"
    # Compare the running image's product Python sources with this checkout.
    archive = command(["docker", "cp", api + ":/app/app", "-"])
    compared = 0
    with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
        for member in contents.getmembers():
            if member.isfile() and member.name.endswith(".py"):
                actual = contents.extractfile(member).read().replace(b"\r\n", b"\n")
                source = BACK / member.name
                assert (
                    source.is_file()
                    and source.read_bytes().replace(b"\r\n", b"\n") == actual
                )
                compared += 1
    assert compared >= 30
    key = serialization.load_pem_private_key(
        (RUNTIME / "private.pem").read_bytes(), None
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    assert public.strip() == (RUNTIME / "public.pem").read_bytes().strip()
    assert key.key_size >= 2048
    fixture = {
        "tenant": "synthetic-http-" + uuid.uuid4().hex,
        "patient": "synthetic-patient-" + uuid.uuid4().hex,
        "clinician": "synthetic-clinician-" + uuid.uuid4().hex,
    }

    def session(
        role="patient", resource=None, permissions=None, tenant=None, expired=False
    ):
        now = int(time.time())
        resource = resource or fixture[role]
        grants = ["clinical:read"] if permissions is None else permissions
        claims = {
            "sub": "synthetic-http-" + role,
            "role": role,
            "resource_id": resource,
            role + "_id": resource,
            "client_id": tenant or fixture["tenant"],
            "permissions": grants,
            "capabilities": [],
            "iss": env["JWT_ISSUER"],
            "aud": env["JWT_AUDIENCE"],
            "iat": now - 120 if expired else now - 1,
            "nbf": now - 120 if expired else now - 1,
            "exp": now - 60 if expired else now + 900,
        }
        token = jwt.encode(claims, key, algorithm="RS256")
        return {
            "accessToken": token,
            "role": role,
            "resourceId": resource,
            "tenantId": claims["client_id"],
            "permissions": grants,
            "capabilities": [],
            "expiresAt": claims["exp"],
        }

    relay_process = None
    relay_lock = threading.Lock()

    def forward(path, headers):
        payload = {"path": path, "headers": headers}
        if relay_process is None:
            return container_python(api, RELAY, payload)
        with relay_lock:
            relay_process.stdin.write(json.dumps(payload).encode() + b"\n")
            relay_process.stdin.flush()
            response = json.loads(relay_process.stdout.readline())
        if response.get("transport_failure"):
            raise RuntimeError("HTTP relay transport failed; no simulated response")
        return response

    def request(path, identity=None):
        headers = (
            {"Authorization": "Bearer " + identity["accessToken"]} if identity else {}
        )
        return forward(path, headers)

    started = []
    bridge = None
    checks = []
    try:
        for name in (mongo, api):
            command(["docker", "start", name])
            started.append(name)
            if name == mongo:
                for _ in range(40):
                    result = subprocess.run(
                        [
                            "docker",
                            "exec",
                            mongo,
                            "mongosh",
                            "--quiet",
                            "--eval",
                            "if (!db.hello().isWritablePrimary) quit(1)",
                        ],
                        capture_output=True,
                    )
                    if result.returncode == 0:
                        break
                    time.sleep(1)
                else:
                    raise RuntimeError("Isolated Mongo primary did not become ready")
        for _ in range(40):
            try:
                if request("/ready")["status"] == 200:
                    break
            except RuntimeError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Isolated API did not become ready")
        relay_process = subprocess.Popen(
            ["docker", "exec", "-i", api, "python", "-B", "-u", "-c", PIPE_RELAY],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        seed = container_python(api, SEED, fixture)
        print(
            "Isolated readiness and ownership verified; synthetic fixtures appended.",
            flush=True,
        )
        assert seed["ownership"] and len(seed["documents"]) == 7
        patient, clinician = session(), session("clinician")

        def check(label, path, identity, expected):
            response = request(path, identity)
            assert response["status"] == expected, (
                label + ": unexpected status " + str(response["status"])
            )
            checks.append({"check": label, "status": expected})
            return json.loads(base64.b64decode(response["body"]))

        listing = check("patient-list", "/api/v1/clinical-tests?limit=6", patient, 200)
        assert len(listing["items"]) == 6 and listing["next_cursor"]
        second = check(
            "cursor-page",
            "/api/v1/clinical-tests?"
            + urlencode({"limit": 6, "cursor": listing["next_cursor"]}),
            patient,
            200,
        )
        assert len(second["items"]) == 1 and not second["next_cursor"]
        assert (
            len({d["clinical_test_id"] for d in listing["items"] + second["items"]})
            == 7
        )
        detail_path = "/api/v1/clinical-tests/" + seed["documents"][0]
        check("patient-detail", detail_path, patient, 200)
        check("catalog", "/api/v1/marker-catalog", patient, 200)
        clinical_path = "/api/v1/patients/" + fixture["patient"] + "/clinical-tests"
        check("clinical-relationship-list", clinical_path, clinician, 200)
        check("clinical-detail", detail_path, clinician, 200)
        check("no-auth", "/api/v1/clinical-tests", None, 401)
        check("expired-auth", "/api/v1/clinical-tests", session(expired=True), 401)
        check(
            "missing-permission", "/api/v1/clinical-tests", session(permissions=[]), 403
        )
        check(
            "unrelated-clinician",
            clinical_path,
            session("clinician", resource="synthetic-unrelated"),
            403,
        )
        check(
            "different-patient",
            detail_path,
            session(resource="synthetic-other-patient"),
            403,
        )
        check(
            "different-tenant",
            detail_path,
            session(tenant="synthetic-other-tenant"),
            404,
        )
        check("invalid-cursor", "/api/v1/clinical-tests?cursor=invalid", patient, 422)
        check(
            "missing-detail", "/api/v1/clinical-tests/synthetic-missing", patient, 404
        )
        check("wrong-role-route", clinical_path, patient, 403)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if not (
                    self.path.startswith("/api/v1/")
                    or self.path in ("/health", "/ready")
                ):
                    self.send_error(404)
                    return
                response = forward(
                    self.path, {"Authorization": self.headers.get("Authorization", "")}
                )
                body = base64.b64decode(response["body"])
                self.send_response(response["status"])
                self.send_header("Content-Type", response["type"])
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                try:
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionError):
                    pass  # Browser cancellation is expected; no request/header logging.

        bridge = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=bridge.serve_forever, daemon=True).start()
        browser_env = os.environ.copy()
        browser_env["WELLQ_DEV_API_TARGET"] = "http://127.0.0.1:" + str(
            bridge.server_port
        )
        browser_env["WELLQ_HTTP_FIXTURE"] = json.dumps(
            {**fixture, "patientSession": patient, "clinicianSession": clinician}
        )
        browser = subprocess.run(
            [
                str(FRONT / "node_modules/.bin/playwright.cmd")
                if os.name == "nt"
                else str(FRONT / "node_modules/.bin/playwright"),
                "test",
                "--config",
                "playwright.live.config.ts",
            ],
            cwd=FRONT,
            env=browser_env,
            capture_output=True,
            timeout=240,
        )
        # Defensive redaction; live tests disable traces, recordings and screenshots.
        output = browser.stdout.decode(errors="replace") + browser.stderr.decode(
            errors="replace"
        )
        output = re.sub(
            r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
            "[REDACTED TEST JWT]",
            output,
        )
        print(output.encode("ascii", "backslashreplace").decode())
        assert browser.returncode == 0, "Real HTTP browser checks failed"
        evidence = {
            "authority": "synthetic RS256 integration authority; no external SSO",
            "transport": "browser -> Vite -> loopback relay -> uvicorn HTTP -> authenticated Mongo replica set",
            "backend_python_sources_matched": compared,
            "checks": checks,
            "synthetic_documents_appended": 7,
            "clinical_api_mutations": False,
            "external_storage_ai_scanner": "explicit integration doubles; not exercised",
            "browser_passed": True,
            "no_published_docker_ports": True,
        }
        evidence_path = os.environ.get("WELLQ_LIVE_EVIDENCE")
        if evidence_path:
            Path(evidence_path).write_text(
                json.dumps(evidence, indent=2), encoding="utf-8"
            )
        print(json.dumps(evidence))
    finally:
        try:
            if bridge:
                bridge.shutdown()
                bridge.server_close()
            if relay_process:
                relay_process.stdin.close()
                relay_process.wait(timeout=20)
        finally:
            if started:
                command(
                    ["docker", "stop", "--time", "30", *reversed(started)], timeout=75
                )
        assert all(not inspect(name)["State"]["Running"] for name in before)
        print(
            "Integration containers restored to stopped state; volumes and fixtures retained."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Only assertions authored above are safe to display, never arbitrary driver errors.
        print(
            "Real HTTP validation STOPPED ("
            + type(error).__name__
            + "). No production startup."
        )
        print(
            "Guard location: line "
            + str(traceback.extract_tb(error.__traceback__)[-1].lineno)
        )
        if isinstance(error, (AssertionError, CommandFailure)):
            print(str(error))
        sys.exit(1)
