"""Opt-in real HTTP checks using an ALREADY provisioned, owned integration stack.

No Docker ports, production identity, old passwords, provisioning or data deletion.
The loopback relay transports HTTP to uvicorn; it does not synthesize responses.
Test signing keys stay in the ignored backend integration runtime, never in React.
"""

import base64
import hashlib
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
from urllib.parse import urlencode, urlsplit

import jwt
from clinical_live import CLONE, check_clinical
from records_live import check_records, check_stale_export
from export_concurrency_live import check_export_concurrency
from current_backend import create_api
from atomic_pdf_live import check_atomic_pdf
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


def container_python(name, code, data=None, timeout=40):
    return json.loads(
        command(
            ["docker", "exec", "-i", name, "python", "-B", "-c", code],
            json.dumps(data).encode() if data is not None else None,
            timeout=timeout,
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
 origin='http://objects-int:8080' if p.get('storage') else 'http://127.0.0.1:8000'
 data=base64.b64decode(p['body']) if p.get('body') is not None else None
 req=urllib.request.Request(origin+p['path'],headers=p['headers'],data=data,method=p.get('method','GET'))
 try:
  try: response=urllib.request.urlopen(req,timeout=15)
  except urllib.error.HTTPError as error: response=error
  with response:
   result={'status':response.status,'body':base64.b64encode(response.read()).decode(),
    'type':response.headers.get('Content-Type','application/json')}
 except (OSError,urllib.error.URLError): result={'transport_failure':True}
 print(json.dumps(result),flush=True)
"""

WORKER = """
import json,sys
from integration.bootstrap import configure
configure()
from integration.guard import database
from app.workers.processing import run_once
p=json.load(sys.stdin);raw=database()
# Restrict the worker's initial lease/expired-job operations to this synthetic tenant.
# All subsequent writes retain the unmodified product worker's tenant facade/fence.
class Collection:
 def __init__(self,collection): self.collection=collection; self.name=collection.name
 def update_many(self,query,update,**kw):
  return self.collection.update_many({'$and':[{'client_id':p['tenant']},query]},update,**kw)
 def find_one_and_update(self,query,update,**kw):
  return self.collection.find_one_and_update({'$and':[{'client_id':p['tenant']},query]},update,**kw)
 def __getattr__(self,name): return getattr(self.collection,name)
class Scoped:
 client=raw.client
 clinical_tests=Collection(raw.clinical_tests)
 def __getitem__(self,name): return self.clinical_tests if name=='clinical_tests' else raw[name]
worked=run_once(Scoped(),'upload')
if worked: run_once(Scoped(),'extraction')
print(json.dumps({'worked':worked}))
"""

VERIFY_UPLOAD = """
import hashlib,json,sys
from integration.guard import database
from integration.adapters import object_path
p=json.load(sys.stdin);db=database()
docs=list(db.clinical_tests.find({'client_id':p['tenant'],'title':'SYNTHETIC BROWSER UPLOAD'}))
assert len(docs)==1
d=docs[0];data=object_path(d['file']['gcs_object_key']).read_bytes()
assert d['upload']['status']=='ready_for_review' and d['upload']['job']['status']=='done'
assert hashlib.sha256(data).hexdigest()==p['sha256']==d['file']['sha256']
assert len(data)==d['file']['size_bytes']==p['size']
assert d['file']['verified_at'] and d['file']['generation']
assert db.audit_events.count_documents({'client_id':p['tenant'],'resource_id':d['clinical_test_id']})>0
ext=db.clinical_test_extractions.find_one({'client_id':p['tenant'],'extraction_id':d['extraction']['extraction_id']})
assert ext['status']=='clinically_validated' and ext['document']['collection_date']=='2026-01-02'
marker=next(m for panel in ext['panels'] for m in panel['markers'] if m['marker_code']=='glucose')
assert marker['value_raw']=='96' and marker['edited'] is True
assert ext['proposal']['panels'][0]['markers'][0]['value_raw']=='90'
assert db.clinical_markers.count_documents({'client_id':p['tenant'],'extraction_id':ext['extraction_id'],'value_raw':'96','invalidated_at':None})==1
assert db.audit_events.count_documents({'client_id':p['tenant'],'resource_id':ext['extraction_id'],'event':'extraction_confirmed'})==1
print(json.dumps({'bytes_verified':True,'server_worker_verified':True,'single_document':True,'byte_count':len(data),'corrections_persisted':True,'proposal_preserved':True,'single_confirmation':True}))
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
    objects = project + "-objects-int-1"
    before = {name: inspect(name) for name in (mongo, api, objects)}
    assert before[objects]["Image"] == before[api]["Image"]
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
    original_api = api
    api = create_api(command, before[api], BACK, project)
    before[api] = inspect(api)
    assert before[api]["Image"] == before[original_api]["Image"]
    assert not before[api]["HostConfig"]["PortBindings"]
    assert before[api]["HostConfig"]["ReadonlyRootfs"]
    source_mount = next(m for m in before[api]["Mounts"] if m["Destination"] == "/app/app")
    assert source_mount["RW"] is False
    # The original API stays stopped; no container or volume is recreated.
    print("Dedicated API uses current backend source read-only; original API remains stopped.", flush=True)
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
        "reject":str(uuid.uuid4()),"race":str(uuid.uuid4()),"second_clinician":"synthetic-clinician-"+uuid.uuid4().hex,
    }

    def session(
        role="patient", resource=None, permissions=None, tenant=None, expired=False, capabilities=None
    ):
        now = int(time.time())
        resource = resource or fixture[role]
        grants = ["clinical:read"] if permissions is None else permissions
        claims = {
            "sub": "synthetic-http-" + role + ":" + resource,
            "role": role,
            "resource_id": resource,
            role + "_id": resource,
            "client_id": tenant or fixture["tenant"],
            "permissions": grants,
            "capabilities": capabilities or [],
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
            "capabilities": capabilities or [],
            "expiresAt": claims["exp"],
        }

    relay_process = None
    relay_lock = threading.Lock()

    def forward(path, headers, method="GET", body=None, storage=False):
        payload = {
            "path": path,
            "headers": headers,
            "method": method,
            "body": base64.b64encode(body).decode() if body is not None else None,
            "storage": storage,
        }
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
    worker_threads = []
    try:
        for name in (mongo, api, objects):
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

        absent_score=check('reporting-score-before-validation','/api/v1/patients/'+fixture['patient']+'/lab-score?history=true',clinician,404)
        assert absent_score['detail']['code']=='NO_SCORE_AVAILABLE'
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

        transfer_evidence = {
            "byte_count": 0,
            "put_requests": 0,
            "authorization_seen": False,
        }
        worker_results = []
        pdf = container_python(
            api,
            "import io,json,base64;from reportlab.pdfgen import canvas;b=io.BytesIO();c=canvas.Canvas(b);c.drawString(20,750,'SYNTHETIC BROWSER UPLOAD - NO PATIENT DATA');p={'schema_version':'1.0','document_type':'blood_panel','language':'es','page_count':1,'collection_date':'2026-01-01','panels':[{'panel_code':'metabolic','panel_name_raw':'SYNTHETIC PANEL','specimen':'blood','markers':[{'marker_code':'glucose','raw_name':'SYNTHETIC glucose','value_raw':'90','unit_raw':'mg/dL','confidence':dict.fromkeys(['value','unit','reference','name'],0.6),'page':1,'evidence':'Synthetic annotation'}]}]};c.drawString(10,700,'WQINT:'+base64.b64encode(json.dumps(p).encode()).decode());c.save();print(json.dumps({'bytes':base64.b64encode(b.getvalue()).decode()}))",
        )["bytes"]
        pdf_bytes = base64.b64decode(pdf)

        def process_upload():
            try:
                time.sleep(1)
                worker_results.append(container_python(api, WORKER, fixture)["worked"])
            except CommandFailure as error:
                print('Scoped test worker failed: '+str(error), flush=True)
                worker_results.append(False)

        confirmations = []
        report_exports = []
        report_downloads = {"count":0,"authorization_seen":False}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def cors(self):
                if self.headers.get("Origin") == "http://127.0.0.1:5175":
                    self.send_header(
                        "Access-Control-Allow-Origin", "http://127.0.0.1:5175"
                    )
                    self.send_header("Vary", "Origin")

            def do_OPTIONS(self):
                self.send_response(204)
                self.cors()
                self.send_header("Access-Control-Allow-Methods", "PUT,OPTIONS")
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Content-Type,x-goog-if-generation-match",
                )
                self.end_headers()

            def respond(self, response, storage=False):
                body = base64.b64decode(response["body"])
                if not storage and "application/json" in response["type"]:
                    document = json.loads(body)
                    if isinstance(document, dict) and isinstance(
                        document.get("upload"), dict
                    ):
                        descriptor = document["upload"]
                        target = urlsplit(descriptor["signed_url"])
                        assert (
                            target.netloc == "objects-int:8080"
                            and target.path.startswith("/object/quarantine/")
                        )
                        # Explicit test gateway origin translation only, signature/path unchanged.
                        descriptor["signed_url"] = (
                            "http://127.0.0.1:"
                            + str(bridge.server_port)
                            + target.path
                            + "?"
                            + target.query
                        )
                        body = json.dumps(document).encode()
                if not storage and "application/json" in response["type"]:
                    document=json.loads(body)
                    if isinstance(document,dict) and document.get('download_url'):
                        target=urlsplit(document['download_url'])
                        assert target.netloc=='objects-int:8080' and target.path.startswith('/object/private/lab-reports/')
                        document['download_url']='http://127.0.0.1:'+str(bridge.server_port)+target.path+'?'+target.query
                        body=json.dumps(document).encode()
                self.send_response(response["status"])
                self.cors()
                self.send_header("Content-Type", response["type"])
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                try:
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionError):
                    pass

            def do_PUT(self):
                if not self.path.startswith("/object/quarantine/clinical-tests/"):
                    self.send_error(404)
                    return
                if self.headers.get("Authorization"):
                    transfer_evidence["authorization_seen"] = True
                    self.send_error(400)
                    return
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 20 * 1024 * 1024:
                    self.send_error(413)
                    return
                data = self.rfile.read(size)
                response = forward(
                    self.path,
                    {
                        key: self.headers[key]
                        for key in ("Content-Type", "x-goog-if-generation-match")
                        if key in self.headers
                    },
                    "PUT",
                    data,
                    True,
                )
                transfer_evidence["put_requests"] += 1
                if response["status"] == 200:
                    transfer_evidence["byte_count"] += len(data)
                self.respond(response, True)

            def do_PATCH(self):
                if not re.fullmatch(r"/api/v1/clinical-tests/[^/]+/(extraction|review)", self.path):
                    self.send_error(404)
                    return
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 65536:
                    self.send_error(413)
                    return
                body = self.rfile.read(size)
                headers = {key:self.headers[key] for key in ('Authorization','Content-Type','Idempotency-Key') if key in self.headers}
                response = forward(self.path,headers,'PATCH',body)
                if response['status']==200 and self.path.endswith('/extraction'):
                    confirmations.append((self.path,headers,body))
                    assert container_python(api,CLONE,fixture)['synthetic_clones']==2
                self.respond(response)

            def do_POST(self):
                if not re.fullmatch(
                    r"/api/v1/(clinical-tests/(uploads/(initiate|[^/]+/(complete|refresh-url))|[^/]+/extraction/validate)|patients/[^/]+/lab-report/export)",
                    self.path,
                ):
                    self.send_error(404)
                    return
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 65536:
                    self.send_error(413)
                    return
                request_body=self.rfile.read(size)
                request_headers={key:self.headers[key] for key in ('Authorization','Content-Type','Idempotency-Key') if key in self.headers}
                response=forward(self.path,request_headers,'POST',request_body)
                if self.path.endswith('/lab-report/export') and response['status']==200:
                    report_exports.append((self.path,request_headers,request_body))
                self.respond(response)
                if self.path.endswith("/complete") and response["status"] == 200:
                    worker = threading.Thread(target=process_upload, daemon=True)
                    worker_threads.append(worker)
                    worker.start()

            def do_GET(self):
                if self.path.startswith('/object/private/lab-reports/'):
                    report_downloads['authorization_seen'] |= bool(self.headers.get('Authorization'))
                    assert not self.headers.get('Authorization')
                    response=forward(self.path,{},storage=True)
                    if response['status']==200:report_downloads['count']+=1
                    self.respond(response,True)
                    return
                if not (
                    self.path.startswith("/api/v1/")
                    or self.path in ("/health", "/ready")
                ):
                    self.send_error(404)
                    return
                response = forward(
                    self.path, {"Authorization": self.headers.get("Authorization", "")}
                )
                self.respond(response)

        bridge = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=bridge.serve_forever, daemon=True).start()
        browser_env = os.environ.copy()
        browser_env["WELLQ_DEV_API_TARGET"] = "http://127.0.0.1:" + str(
            bridge.server_port
        )
        browser_env["WELLQ_HTTP_FIXTURE"] = json.dumps(
            {
                **fixture,
                "patientSession": patient,
                "clinicianSession": clinician,
                "recordsSession":session('clinician',permissions=['clinical:read','reports:export'],capabilities=['report_export']),
                "clinicalSession":session('clinician',permissions=['clinical:read','clinical:review','extractions:validate']),
                "uploadSession": session(
                    permissions=["clinical:read", "clinical:write", "extractions:confirm"]
                ),
                "pdfBytes": pdf,
            }
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
        records_proof=check_records(forward,session,fixture,api,container_python,report_exports,report_downloads)
        export_concurrency_proof=check_export_concurrency(forward,session,fixture,api,container_python)
        clinical_proof=check_clinical(forward,session,fixture,api,container_python)
        assert check_stale_export(forward,report_exports)
        atomic_pdf_proof=check_atomic_pdf(session,fixture,api,container_python)
        assert len(confirmations)==1, 'Exactly one browser confirmation required'
        confirm_path, confirm_headers, confirm_body=confirmations[0]
        assert forward(confirm_path,confirm_headers,'PATCH',confirm_body)['status']==200, 'Idempotent replay failed'
        changed=json.loads(confirm_body);changed['marker_edits'][0]['value_raw']='96'
        assert forward(confirm_path,confirm_headers,'PATCH',json.dumps(changed).encode())['status']==409, 'Changed replay must conflict'
        changed['extraction_id']=str(uuid.uuid4())
        assert forward(confirm_path,confirm_headers,'PATCH',json.dumps(changed).encode())['status']==409, 'Stale version must conflict'
        for worker in worker_threads:
            worker.join(timeout=30)
        assert worker_results and all(worker_results), (
            "Scoped product worker did not complete"
        )
        upload_proof = container_python(
            api,
            VERIFY_UPLOAD,
            {
                **fixture,
                "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                "size": len(pdf_bytes),
            },
        )
        assert (
            not transfer_evidence["authorization_seen"]
            and transfer_evidence["put_requests"] == 1
        )
        assert transfer_evidence["byte_count"] == len(pdf_bytes)
        evidence = {
            "authority": "synthetic RS256 integration authority; no external SSO",
            "transport": "browser -> Vite -> loopback relay -> uvicorn HTTP -> authenticated Mongo replica set",
            "backend_python_sources_matched": compared,
            "checks": checks,
            "synthetic_documents_appended": 7,
            "clinical_api_mutations": "one synthetic upload; no real patient data",
            "upload_proof": upload_proof,
            "clinical_proof":clinical_proof,
            "records_proof":records_proof,
            "export_concurrency_proof":export_concurrency_proof,
            "atomic_pdf_proof":atomic_pdf_proof,
            "score_absent_before_validation":True,
            "export_source_change_denied":True,
            "storage_transfer": transfer_evidence,
            "external_storage_ai_scanner": "filesystem signed HTTP test storage, scanner and annotated PDF extraction doubles; no production provider certified",
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
            for worker in worker_threads:
                worker.join(timeout=30)
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
