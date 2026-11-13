"""Explicit synthetic authority/proxy for a NEW isolated Capstone deployment.

Never imported by app.main or a production image. No fallback to local_web.
"""

import hashlib
import json
import os
import secrets
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

GRANTS = [
    "clinical:read",
    "clinical:write",
    "documents:download",
    "extractions:confirm",
    "extractions:validate",
    "clinical:review",
    "reports:export",
]
ISSUER = "https://identity.wellq-capstone-demo.invalid"
AUDIENCE = "wellq-capstone-demo-only"
ADAPTER = r"""'use strict';
// Synthetic demonstration only. Tokens and access passes never persist.
(() => {
 let session = null;
 async function exchange(path, body, token) {
   const response = await fetch(path, {method:'POST', credentials:'omit', cache:'no-store',
     redirect:'error', headers:{'Content-Type':'application/json', ...(token ? {Authorization:'Bearer '+token} : {})},
     body: body ? JSON.stringify(body) : undefined});
   if (!response.ok) throw new Error('Demonstration identity unavailable');
   return response.json();
 }
 window.wellqIdentity = {
   getSession: async () => session && session.expiresAt*1000 > Date.now() ? session : null,
   signIn: async () => {
     session = null;
     const code = window.prompt('WellQ DEMO: temporary access pass / código temporal (not OTP)');
     if (!code) throw new Error('Access cancelled');
     session = await exchange('/__wellq_demo/session', {accessCode:code});
   },
   refreshSession: async () => {
     if (!session) return null;
     session = await exchange('/__wellq_demo/refresh', null, session.accessToken);
     return session;
   },
   signOut: async () => {
     const previous = session; session = null;
     if (previous) await exchange('/__wellq_demo/logout', null, previous.accessToken);
   }
 };
})();
"""


def validate_origin(value):
    u = urlsplit(value)
    if (
        u.username
        or u.password
        or u.query
        or u.fragment
        or u.path not in ("", "/")
        or not u.hostname
        or (u.scheme != "https" and value != "http://127.0.0.1:9080")
        or (u.scheme == "https" and u.port not in (None, 443))
    ):
        raise ValueError("Exact HTTPS demo origin required")
    return value.rstrip("/")


class Authority:
    def __init__(self, config, private_key):
        if (
            config.get("environment") != "test"
            or not config.get("project", "").startswith("wellq-int-capstone-")
            or config.get("catalog_clinically_approved") is not False
        ):
            raise ValueError("Isolated synthetic deployment required")
        self.origin = validate_origin(config["origin"])
        self.expires = config["expires_at"]
        if not time.time() < self.expires <= time.time() + 7260:
            raise ValueError("Demo lifetime must be at most two hours")
        self.profiles = config["profiles"]
        for p in self.profiles:
            if (
                p["role"] not in ("patient", "clinician")
                or not p["tenant"].startswith("synthetic-local-demo-")
                or not p["resource"].startswith("synthetic-local-")
            ):
                raise ValueError("Synthetic profiles required")
        self.private = private_key
        self.public = load_pem_private_key(private_key, password=None).public_key()
        self.revoked = {}
        self.attempts = defaultdict(deque)
        self.epoch = secrets.token_hex(
            16
        )  # Restart invalidates every prior public session.

    def attempt(self, peer):
        now = time.time()
        recent = self.attempts[peer]
        while recent and recent[0] < now - 60:
            recent.popleft()
        if len(recent) >= 5:
            raise HTTPException(
                429, "Access temporarily limited", headers={"Retry-After": "60"}
            )
        recent.append(now)

    def access(self, code):
        digest = hashlib.sha256(code.encode()).hexdigest()
        if time.time() >= self.expires:
            raise HTTPException(401, "Demo expired")
        for p in self.profiles:
            if secrets.compare_digest(digest, p["code_hash"]):
                return p
        raise HTTPException(401, "Invalid demonstration access")

    def issue(self, profile):
        now = int(time.time())
        if now >= self.expires:
            raise HTTPException(401, "Demo expired")
        token = {
            "sub": profile["subject"],
            "role": profile["role"],
            "client_id": profile["tenant"],
            "resource_id": profile["resource"],
            ("patient_id" if profile["role"] == "patient" else "clinician_id"): profile[
                "resource"
            ],
            "permissions": GRANTS,
            "capabilities": ["report_export"],
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "nbf": now,
            "exp": min(now + 300, self.expires),
            "jti": uuid.uuid4().hex,
            "demo_epoch": self.epoch,
        }
        return {
            "accessToken": jwt.encode(token, self.private, algorithm="RS256"),
            "role": profile["role"],
            "tenantId": profile["tenant"],
            "resourceId": profile["resource"],
            "permissions": GRANTS,
            "capabilities": ["report_export"],
            "expiresAt": token["exp"],
        }

    def verify(self, request):
        raw = request.headers.get("authorization", "")
        if not raw.startswith("Bearer "):
            raise HTTPException(
                401, "Bearer required", headers={"WWW-Authenticate": "Bearer"}
            )
        try:
            token = jwt.decode(
                raw[7:],
                self.public,
                algorithms=["RS256"],
                issuer=ISSUER,
                audience=AUDIENCE,
                options={
                    "require": [
                        "sub",
                        "role",
                        "client_id",
                        "resource_id",
                        "exp",
                        "iat",
                        "nbf",
                        "jti",
                    ]
                },
            )
            if (
                token.get("demo_epoch") != self.epoch
                or token["exp"] > self.expires
                or time.time() >= self.expires
                or token["jti"] in self.revoked
            ):
                raise ValueError("Expired or revoked")
            p = next(
                p
                for p in self.profiles
                if (p["subject"], p["role"], p["tenant"], p["resource"])
                == (
                    token["sub"],
                    token["role"],
                    token["client_id"],
                    token["resource_id"],
                )
            )
            return token, p
        except (jwt.PyJWTError, ValueError, StopIteration):
            raise HTTPException(401, "Invalid demonstration session") from None


def create_app(config, private_key, dist, transport=None):
    authority = Authority(config, private_key)
    dist = Path(dist).resolve()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.authority = authority

    @app.middleware("http")
    async def boundary(request, call_next):
        # Browsers must use this exact origin; native clients authenticate with
        # a runtime invitation/Bearer, never a permissive CORS exception.
        if request.headers.get("origin") not in (None, authority.origin):
            return JSONResponse({"detail": "Origin denied"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/__wellq_demo/adapter.js")
    async def adapter():
        return Response(ADAPTER, media_type="application/javascript")

    @app.post("/__wellq_demo/session")
    async def login(request: Request):
        authority.attempt(request.client.host)
        body = await limited_body(request, 4096)
        try:
            value = json.loads(body)
            if set(value) != {"accessCode"} or not isinstance(value["accessCode"], str):
                raise ValueError()
            return authority.issue(authority.access(value["accessCode"]))
        except (ValueError, TypeError):
            raise HTTPException(422, "Demonstration access code required") from None

    @app.post("/__wellq_demo/refresh")
    async def refresh(request: Request):
        authority.attempt(request.client.host)
        token, p = authority.verify(request)
        result = authority.issue(p)
        authority.revoked[token["jti"]] = token["exp"]
        return result

    @app.post("/__wellq_demo/logout")
    async def logout(request: Request):
        token, _ = authority.verify(request)
        authority.revoked[token["jti"]] = token["exp"]
        return {"signedOut": True}

    def rewrite(value):
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        if isinstance(value, str) and value.startswith(
            "http://objects-int:8080/object/"
        ):
            return authority.origin + value[len("http://objects-int:8080") :]
        return value

    async def forward(request, target):
        body = await limited_body(request, 20 * 1024 * 1024)
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower()
            in {
                "authorization",
                "content-type",
                "idempotency-key",
                "x-goog-if-generation-match",
            }
        }
        try:
            async with httpx.AsyncClient(
                transport=transport, trust_env=False, timeout=30, follow_redirects=False
            ) as client:
                r = await client.request(
                    request.method,
                    target,
                    params=request.query_params,
                    headers=headers,
                    content=body,
                )
            if r.is_redirect:
                raise HTTPException(502, "Upstream redirect denied")
            content = r.content
            if "application/json" in r.headers.get("content-type", ""):
                content = json.dumps(rewrite(r.json())).encode()
            return Response(
                content,
                status_code=r.status_code,
                headers={
                    k: v
                    for k, v in r.headers.items()
                    if k.lower() in {"content-type", "retry-after", "www-authenticate"}
                },
            )
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "Independent demo service unavailable") from None

    @app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
    async def api(path: str, request: Request):
        authority.verify(request)
        if "\\" in path or any(p in (".", "..") for p in path.split("/")):
            raise HTTPException(404)
        return await forward(request, "http://api-int:8000/api/v1/" + path)

    @app.get("/ready")
    async def ready(request: Request):
        return await forward(request, "http://api-int:8000/ready")

    @app.api_route("/object/{path:path}", methods=["GET", "PUT"])
    async def objects(path: str, request: Request):
        if time.time() >= authority.expires:
            raise HTTPException(401, "Demo expired")
        from integration.adapters import object_path, verify_signature

        try:
            object_path(path)
            valid = verify_signature(
                path,
                request.method,
                request.query_params["expiry"],
                request.query_params["signature"],
            )
        except (KeyError, ValueError):
            valid = False
        if not valid:
            raise HTTPException(403, "Signed access required")
        return await forward(request, "http://objects-int:8080/object/" + path)

    @app.get("/{path:path}")
    async def static(path: str):
        if (
            path in {"docs", "redoc", "openapi.json", "health"}
            or path.startswith(("api", "object", "__", "."))
            or any(x.startswith(".") for x in path.split("/"))
        ):
            raise HTTPException(404)
        target = (dist / path).resolve()
        if not target.is_relative_to(dist):
            raise HTTPException(404)
        if not Path(path).suffix:
            target = (dist / "index.html").resolve()
            if not target.is_relative_to(dist) or not target.is_file():
                raise HTTPException(503, "Compiled demo portal missing")
            html = target.read_text().replace(
                "</head>", '<script src="/__wellq_demo/adapter.js"></script></head>'
            )
            return HTMLResponse(
                html.replace(
                    "<body>",
                    '<body><p role="note">WellQ DEMO — synthetic / sintético — no uso clínico</p>',
                )
            )
        if (
            target.suffix
            not in {
                ".js",
                ".css",
                ".svg",
                ".png",
                ".ico",
                ".woff",
                ".woff2",
                ".webmanifest",
            }
            or not target.is_file()
        ):
            raise HTTPException(404)
        return FileResponse(target)

    return app


async def limited_body(request, limit):
    body = bytearray()
    async for part in request.stream():
        body.extend(part)
        if len(body) > limit:
            raise HTTPException(413, "Request too large")
    return bytes(body)


def validate_portal(dist, project):
    dist = Path(dist)
    marker = json.loads((dist / ".artifact.json").read_text())
    if (
        marker.get("project") != project
        or marker.get("api_mode") is not True
        or marker.get("production") is not False
        or marker.get("mode") != "capstone-demo"
        or marker.get("node_env") != "development"
        or marker.get("index_sha256")
        != hashlib.sha256((dist / "index.html").read_bytes()).hexdigest()
    ):
        raise ValueError("Explicit owned non-production portal artifact required")
    files = marker.get("files", {})
    actual = {
        p.relative_to(dist).as_posix()
        for p in dist.rglob("*")
        if p.is_file() and p.name != ".artifact.json"
    }
    if not files or set(files) != actual:
        raise ValueError("Portal inventory changed")
    for name, expected in files.items():
        path = (dist / name).resolve()
        if (
            not path.is_relative_to(dist.resolve())
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Portal artifact hash mismatch")


if __name__ == "__main__":
    import uvicorn

    from integration.guard import environment

    project, *_ = environment()
    config = json.loads(Path("/demo/gateway.json").read_text())
    assert config["project"] == project
    validate_portal("/portal", project)
    assert os.environ["JWT_ISSUER"] == ISSUER and os.environ["JWT_AUDIENCE"] == AUDIENCE
    uvicorn.run(
        create_app(config, Path("/demo/private.pem").read_bytes(), "/portal"),
        host="0.0.0.0",
        port=9080,
        access_log=False,
        log_level="warning",
    )
