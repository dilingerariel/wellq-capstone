"""Opt-in Windows loopback host for the EXISTING owned synthetic integration.

No Docker ports, provisioning, credential rotation, production identity or API
fallback. The browser talks HTTP to Vite -> this bridge -> real ASGI/objects.
Signing is host-side, using the existing private test key outside React/Git.
"""

import argparse
import base64
import hashlib
import io
import json
import os
import secrets
import socket
import subprocess
import sys
import tarfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import urllib.request
import urllib.error

import jwt
from cryptography.hazmat.primitives import serialization

from live_api import (
    BACK,
    FRONT,
    RUNTIME,
    PIPE_RELAY,
    command,
    container_python,
    inspect,
)

LOCAL = RUNTIME / "local-web"
CONTROL = LOCAL / "control.json"
FIXTURE = LOCAL / "fixture.json"
WEB = "http://127.0.0.1:5178"
BRIDGE = "http://127.0.0.1:8765"
# A Windows proxy setting must never receive the private loopback control nonce.
LOCAL_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
GRANTS = [
    "clinical:read",
    "clinical:write",
    "documents:download",
    "extractions:confirm",
    "extractions:validate",
    "clinical:review",
    "reports:export",
]
SEED_ACCESS = """
import json,sys
from integration.guard import database
from app.tenancy import TenantDatabase
p=json.load(sys.stdin)
assert p['tenant'].startswith('synthetic-local-') and p['patient'].startswith('synthetic-local-patient-')
db=TenantDatabase(database(),p['tenant'])
old=db.patient_access.find_one({'patient_id':p['patient']})
if old:assert old.get('authorised_clinicians')==[p['clinician']]
else:db.patient_access.insert_one({'patient_id':p['patient'],'authorised_clinicians':[p['clinician']]})
print(json.dumps({'owned_synthetic_relation':True}))
"""


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def owned(check_source=True):
    state = load(RUNTIME / "state.json")
    project = state["project"]
    assert (
        project == "wellq-int-" + state["run"]
        and state["db"] == "wellq_integration_" + state["run"]
    )
    names = [
        project + "-" + service
        for service in (
            "mongo-int-1",
            "objects-int-1",
            "api-int-1",
            "worker-int-1",
            "worker-int-2",
        )
    ]
    details = [inspect(name) for name in names]
    for c in details:
        assert c["Config"]["Labels"]["com.docker.compose.project"] == project
        assert not c["HostConfig"].get("PortBindings")
        assert set(c["NetworkSettings"]["Networks"]) == {project + "-net"}
        if c["Config"]["Labels"]["com.docker.compose.service"] != "mongo-int":
            env = dict(item.split("=", 1) for item in c["Config"]["Env"])
            assert env["ENVIRONMENT"] == "test" and env["MONGODB_DB"] == state["db"]
            assert (
                "@mongo-int:27017/" + state["db"] + "?" in env["MONGODB_URI"]
                and "replicaSet=wellqIntRs" in env["MONGODB_URI"]
            )
            assert (
                env["JWT_ISSUER"] == "https://identity.wellq-integration.invalid"
                and env["JWT_AUDIENCE"] == "wellq-integration-only"
            )
        for mount in c["Mounts"]:
            if mount["Type"] == "volume" and mount["Destination"] != "/data/configdb":
                assert mount["Name"].startswith(project + "-")
                volume = json.loads(
                    command(["docker", "volume", "inspect", mount["Name"]])
                )[0]
                assert volume["Labels"]["com.docker.compose.project"] == project
    volumes = {
        mount["Name"]
        for c in details
        for mount in c["Mounts"]
        if mount["Type"] == "volume"
    }
    ids = command(["docker", "ps", "-q"]).decode().split()
    for c in json.loads(command(["docker", "inspect", *ids])) if ids else []:
        if c["Name"].lstrip("/") in names:
            continue
        if (
            (c["Config"].get("Labels") or {}).get("com.docker.compose.project")
            == project
            or project + "-net" in c["NetworkSettings"]["Networks"]
            or any(mount.get("Name") in volumes for mount in c["Mounts"])
        ):
            raise RuntimeError(
                "Another integration task is active; finish it before local Start/Stop"
            )
    # Refuse stale product code without rebuilding or replacing historical containers.
    if not check_source:
        return state, names
    archive = command(["docker", "cp", names[2] + ":/app/app", "-"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as entries:
        compared = 0
        for m in entries.getmembers():
            if m.isfile() and m.name.endswith(".py"):
                current = BACK / m.name
                assert current.is_file() and current.read_bytes().replace(
                    b"\r\n", b"\n"
                ) == entries.extractfile(m).read().replace(b"\r\n", b"\n"), (
                    "Integration image is stale; see LOCAL_DEVELOPMENT.md"
                )
                compared += 1
        assert compared >= 35
    return state, names


def status():
    if not CONTROL.is_file():
        return None
    record = load(CONTROL)
    try:
        request = urllib.request.Request(
            BRIDGE + "/__wellq_local/status",
            headers={"X-WellQ-Control": record["control"]},
        )
        with LOCAL_HTTP.open(request, timeout=3) as response:
            result = json.load(response)
        if result["run"] == record["run"]:
            return result
    except (OSError, ValueError, KeyError):
        pass
    return None


class LocalHost:
    def __init__(self, names, fixture):
        self.names, self.fixture = names, fixture
        self.nonce, self.control, self.run = (
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(32),
            secrets.token_hex(12),
        )
        self.ready = False
        self.lock = threading.Lock()
        self.relay = subprocess.Popen(
            ["docker", "exec", "-i", names[2], "python", "-B", "-u", "-c", PIPE_RELAY],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.key = serialization.load_pem_private_key(
            (RUNTIME / "private.pem").read_bytes(), None
        )
        public = self.key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        assert (
            self.key.key_size >= 2048
            and public.strip() == (RUNTIME / "public.pem").read_bytes().strip()
        )
        self.frontend = None

    def session(self, role):
        assert role in ("patient", "clinician")
        now = int(time.time())
        identity = self.fixture[role]
        grants = [
            g
            for g in GRANTS
            if g
            not in (
                ("reports:export", "extractions:validate", "clinical:review")
                if role == "patient"
                else ("extractions:confirm",)
            )
        ]
        capabilities = ["report_export"] if role == "clinician" else []
        claims = {
            "sub": "synthetic-local:" + identity,
            "resource_id": identity,
            role + "_id": identity,
            "role": role,
            "client_id": self.fixture["tenant"],
            "permissions": grants,
            "capabilities": capabilities,
            "iss": "https://identity.wellq-integration.invalid",
            "aud": "wellq-integration-only",
            "iat": now - 1,
            "nbf": now - 1,
            "exp": now + 600,
        }
        return {
            "accessToken": jwt.encode(claims, self.key, algorithm="RS256"),
            "role": role,
            "resourceId": identity,
            "tenantId": self.fixture["tenant"],
            "permissions": grants,
            "capabilities": capabilities,
            "expiresAt": claims["exp"],
        }

    def forward(self, path, headers=None, method="GET", body=None, storage=False):
        payload = {
            "path": path,
            "headers": headers or {},
            "method": method,
            "body": base64.b64encode(body).decode() if body is not None else None,
            "storage": storage,
        }
        with self.lock:
            self.relay.stdin.write(json.dumps(payload).encode() + b"\n")
            self.relay.stdin.flush()
            result = json.loads(self.relay.stdout.readline())
        if result.get("transport_failure"):
            raise RuntimeError("Real integration HTTP transport unavailable")
        return result

    def api(self, method, path, body=None, role="patient", key=None):
        headers = {
            "Authorization": "Bearer " + self.session(role)["accessToken"],
            "Content-Type": "application/json",
        }
        if key:
            headers["Idempotency-Key"] = key
        result = self.forward(
            "/api/v1" + path,
            headers,
            method,
            json.dumps(body).encode() if body is not None else None,
        )
        return result["status"], json.loads(base64.b64decode(result["body"]))

    def seed(self):
        assert container_python(self.names[2], SEED_ACCESS, self.fixture)[
            "owned_synthetic_relation"
        ]
        # Generate an annotated PDF; the normal product upload/worker/confirmation
        # chain processes its bytes. IA/scanner/storage remain explicit doubles.
        from reportlab.pdfgen import canvas

        payload = {
            "schema_version": "1.0",
            "document_type": "blood_panel",
            "language": "es",
            "page_count": 1,
            "collection_date": time.strftime("%Y-%m-%d"),
            "panels": [
                {
                    "panel_code": "metabolic",
                    "panel_name_raw": "SYNTHETIC",
                    "specimen": "blood",
                    "markers": [
                        {
                            "marker_code": "glucose",
                            "raw_name": "SYNTHETIC glucose",
                            "value_raw": "90",
                            "unit_raw": "mg/dL",
                            "confidence": dict.fromkeys(
                                ["value", "unit", "reference", "name"], 0.99
                            ),
                            "page": 1,
                            "evidence": "Synthetic annotation",
                        }
                    ],
                }
            ],
        }
        output = io.BytesIO()
        c = canvas.Canvas(output)
        c.drawString(20, 750, "SYNTHETIC LOCAL SAMPLE - NOT PATIENT DATA")
        c.drawString(
            10, 700, "WQINT:" + base64.b64encode(json.dumps(payload).encode()).decode()
        )
        c.save()
        data = output.getvalue()
        (LOCAL / "synthetic-example.pdf").write_bytes(data)
        docs = self.fixture.setdefault("documents", [])
        while len(docs) < 2:
            request = {
                "client_upload_id": secrets.token_hex(16),
                "file_name": "synthetic-example.pdf",
                "mime_type": "application/pdf",
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "test_type": "blood_test",
                "title": "SYNTHETIC LOCAL SAMPLE " + str(len(docs) + 1),
                "test_date": payload["collection_date"],
                "ai_consent": True,
            }
            code, init = self.api(
                "POST",
                "/clinical-tests/uploads/initiate",
                request,
                key=secrets.token_hex(16),
            )
            assert code == 201
            upload = init["upload"]
            target = urlsplit(upload["signed_url"])
            assert target.netloc == "objects-int:8080"
            put = self.forward(
                target.path + "?" + target.query,
                upload["required_headers"],
                "PUT",
                data,
                True,
            )
            assert put["status"] == 200
            code, _ = self.api(
                "POST",
                "/clinical-tests/uploads/" + init["upload_id"] + "/complete",
                {k: request[k] for k in ("client_upload_id", "sha256", "size_bytes")},
                key=secrets.token_hex(16),
            )
            assert code == 200
            docs.append(init["clinical_test_id"])
            save(FIXTURE, self.fixture)
        for cid in docs:
            for _ in range(180):
                code, ext = self.api("GET", "/clinical-tests/" + cid + "/extraction")
                if code == 200:
                    break
                time.sleep(0.3)
            assert code == 200, (
                "Synthetic extraction did not finish; inspect local logs"
            )
            if ext["status"] == "awaiting_confirmation":
                code, _ = self.api(
                    "PATCH",
                    "/clinical-tests/" + cid + "/extraction",
                    {
                        "action": "confirm",
                        "extraction_id": ext["extraction_id"],
                        "document_edits": {"identity_confirmed": True},
                    },
                    key=secrets.token_hex(16),
                )
                assert code == 200
        code, _ = self.api(
            "GET",
            "/patients/" + self.fixture["patient"] + "/lab-report",
            role="clinician",
        )
        assert code == 200
        code, _ = self.api(
            "GET",
            "/patients/synthetic-local-unrelated/clinical-tests",
            role="clinician",
        )
        assert code == 403


def handler(host):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No URL, JWT, signature, document or exception logging.

        def allowed(self):
            return (
                self.headers.get("Host") in ("127.0.0.1:5178", "127.0.0.1:8765")
                and self.headers.get("Origin") in (None, WEB, BRIDGE)
                and self.headers.get("Sec-Fetch-Site") != "cross-site"
            )

        def respond(self, code, data, kind="application/json", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for key, value in (extra or {}).items():
                if key in ("Retry-After", "WWW-Authenticate"):
                    self.send_header(key, value)
            if self.headers.get("Origin") == WEB:
                self.send_header("Access-Control-Allow-Origin", WEB)
                self.send_header("Vary", "Origin")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionError):
                pass

        def dispatch(self):
            if not self.allowed():
                return self.respond(403, b'{"error":"LOCAL_ORIGIN_DENIED"}')
            path = urlsplit(self.path).path
            if self.command == "OPTIONS":
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", WEB)
                self.send_header(
                    "Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,PUT,OPTIONS"
                )
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Authorization,Content-Type,Idempotency-Key,X-WellQ-Local,x-goog-if-generation-match",
                )
                self.end_headers()
                return
            if path == "/__wellq_local/status":
                if not secrets.compare_digest(
                    self.headers.get("X-WellQ-Control", ""), host.control
                ):
                    return self.respond(403, b"{}")
                return self.respond(
                    200,
                    json.dumps(
                        {
                            "run": host.run,
                            "ready": host.ready,
                            "web": WEB,
                            "patient": host.fixture["patient"],
                            "synthetic_only": True,
                            "production_pdf_enabled": False,
                        }
                    ).encode(),
                )
            if path == "/__wellq_local/stop":
                if self.command != "POST" or not secrets.compare_digest(
                    self.headers.get("X-WellQ-Control", ""), host.control
                ):
                    return self.respond(403, b"{}")
                self.respond(200, b"{}")
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if path == "/__wellq_local/adapter.js" and self.command == "GET":
                script = (
                    (FRONT / "scripts/local_adapter.js")
                    .read_text(encoding="utf-8")
                    .replace("__LOCAL_NONCE__", host.nonce)
                    .replace("__LOCAL_PATIENT__", host.fixture["patient"])
                )
                return self.respond(
                    200, script.encode(), "text/javascript; charset=utf-8"
                )
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 20 * 1024 * 1024:
                return self.respond(413, b"{}")
            data = self.rfile.read(length) if length else None
            if path == "/__wellq_local/session" and self.command == "POST":
                if not secrets.compare_digest(
                    self.headers.get("X-WellQ-Local", ""), host.nonce
                ):
                    return self.respond(403, b"{}")
                body = json.loads(data or b"{}")
                if not host.ready or body.get("role") not in ("patient", "clinician"):
                    return self.respond(503, b"{}")
                return self.respond(
                    200, json.dumps(host.session(body["role"])).encode()
                )
            storage = path.startswith("/object/")
            if storage:
                if self.headers.get("Authorization"):
                    return self.respond(400, b"{}")
                if not (
                    (
                        self.command == "PUT"
                        and path.startswith("/object/quarantine/clinical-tests/")
                    )
                    or (self.command == "GET" and path.startswith("/object/private/"))
                ):
                    return self.respond(404, b"{}")
            elif not (path.startswith("/api/v1/") or path in ("/health", "/ready")):
                return self.respond(404, b"{}")
            headers = {
                k: self.headers[k]
                for k in (
                    "Authorization",
                    "Content-Type",
                    "Idempotency-Key",
                    "x-goog-if-generation-match",
                )
                if k in self.headers
            }
            result = host.forward(self.path, headers, self.command, data, storage)
            content = base64.b64decode(result["body"])
            if not storage and "application/json" in result["type"]:
                body = json.loads(content)

                # Only translate the explicit signed integration object origin.
                def translate(value):
                    if isinstance(value, dict):
                        return {k: translate(v) for k, v in value.items()}
                    if isinstance(value, list):
                        return [translate(v) for v in value]
                    if isinstance(value, str) and value.startswith(
                        "http://objects-int:8080/object/"
                    ):
                        return BRIDGE + value[len("http://objects-int:8080") :]
                    return value

                content = json.dumps(translate(body)).encode()
            self.respond(
                result["status"], content, result["type"], result.get("headers")
            )

        def handle_request(self):
            try:
                self.dispatch()
            except Exception:
                self.respond(502, b'{"detail":{"code":"LOCAL_TRANSPORT_ERROR"}}')

        do_GET = do_POST = do_PATCH = do_DELETE = do_PUT = do_OPTIONS = handle_request

    return Handler


def services():
    _, names = owned()
    command(["docker", "start", names[0]])
    # hello is an unauthenticated topology/readiness query, not a credential test.
    # Wait for the existing replica set before starting clients/workers.
    for _ in range(60):
        try:
            hello = json.loads(
                command(
                    [
                        "docker",
                        "exec",
                        names[0],
                        "mongosh",
                        "--quiet",
                        "--norc",
                        "--eval",
                        "const h=db.hello();print(JSON.stringify({ready:h.isWritablePrimary&&h.setName==='wellqIntRs'}))",
                    ]
                )
            )
            if hello.get("ready"):
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("Owned Mongo replica set did not become primary")
    command(["docker", "start", *names[1:]])
    for _ in range(90):
        try:
            if container_python(
                names[2],
                "import json,urllib.request;print(json.dumps({'ready':urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=2).status==200}))",
            )["ready"]:
                break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError("Integration API readiness failed")
    return names


def serve():
    names = services()
    if FIXTURE.is_file():
        fixture = load(FIXTURE)
    else:
        fixture = {
            "tenant": "synthetic-local-" + secrets.token_hex(12),
            "patient": "synthetic-local-patient-" + secrets.token_hex(12),
            "clinician": "synthetic-local-clinician-" + secrets.token_hex(12),
        }
        save(FIXTURE, fixture)
    assert fixture["tenant"].startswith("synthetic-local-")
    host = LocalHost(names, fixture)
    server = ThreadingHTTPServer(("127.0.0.1", 8765), handler(host))
    save(CONTROL, {"control": host.control, "run": host.run, "pid": os.getpid()})
    try:
        host.seed()
        host.ready = True
        env = os.environ.copy()
        env.update(
            VITE_DATA_MODE="api",
            VITE_API_BASE_URL="/api/v1",
            VITE_API_HEALTH_URL="/health",
            WELLQ_LOCAL_INTEGRATION="1",
            WELLQ_DEV_API_TARGET=BRIDGE,
        )
        with (LOCAL / "vite.log").open("a", encoding="utf-8") as log:
            host.frontend = subprocess.Popen(
                [
                    "node",
                    str(FRONT / "node_modules/vite/bin/vite.js"),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "5178",
                    "--strictPort",
                ],
                cwd=FRONT,
                env=env,
                stdout=log,
                stderr=log,
            )
            server.serve_forever()
    finally:
        server.server_close()
        host.relay.terminate()
        if host.frontend:
            host.frontend.terminate()
            host.frontend.wait(timeout=10)


def main():
    if not __debug__:
        raise RuntimeError(
            "Integration safety guards require Python assertions enabled"
        )
    action = argparse.ArgumentParser()
    action.add_argument(
        "action", choices=["start", "serve", "stop", "status", "logs", "test-services"]
    )
    args = action.parse_args()
    if args.action == "serve":
        serve()
        return
    current = status()
    if args.action == "test-services":
        if current:
            raise RuntimeError(
                "Manual browser session active; explicitly Stop before Test to preserve RAM-only drafts"
            )
        services()
        print("Five owned synthetic integration services ready")
        return
    if args.action == "status":
        result = current or {"ready": False, "hint": "Run .\\WellQ.ps1 Start"}
        try:
            state = load(RUNTIME / "state.json")
            project = state["project"]
            assert project == "wellq-int-" + state["run"]
            names = [
                project + "-" + s
                for s in (
                    "mongo-int-1",
                    "objects-int-1",
                    "api-int-1",
                    "worker-int-1",
                    "worker-int-2",
                )
            ]
            result["containers"] = [
                {
                    "name": n,
                    "running": (c := inspect(n))["State"]["Running"],
                    "health": c["State"].get("Health", {}).get("Status"),
                    "memory_limit_mib": c["HostConfig"]["Memory"] // 1048576,
                    "published_ports": bool(c["HostConfig"].get("PortBindings")),
                }
                for n in names
            ]
            result["memory"] = (
                command(
                    [
                        "docker",
                        "stats",
                        "--no-stream",
                        "--format",
                        "{{.Name}} {{.MemUsage}}",
                        *names,
                    ]
                )
                .decode()
                .splitlines()
            )
        except Exception:
            result["docker_status"] = (
                "unavailable; start Docker Desktop / check owned state"
            )
        print(json.dumps(result))
        return
    if args.action == "logs":
        # Never echo raw dependency/transport logs; paths are sufficient to inspect privately.
        print(
            "Private local logs: "
            + str(LOCAL / "host.log")
            + " ; "
            + str(LOCAL / "vite.log")
        )
        return
    if args.action == "start":
        if current and current["ready"]:
            print("WellQ synthetic local: " + WEB)
            return
        owned()
        for port in (5178, 8765):
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", port))
        LOCAL.mkdir(parents=True, exist_ok=True)
        with (LOCAL / "host.log").open("a", encoding="utf-8") as log:
            child = subprocess.Popen(
                [sys.executable, "-B", __file__, "serve"],
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        for _ in range(120):
            if child.poll() is not None:
                raise RuntimeError(
                    "Local host stopped during startup; inspect its private log"
                )
            current = status()
            if current and current["ready"]:
                try:
                    with LOCAL_HTTP.open(WEB, timeout=2) as response:
                        if response.status == 200:
                            print("WellQ synthetic local: " + WEB)
                            return
                except OSError:
                    pass
            time.sleep(1)
        raise RuntimeError(
            "Local startup failed; use Logs. No historical container was started"
        )
    if args.action == "stop":
        _, names = owned(
            check_source=False
        )  # Stop remains possible after source edits; ownership still checked.
        if current:
            token = load(CONTROL)["control"]
            request = urllib.request.Request(
                BRIDGE + "/__wellq_local/stop",
                data=b"{}",
                headers={"X-WellQ-Control": token},
            )
            with LOCAL_HTTP.open(request, timeout=3):
                pass
            for _ in range(30):
                if status() is None:
                    break
                time.sleep(0.2)
        command(["docker", "stop", *reversed(names)], timeout=90)
        print("Only the five owned integration services stopped; all data retained")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # No traceback can include a JWT, URI, signature or private key.
        detail = (
            str(error)
            if isinstance(error, RuntimeError)
            else "Inspect private logs / ownership / ports."
        )
        print(
            "Local WellQ failed safely (" + type(error).__name__ + "). " + detail,
            file=sys.stderr,
        )
        raise SystemExit(1)
