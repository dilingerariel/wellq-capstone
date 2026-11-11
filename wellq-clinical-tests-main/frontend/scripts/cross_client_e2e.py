"""New disposable synthetic stack only. No reuse of recovered integration state."""

import argparse
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tarfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[3]
BACK = REPO / "wellq-clinical-tests-main/backend"
FRONT = REPO / "wellq-clinical-tests-main/frontend"
MOBILE = REPO / "wellq-clinical-tests-main/mobile"
RUNS = REPO / ".venv/wellq-cross-e2e"
MIB = 1024 * 1024
SERVICE_MEMORY = {
    "setup-int": 128,
    "mongo-int": 512,
    "provision-int": 256,
    "objects-int": 128,
    "api-int": 256,
    "worker-int": 256,
}
STEADY = (512 + 128 + 256 + 256) * MIB
RESERVE = 384 * MIB


def command(args, **kwargs):
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        timeout=kwargs.pop("timeout", 60),
        **kwargs,
    )
    if result.returncode:
        raise RuntimeError("External command failed; output withheld")
    return result.stdout


def docker_json(*args):
    return json.loads(command(["docker", *args]))


def snapshot():
    ids = command(["docker", "ps", "-aq"]).decode().split()
    return docker_json("inspect", *ids) if ids else []


def fingerprint(container):
    # Exclude fluctuating health probe history, counters and statistics.
    return {
        key: container[key] for key in ("Id", "Name", "Config", "HostConfig", "Mounts")
    } | {
        "running": container["State"]["Running"],
        "started": container["State"]["StartedAt"],
        "restart_count": container["RestartCount"],
        "networks": sorted(container["NetworkSettings"]["Networks"]),
    }


def resource_guard(total, containers):
    running = [c for c in containers if c["State"]["Running"]]
    limits = [c["HostConfig"].get("Memory", 0) for c in running]
    if total <= 0 or any(limit <= 0 for limit in limits):
        raise RuntimeError("Memory budget unverifiable; do not start an isolated stack")
    if sum(limits) + STEADY + RESERVE > total:
        raise RuntimeError(
            "Insufficient reserved Docker memory; recovered services will not be changed"
        )
    return {
        "docker_total_mib": total // MIB,
        "existing_reserved_mib": sum(limits) // MIB,
        "new_stack_mib": STEADY // MIB,
        "reserve_mib": RESERVE // MIB,
    }


def project_guard(project, containers, volume_names, network_names):
    if any(
        (c["Config"].get("Labels") or {}).get("com.docker.compose.project") == project
        or c["Name"].lstrip("/").startswith(project + "-")
        for c in containers
    ):
        raise RuntimeError("Project already exists; never reuse a test run")
    if any(name.startswith(project + "-") for name in [*volume_names, *network_names]):
        raise RuntimeError("Preexisting test volume/network; do not reuse")


def compose_document(directory, image, mongo_image, run):
    project = "wellq-int-" + run
    mounts = [
        f"{directory / 'public.pem'}:/identity/public.pem:ro",
        f"{directory / 'gateway.key'}:/identity/gateway.key:ro",
        f"{BACK / 'app'}:/app/app:ro",
        "synthetic-store:/synthetic-store",
    ]
    env = {
        "ENVIRONMENT": "test",
        "WELLQ_INTEGRATION_PROJECT": project,
        "WELLQ_INTEGRATION_RUN": run,
        "MONGODB_DB": "wellq_integration_" + run,
        "MONGODB_URI": "mongodb://"
        + "integration_app:${WELLQ_APP_PASSWORD}@mongo-int:27017/"
        + "wellq_integration_"
        + run
        + "?authSource=wellq_integration_"
        + run
        + "&replicaSet=wellqIntRs",
        "JWT_PUBLIC_KEY_FILE": "/identity/public.pem",
        "JWT_ISSUER": "https://identity.wellq-integration.invalid",
        "JWT_AUDIENCE": "wellq-integration-only",
        "INTEGRATION_STORE": "/synthetic-store",
        "INTEGRATION_SIGNING_KEY": "/identity/gateway.key",
        "WELLQ_INTEGRATION_SCAN_MODE": "explicit-test-double",
        "WELLQ_INTEGRATION_ASSOCIATION_MODE": "explicit-test-double",
        "AI_PROVIDER_APPROVED": "true",
        "CATALOG_CLINICALLY_APPROVED": "false",
        "MAX_REQUESTS_PER_MINUTE": "10000",
    }
    services = {}
    for service in ("objects-int", "api-int", "worker-int", "provision-int"):
        services[service] = {
            "image": image,
            "pull_policy": "never",
            "environment": dict(env),
            "command": [service.removesuffix("-int")],
            "networks": ["isolated"],
            "volumes": list(mounts),
            "read_only": True,
            "tmpfs": ["/tmp"],
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "mem_limit": SERVICE_MEMORY[service] * MIB,
            "labels": {"wellq.cross-client": run},
        }
        services[service]["depends_on"] = {
            "provision-int": {"condition": "service_completed_successfully"}
        }
    provision = services["provision-int"]
    provision["entrypoint"] = [
        "python",
        "-B",
        "-m",
        "integration.provision",
        "database",
    ]
    provision.pop("command")
    provision["depends_on"] = {"mongo-int": {"condition": "service_started"}}
    provision["environment"].update(
        {
            "WELLQ_ROOT_PASSWORD": "${WELLQ_ROOT_PASSWORD}",
            "WELLQ_APP_PASSWORD": "${WELLQ_APP_PASSWORD}",
        }
    )
    services["setup-int"] = {
        "image": image,
        "pull_policy": "never",
        "user": "0:0",
        "entrypoint": ["python", "-B", "-m", "integration.provision", "files"],
        "environment": {"WELLQ_INTEGRATION_PROJECT": project},
        "networks": ["isolated"],
        "volumes": ["mongo-key:/mongo-key", "synthetic-store:/synthetic-store"],
        "mem_limit": 128 * MIB,
        "labels": {"wellq.cross-client": run},
    }
    services["mongo-int"] = {
        "image": mongo_image,
        "pull_policy": "never",
        "command": [
            "mongod",
            "--replSet",
            "wellqIntRs",
            "--keyFile",
            "/mongo-key/keyfile",
            "--bind_ip_all",
            "--wiredTigerCacheSizeGB",
            "0.25",
        ],
        "environment": {
            "MONGO_INITDB_ROOT_USERNAME": "integration_root",
            "MONGO_INITDB_ROOT_PASSWORD": "${WELLQ_ROOT_PASSWORD}",
        },
        "volumes": [
            "mongo-data:/data/db",
            "mongo-config:/data/configdb",
            "mongo-key:/mongo-key:ro",
        ],
        "networks": ["isolated"],
        "mem_limit": 512 * MIB,
        "labels": {"wellq.cross-client": run},
        "depends_on": {"setup-int": {"condition": "service_completed_successfully"}},
    }
    return {
        "name": project,
        "services": services,
        "networks": {"isolated": {"name": project + "-net", "internal": True}},
        "volumes": {
            key: {"name": project + "-" + key}
            for key in ("mongo-data", "mongo-config", "mongo-key", "synthetic-store")
        },
    }


def source_hashes():
    paths = sorted((BACK / "app").rglob("*.py")) + sorted(
        (MOBILE / "lib").rglob("*.dart")
    )
    paths += sorted((FRONT / "src").rglob("*.ts")) + sorted(
        (FRONT / "src").rglob("*.tsx")
    )
    paths += [
        Path(__file__),
        MOBILE / "test/cross_client_e2e_test.dart",
        FRONT / "e2e/cross-client.spec.ts",
        FRONT / "playwright.cross.config.ts",
    ]
    paths += [
        FRONT / "scripts" / name
        for name in ("cross_client_linux.py", "cross_client_transport.py")
    ]
    return {
        p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }


def prepare(image):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    image_info = docker_json("image", "inspect", image)[0]
    if image_info["Config"].get("Entrypoint") != [
        "python",
        "-B",
        "-m",
        "integration.bootstrap",
    ]:
        raise RuntimeError("An existing integration image is required")
    mongo = docker_json("image", "inspect", "mongo:7.0")[0]["Id"]
    run = secrets.token_hex(6)
    directory = RUNS / ("run-" + run)
    directory.mkdir(parents=True, exist_ok=False)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (directory / "private.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    (directory / "public.pem").write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    (directory / "gateway.key").write_bytes(secrets.token_bytes(32))
    (directory / "integration.env").write_text(
        "WELLQ_ROOT_PASSWORD="
        + secrets.token_hex(32)
        + "\nWELLQ_APP_PASSWORD="
        + secrets.token_hex(32)
        + "\n"
    )
    document = compose_document(directory, image_info["Id"], mongo, run)
    (directory / "compose.json").write_text(json.dumps(document, indent=2))
    manifest = {
        "synthetic_only": True,
        "run": run,
        "project": document["name"],
        "tenant": "synthetic-local-cross-" + run,
        "patient": "synthetic-local-patient-cross-" + run,
        "clinician": "synthetic-local-clinician-cross-" + run,
        "status": "PREPARED_NOT_EXECUTED",
        "source_hashes": source_hashes(),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))
    names = (
        command(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                str(MOBILE),
            ],
            cwd=REPO,
        )
        .decode()
        .split("\0")
    )
    with tarfile.open(directory / "mobile.tar", "w") as archive:
        for name in sorted(filter(None, names)):
            p = REPO / name
            if p.is_file() and not p.is_symlink():
                archive.add(
                    p, arcname=p.relative_to(MOBILE).as_posix(), recursive=False
                )
    return directory


def verify_owned(directory, manifest):
    project = manifest["project"]
    compose = json.loads((directory / "compose.json").read_text())
    ids = (
        command(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=" + project,
            ]
        )
        .decode()
        .split()
    )
    containers = docker_json("inspect", *ids) if ids else []
    for c in containers:
        labels = c["Config"]["Labels"]
        service = labels["com.docker.compose.service"]
        if (
            service not in compose["services"]
            or c["Image"] != compose["services"][service]["image"]
        ):
            raise RuntimeError("Unknown owned service/image; stop")
        if c["Name"] != "/" + project + "-" + service + "-1":
            raise RuntimeError("Unexpected container identity")
        if (
            labels.get("wellq.cross-client") != manifest["run"]
            or c["HostConfig"].get("PortBindings")
            or set(c["NetworkSettings"]["Networks"]) != {project + "-net"}
        ):
            raise RuntimeError("Unverified integration isolation")
        expected = {
            entry.rsplit(":", 2)[-2]
            if entry.endswith(":ro")
            else entry.rsplit(":", 1)[-1]: entry
            for entry in compose["services"][service]["volumes"]
        }
        if {m["Destination"] for m in c["Mounts"]} != set(expected):
            raise RuntimeError("Unexpected mount destinations")
        for mount in c["Mounts"]:
            entry = expected[mount["Destination"]]
            prefix = entry.removesuffix(":ro").rsplit(":", 1)[0]
            if mount["RW"] != (not entry.endswith(":ro")):
                raise RuntimeError("Unexpected mount permissions")
            if mount["Type"] == "volume":
                if (
                    prefix not in compose["volumes"]
                    or mount["Name"] != compose["volumes"][prefix]["name"]
                ):
                    raise RuntimeError("Foreign volume refused")
                owner = docker_json("volume", "inspect", mount["Name"])[0]
                if owner["Labels"].get("com.docker.compose.project") != project:
                    raise RuntimeError("Wrong volume project")
            elif (
                mount["Type"] != "bind"
                or mount["RW"]
                or not same_bind_source(mount["Source"], prefix)
            ):
                raise RuntimeError("Unreviewed mount")
    return containers


def same_bind_source(actual, expected):
    def canonical(value):
        value = value.replace("\\", "/").lower()
        for base in ("/run/desktop/mnt/host/", "/host_mnt/", "/mnt/"):
            if value.startswith(base) and len(value) > len(base) + 1:
                value = value[len(base)] + ":" + value[len(base) + 1 :]
                break
        return value.rstrip("/")

    return canonical(actual) == canonical(expected)


def linux_path(path):
    path = Path(path).resolve()
    if os.name == "nt":
        return "/mnt/" + path.drive[0].lower() + path.as_posix()[2:]
    return str(path)


def run(directory, args):
    import local_web as web

    directory = directory.resolve()
    if directory.parent != RUNS.resolve() or not directory.name.startswith("run-"):
        raise RuntimeError("Only a newly prepared private run is permitted")
    info = json.loads((directory / "manifest.json").read_text())
    if (
        info["status"] != "PREPARED_NOT_EXECUTED"
        or info["source_hashes"] != source_hashes()
    ):
        raise RuntimeError("Run already used or source changed; prepare a new run")
    before = snapshot()
    total = docker_json("info", "--format", "{{json .MemTotal}}")
    resource_guard(total, before)  # No bind or container creation before this passes.
    project_guard(
        info["project"],
        before,
        command(["docker", "volume", "ls", "-q"]).decode().split(),
        command(["docker", "network", "ls", "--format", "{{.Name}}"]).decode().split(),
    )
    baseline = {c["Id"]: fingerprint(c) for c in before}
    compose = [
        "docker",
        "compose",
        "--project-name",
        info["project"],
        "--env-file",
        str(directory / "integration.env"),
        "--file",
        str(directory / "compose.json"),
    ]
    server = ThreadingHTTPServer(
        ("127.0.0.1", 8765), web.BaseHTTPRequestHandler, bind_and_activate=False
    )
    host = vite = thread = None
    created = False
    try:
        server.allow_reuse_address = False
        if os.name == "nt":
            server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        server.server_bind()  # Fails closed on the existing bridge; never replace it.
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", 5179)) == 0:
                raise RuntimeError("Portal port occupied")
        created = True
        info["status"] = "RUNNING"
        (directory / "manifest.json").write_text(json.dumps(info, indent=2))
        command(
            compose
            + [
                "up",
                "-d",
                "setup-int",
                "mongo-int",
                "provision-int",
                "objects-int",
                "api-int",
                "worker-int",
            ],
            timeout=240,
        )
        owned = verify_owned(directory, info)
        if len(owned) != 6:
            raise RuntimeError("Incomplete isolated stack")
        names = [
            info["project"] + "-" + part
            for part in ("mongo-int-1", "objects-int-1", "api-int-1")
        ]
        for _ in range(90):
            try:
                ready = web.container_python(
                    names[2],
                    "import urllib.request,json;print(json.dumps(urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=2).status))",
                )
                if ready == 200:
                    break
            except RuntimeError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Isolated API did not become ready")
        web.RUNTIME = directory
        host = web.LocalHost(names, info)
        web.container_python(
            names[2], web.SEED_ACCESS, info
        )  # New DB relationship only.
        host.ready = True
        server.RequestHandlerClass = web.handler(host)
        server.server_activate()
        control = directory / "bridge-control.json"
        control.write_text(json.dumps({"control": host.control, "run": host.run}))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def flutter(stage):
            cmd = [
                "wsl",
                "-d",
                "Ubuntu",
                "-u",
                "vegal",
                "--",
                "python3",
                "-B",
                linux_path(FRONT / "scripts/cross_client_linux.py"),
                "--stage",
                stage,
                "--sdk",
                args.sdk,
                "--cache",
                args.cache,
                "--pdfium",
                args.pdfium,
                "--archive",
                linux_path(directory / "mobile.tar"),
                "--manifest",
                linux_path(directory / "manifest.json"),
                "--control",
                str(control),
                "--python",
                linux_path(sys.executable),
                "--helper",
                str(FRONT / "scripts/cross_client_transport.py"),
            ]
            command(cmd, timeout=780)

        flutter("upload")
        manifest = json.loads((directory / "manifest.json").read_text())
        env = {
            **os.environ,
            "VITE_DATA_MODE": "api",
            "VITE_API_BASE_URL": "/api/v1",
            "WELLQ_LOCAL_INTEGRATION": "1",
            "WELLQ_DEV_API_TARGET": web.BRIDGE,
            "WELLQ_CROSS_E2E": "1",
            "WELLQ_CROSS_MANIFEST": str(directory / "manifest.json"),
            "WELLQ_CROSS_WEB": "http://127.0.0.1:5179",
        }
        with (directory / "vite.log").open("wb") as log:
            vite = subprocess.Popen(
                [
                    "node",
                    "node_modules/vite/bin/vite.js",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "5179",
                    "--strictPort",
                ],
                cwd=FRONT,
                env=env,
                stdout=log,
                stderr=log,
            )
        for _ in range(60):
            if vite.poll() is not None:
                raise RuntimeError("Owned Vite exited")
            try:
                with web.LOCAL_HTTP.open(
                    "http://127.0.0.1:5179", timeout=2
                ) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError("Owned portal unavailable")
        output = command(
            [
                "node",
                "node_modules/@playwright/test/cli.js",
                "test",
                "--config=playwright.cross.config.ts",
                "--output=" + str(directory / "playwright"),
            ],
            cwd=FRONT,
            env=env,
            timeout=180,
        )
        (directory / "playwright.log").write_bytes(output)
        flutter("verify")
        for field, role, status in (
            ("patient", "patient", 403),
            ("clinician", "clinician", 403),
            ("tenant", "clinician", 404),
        ):
            other = dict(info)
            other[field] += "-unrelated"
            token = web.LocalHost.session(
                SimpleNamespace(fixture=other, key=host.key), role
            )["accessToken"]
            answer = host.forward(
                "/api/v1/clinical-tests/" + manifest["clinical_test_id"],
                {"Authorization": "Bearer " + token},
            )
            if answer["status"] != status:
                raise RuntimeError("Unauthorized identity was not denied")
        count = web.container_python(
            names[2],
            "import json,sys;from integration.guard import database;p=json.load(sys.stdin);d=database();print(json.dumps(d.clinical_tests.count_documents({'client_id':p['tenant'],'upload.client_upload_id':p['client_upload_id']})))",
            manifest,
        )
        if count != 1:
            raise RuntimeError("Logical upload count mismatch")
        manifest = json.loads((directory / "manifest.json").read_text())
        if not manifest.get("patient_observed_final"):
            raise RuntimeError("Patient final read missing")
        manifest.update(
            status="E2E_PASSED",
            logical_exam_count=count,
            unauthorized_cases_denied=3,
            real_clients=True,
            production_providers_certified=False,
        )
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))
    finally:
        errors = []

        def attempt(action):
            try:
                action()
            except (
                OSError,
                ValueError,
                RuntimeError,
                KeyError,
                TypeError,
                subprocess.SubprocessError,
            ):
                errors.append("Owned-resource cleanup/check incomplete")

        def stop_vite():
            if vite is not None and vite.poll() is None:
                vite.terminate()
                vite.wait(timeout=15)

        def stop_http():
            if thread is not None:
                server.shutdown()
                thread.join(timeout=5)
            server.server_close()

        def stop_relay():
            if host is not None:
                host.relay.stdin.close()
                host.relay.wait(timeout=15)

        def stop_stack():
            if created:
                verify_owned(directory, info)
                command(
                    compose + ["stop"], timeout=90
                )  # Fresh project only. No deletion.

        def check_baseline():
            after = {c["Id"]: fingerprint(c) for c in snapshot()}
            if any(after.get(key) != value for key, value in baseline.items()):
                raise RuntimeError("Preexisting environment changed")

        for action in (stop_vite, stop_http, stop_relay, stop_stack, check_baseline):
            attempt(action)
        if errors:
            raise RuntimeError(
                "Cleanup or preservation check incomplete; inspect owned run without changing other services"
            )


def main():
    if not __debug__:
        raise RuntimeError("Safety checks require assertions enabled")
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--run", type=Path)
    parser.add_argument("--backend-image")
    parser.add_argument("--sdk")
    parser.add_argument("--cache")
    parser.add_argument("--pdfium")
    args = parser.parse_args()
    if args.check:
        print(
            json.dumps(
                resource_guard(
                    docker_json("info", "--format", "{{json .MemTotal}}"), snapshot()
                )
            )
        )
    elif args.prepare:
        if not args.backend_image:
            parser.error("--prepare requires a reviewed cached --backend-image")
        print("Prepared only; no services started: " + str(prepare(args.backend_image)))
    else:
        if not all((args.sdk, args.cache, args.pdfium)):
            parser.error("--run requires Linux --sdk, --cache and --pdfium paths")
        run(args.run, args)


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        RuntimeError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        print(
            "Cross-client E2E stopped: "
            + (str(error) if isinstance(error, RuntimeError) else type(error).__name__),
            file=sys.stderr,
        )
        raise SystemExit(2)
