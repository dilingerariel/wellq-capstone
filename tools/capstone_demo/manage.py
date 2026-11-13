"""Prepare/start/stop only a NEW synthetic deployment. Never starts ngrok."""

import argparse
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from copy import deepcopy
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[2]
BACK = ROOT / "wellq-clinical-tests-main/backend"
BASE = BACK / "integration/.runtime/capstone-demo"
REQUIRED_FREE_MIB = 4096


def write_private(path, value):
    with path.open("xb") as f:
        f.write(
            value if isinstance(value, bytes) else json.dumps(value, indent=2).encode()
        )
    path.chmod(0o600)


def traffic_policy(cidrs):
    networks = [ipaddress.ip_network(c, strict=True) for c in cidrs]
    if not networks or any(n.prefixlen == 0 for n in networks):
        raise ValueError("Explicit evaluator CIDRs required; /0 denied")
    return {
        "on_http_request": [
            {
                "actions": [
                    {
                        "type": "restrict-ips",
                        "config": {
                            "enforce": True,
                            "allow": [str(n) for n in networks],
                        },
                    }
                ]
            }
        ]
    }


def prepare(origin="http://127.0.0.1:9080", base=BASE):
    # Validate using the actual gateway policy without importing the clinical app.
    import sys

    sys.path.insert(0, str(BACK))
    from integration.capstone_gateway import AUDIENCE, ISSUER, validate_origin

    origin = validate_origin(origin)
    run = "capstone-" + uuid.uuid4().hex[:12]
    folder = base / run
    folder.mkdir(parents=True, exist_ok=False)
    project = "wellq-int-" + run
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    write_private(
        folder / "private.pem",
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    write_private(
        folder / "public.pem",
        private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ),
    )
    write_private(folder / "gateway.key", secrets.token_bytes(64))
    profiles, passes = [], {}
    for clinic in ("a", "b"):
        for role in ("patient", "clinician"):
            name = role + "-" + clinic
            code = secrets.token_urlsafe(32)
            passes[name] = code
            profiles.append(
                {
                    "subject": project + ":" + name,
                    "role": role,
                    "tenant": "synthetic-local-demo-" + run + "-" + clinic,
                    "resource": (
                        "synthetic-local-patient-demo-shared"
                        if role == "patient"
                        else "synthetic-local-clinician-demo-" + clinic
                    ),
                    "code_hash": hashlib.sha256(code.encode()).hexdigest(),
                }
            )
    config = {
        "project": project,
        "run": run,
        "environment": "test",
        "origin": origin,
        "catalog_clinically_approved": False,
        "expires_at": int(time.time()) + 7200,
        "profiles": profiles,
    }
    write_private(folder / "gateway.json", config)
    write_private(folder / "participant-passes.private.json", passes)
    root_password, app_password = secrets.token_hex(32), secrets.token_hex(32)
    env = {
        "ENVIRONMENT": "test",
        "WELLQ_INTEGRATION_PROJECT": project,
        "WELLQ_INTEGRATION_RUN": run,
        "MONGODB_DB": "wellq_integration_" + run,
        "MONGODB_URI": f"mongodb://integration_app:{app_password}@mongo-int:27017/wellq_integration_{run}?authSource=wellq_integration_{run}&replicaSet=wellqIntRs",
        "JWT_ISSUER": ISSUER,
        "JWT_AUDIENCE": AUDIENCE,
        "JWT_PUBLIC_KEY_FILE": "/identity/public.pem",
        "INTEGRATION_STORE": "/synthetic-store",
        "INTEGRATION_SIGNING_KEY": "/identity/gateway.key",
        "WELLQ_INTEGRATION_SCAN_MODE": "clamav",
        "WELLQ_INTEGRATION_ASSOCIATION_MODE": "explicit-test-double",
        "AI_PROVIDER_APPROVED": "true",
        "CATALOG_CLINICALLY_APPROVED": "false",
        "CLAMAV_HOST": "clamav-int",
        "CORS_ORIGINS": json.dumps([origin]),
    }

    def bind(file, target):
        return {
            "type": "bind",
            "source": str((folder / file).resolve()),
            "target": target,
            "read_only": True,
        }

    mounts = [
        "store:/synthetic-store",
        bind("public.pem", "/identity/public.pem"),
        bind("gateway.key", "/identity/gateway.key"),
    ]
    app = {
        "image": project + "-backend",
        "environment": env,
        "networks": ["private"],
        "read_only": True,
        "tmpfs": ["/tmp"],
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "mem_limit": "256m",
        "volumes": mounts,
    }
    complete = {"provision-int": {"condition": "service_completed_successfully"}}
    services = {
        "setup-int": {
            "image": project + "-backend",
            "user": "0:0",
            "mem_limit": "128m",
            "environment": {"WELLQ_INTEGRATION_PROJECT": project},
            "networks": ["private"],
            "entrypoint": ["python", "-B", "-m", "integration.provision", "files"],
            "volumes": ["mongo-key:/mongo-key", "store:/synthetic-store"],
        },
        "mongo-int": {
            "image": "mongo:7.0",
            "mem_limit": "512m",
            "networks": ["private"],
            "environment": {
                "MONGO_INITDB_ROOT_USERNAME": "integration_root",
                "MONGO_INITDB_ROOT_PASSWORD": root_password,
            },
            "command": [
                "mongod",
                "--replSet",
                "wellqIntRs",
                "--keyFile",
                "/mongo-key/keyfile",
                "--bind_ip_all",
                "--wiredTigerCacheSizeGB",
                "0.15",
            ],
            "volumes": ["mongo:/data/db", "mongo-key:/mongo-key:ro"],
            "depends_on": {
                "setup-int": {"condition": "service_completed_successfully"}
            },
        },
        "provision-int": {
            **deepcopy(app),
            "entrypoint": ["python", "-B", "-m", "integration.capstone_seed"],
            "environment": {
                **env,
                "WELLQ_ROOT_PASSWORD": root_password,
                "WELLQ_APP_PASSWORD": app_password,
            },
            "volumes": mounts + [bind("gateway.json", "/demo/gateway.json")],
            "depends_on": ["mongo-int"],
        },
        "api-int": {
            **deepcopy(app),
            "build": {"context": str(BACK), "dockerfile": "integration/Dockerfile"},
            "command": ["api"],
            "depends_on": {**complete, "clamav-int": {"condition": "service_healthy"}},
            "healthcheck": {
                "test": [
                    "CMD",
                    "python",
                    "-B",
                    "-c",
                    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=3)",
                ],
                "interval": "5s",
                "timeout": "4s",
                "retries": 24,
            },
        },
        "objects-int": {
            **deepcopy(app),
            "mem_limit": "128m",
            "command": ["objects"],
            "depends_on": complete,
        },
        "worker-int": {
            **deepcopy(app),
            "command": ["worker"],
            "depends_on": {**complete, "clamav-int": {"condition": "service_healthy"}},
        },
        "clamav-int": {
            "image": "clamav/clamav:stable",
            "mem_limit": "1800m",
            "networks": ["private", "av-update"],
            "volumes": ["clam:/var/lib/clamav"],
        },
        "gateway": {
            **deepcopy(app),
            "mem_limit": "192m",
            "entrypoint": ["python", "-B", "-m", "integration.capstone_gateway"],
            "ports": ["127.0.0.1:9080:9080"],
            "volumes": mounts
            + [
                bind("gateway.json", "/demo/gateway.json"),
                bind("private.pem", "/demo/private.pem"),
                bind("portal", "/portal"),
            ],
            "depends_on": {
                "api-int": {"condition": "service_healthy"},
                "objects-int": {"condition": "service_started"},
            },
        },
    }
    plan = {
        "name": project,
        "services": services,
        "networks": {
            "private": {"name": project + "-net", "internal": True},
            "av-update": {"name": project + "-av-update"},
        },
        "volumes": {
            k: {"name": project + "-" + k}
            for k in ("mongo", "mongo-key", "store", "clam")
        },
    }
    write_private(folder / "compose.json", plan)
    write_private(
        folder / "ownership.json",
        {
            "project": project,
            "run": run,
            "compose_sha256": hashlib.sha256(
                (folder / "compose.json").read_bytes()
            ).hexdigest(),
        },
    )
    write_private(
        folder / "ngrok-deny-all.json",
        {
            "on_http_request": [
                {
                    "actions": [
                        {
                            "type": "custom-response",
                            "config": {
                                "status_code": 503,
                                "body": "Demonstration not publicly authorized",
                            },
                        }
                    ]
                }
            ]
        },
    )
    return folder


def owned_folder(run):
    if not re.fullmatch(r"capstone-[0-9a-f]{12}", run):
        raise ValueError("Owned demo run required")
    folder = (BASE / run).resolve(strict=True)
    if not folder.is_relative_to(BASE.resolve()):
        raise ValueError("Demo path denied")
    owner = json.loads((folder / "ownership.json").read_text())
    config = json.loads((folder / "gateway.json").read_text())
    plan = json.loads((folder / "compose.json").read_text())
    if (
        owner["project"] != "wellq-int-" + run
        or plan["name"] != owner["project"]
        or config["project"] != owner["project"]
        or owner["compose_sha256"]
        != hashlib.sha256((folder / "compose.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Demo ownership/configuration changed")
    return folder, plan


def free_memory_mib():
    if os.name == "nt":
        value = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory",
            ],
            text=True,
        )
        return int(value.strip()) // 1024
    values = Path("/proc/meminfo").read_text().splitlines()
    return (
        int(next(v.split()[1] for v in values if v.startswith("MemAvailable:"))) // 1024
    )


def build_portal(folder, project, runner=None):
    """Compiled DEVELOPMENT artifact; the normal production build stays intact."""
    runner = runner or subprocess.run
    output = folder / "portal"
    if output.exists():
        raise ValueError("Portal artifact already exists; prepare a fresh run")
    environment = {
        **os.environ,
        "NODE_ENV": "development",
        "VITE_DATA_MODE": "api",
        "WELLQ_LOCAL_INTEGRATION": "0",
        "WELLQ_LOCAL_PROFESSIONAL_LOGIN": "0",
    }
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise ValueError("Existing Node/npm installation required")
    runner(
        [npm, "run", "build", "--", "--mode", "capstone-demo", "--outDir", str(output)],
        cwd=ROOT / "wellq-clinical-tests-main/frontend",
        env=environment,
        check=True,
    )
    marker = {
        "project": project,
        "api_mode": True,
        "production": False,
        "node_env": "development",
        "mode": "capstone-demo",
        "index_sha256": hashlib.sha256(
            (output / "index.html").read_bytes()
        ).hexdigest(),
        "files": {
            p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.rglob("*")
            if p.is_file()
        },
    }
    write_private(output / ".artifact.json", marker)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "action",
        choices=["prepare", "build-portal", "check", "start", "stop", "policy"],
    )
    p.add_argument("--origin", default="http://127.0.0.1:9080")
    p.add_argument("--run")
    p.add_argument("--allow-cidr", action="append", default=[])
    a = p.parse_args()
    if a.action == "prepare":
        folder = prepare(a.origin)
        print(
            json.dumps(
                {
                    "run": folder.name,
                    "private_directory": str(folder),
                    "public_tunnel": False,
                }
            )
        )
        return
    folder, plan = owned_folder(a.run or "")
    command = [
        "docker",
        "compose",
        "-p",
        plan["name"],
        "-f",
        str(folder / "compose.json"),
    ]
    if a.action == "build-portal":
        build_portal(folder, plan["name"])
        print(
            "Compiled non-production API demo portal; production build guards unchanged"
        )
    elif a.action == "policy":
        config = json.loads((folder / "gateway.json").read_text())
        if not config["origin"].startswith("https://"):
            raise ValueError(
                "Configure the exact HTTPS domain before preparing public policy"
            )
        write_private(folder / "ngrok-restricted.json", traffic_policy(a.allow_cidr))
        print("Restricted policy prepared; deny-all retained; no tunnel started")
    elif a.action == "check":
        subprocess.run(command + ["config", "--quiet"], check=True)
        print(
            json.dumps(
                {
                    "configuration": "valid",
                    "free_mib": free_memory_mib(),
                    "required_mib": REQUIRED_FREE_MIB,
                }
            )
        )
    elif a.action == "start":
        available = free_memory_mib()
        if available < REQUIRED_FREE_MIB:
            print(
                json.dumps(
                    {
                        "blocked": "Insufficient free RAM; historical services untouched",
                        "free_mib": available,
                        "required_mib": REQUIRED_FREE_MIB,
                    }
                )
            )
            raise SystemExit(2)
        config = json.loads((folder / "gateway.json").read_text())
        if (
            config["expires_at"] <= time.time()
            or not (folder / "portal/index.html").is_file()
        ):
            raise ValueError(
                "Fresh invitations and a compiled API-mode portal required"
            )
        sys.path.insert(0, str(BACK))
        from integration.capstone_gateway import validate_portal

        validate_portal(folder / "portal", plan["name"])
        if subprocess.check_output(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=" + plan["name"],
            ]
        ).strip():
            raise ValueError("Demo containers already exist; inspect before restarting")
        subprocess.run(command + ["build", "api-int"], check=True)
        subprocess.run(
            command + ["up", "-d", "--no-build", "--pull", "never"], check=True
        )
    else:
        subprocess.run(
            command + ["stop"], check=True
        )  # No down, removal, volume purge or historical project.


if __name__ == "__main__":
    main()
