"""Synthetic account authentication for the isolated WellQ demo tenant."""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta
from typing import Any

import jwt
from fastapi import HTTPException, Request
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.database import mongodb
from app.routes.demo import CLINICS_CATALOG, get_demo_private_key

EMAIL_RE = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}$")
PASSWORD_MIN = 12
PASSWORD_MAX = 128
TOKEN_TTL_SECONDS = 1800
_SCRYPT_N = 1 << 14


def require_account_auth() -> None:
    if not settings.DEMO_AUTH_ENABLED or settings.ENVIRONMENT == "production" or not settings.DEMO_MONGO_STORAGE_ENABLED:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Not found"})


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        raise HTTPException(422, detail={"code": "INVALID_EMAIL", "message": "Enter a valid email address"})
    return email


def validate_password(value: str) -> str:
    if len(value) < PASSWORD_MIN or len(value) > PASSWORD_MAX:
        raise HTTPException(422, detail={"code": "PASSWORD_POLICY", "message": f"Password must contain {PASSWORD_MIN}-{PASSWORD_MAX} characters"})
    return value


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def hash_password(password: str) -> str:
    validate_password(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=8, p=1, dklen=32)
    return f"scrypt${_SCRYPT_N}$8$1${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_text, digest_text = encoded.split("$")
        if scheme != "scrypt" or int(n) > _SCRYPT_N or int(n) < (1 << 14) or int(r) != 8 or int(p) != 1:
            return False
        decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        expected = decode(digest_text)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=decode(salt_text), n=int(n), r=8, p=1, dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, MemoryError):
        return False


# Keep response time for unknown addresses close to a real password check.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(24))


def _rate_limit(request: Request, action: str, email: str, maximum: int = 12) -> None:
    """Shared Mongo-backed fixed-window limiter, safe across serverless instances."""
    now = datetime.utcnow()
    bucket = int(now.timestamp() // 600)
    ip = request.client.host if request.client else "unknown"
    ip_fingerprint = hashlib.sha256(f"{ip}\0{email}".encode()).hexdigest()
    email_fingerprint = hashlib.sha256(email.encode()).hexdigest()
    keys = (
        (f"account:{action}:ip:{ip_fingerprint}:{bucket}", maximum),
        (f"account:{action}:email:{email_fingerprint}:{bucket}", maximum * 3),
    )
    db = mongodb.db
    if db is None:
        raise HTTPException(503, detail={"code": "DATABASE_UNAVAILABLE", "message": "Service unavailable"})
    for key, limit in keys:
        selector = {"client_id": "__wellq_auth__", "key": key}
        update = {"$inc": {"count": 1}, "$setOnInsert": {
            "expires_at": datetime.utcfromtimestamp((bucket + 2) * 600)}}
        try:
            doc = db.request_limits.find_one_and_update(
                selector, update, upsert=True, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:
            # Another serverless worker created the bucket concurrently.
            doc = db.request_limits.find_one_and_update(
                selector, {"$inc": {"count": 1}}, return_document=ReturnDocument.AFTER)
        if doc and doc.get("count", 0) > limit:
            raise HTTPException(429, detail={"code": "RATE_LIMITED", "message": "Too many attempts; try again later"}, headers={"Retry-After": "600"})


def issue_session(*, role: str, client_id: str, resource_id: str,
                  display_name: str | None = None) -> dict[str, Any]:
    now = int(time.time())
    expires_at = now + min(TOKEN_TTL_SECONDS, settings.JWT_MAX_LIFETIME_SECONDS)
    permissions = (["clinical:read", "clinical:write", "documents:download", "extractions:confirm"]
                   if role == "patient" else ["clinical:read", "clinical:write", "documents:download",
                                                "extractions:validate", "clinical:review", "reports:export"])
    capabilities = [] if role == "patient" else ["report_export"]
    claims: dict[str, Any] = {
        "sub": f"account:{role}:{resource_id}", "role": role, "client_id": client_id,
        "resource_id": resource_id, "iat": now, "nbf": now, "exp": expires_at,
        "iss": settings.JWT_ISSUER or "https://identity.wellq-demo.invalid",
        "aud": settings.JWT_AUDIENCE or "wellq-demo", "permissions": permissions,
        "capabilities": capabilities,
    }
    claims["patient_id" if role == "patient" else "clinician_id"] = resource_id
    token = jwt.encode(claims, get_demo_private_key(), algorithm="RS256")
    return {"accessToken": token, "role": role, "tenantId": client_id, "resourceId": resource_id,
            "permissions": permissions, "capabilities": capabilities, "expiresAt": expires_at,
            "displayName": display_name}


def issue_admin_session(email: str) -> dict[str, Any]:
    now = int(time.time())
    expires_at = now + min(TOKEN_TTL_SECONDS, settings.JWT_MAX_LIFETIME_SECONDS)
    resource_id = "platform-admin"
    claims = {"sub": f"admin:{email}", "role": "admin", "client_id": "wellq_platform",
              "resource_id": resource_id, "admin_id": resource_id, "iat": now, "nbf": now,
              "exp": expires_at, "iss": settings.JWT_ISSUER or "https://identity.wellq-demo.invalid",
              "aud": settings.JWT_AUDIENCE or "wellq-demo", "permissions": ["clinicians:manage"],
              "capabilities": []}
    return {"accessToken": jwt.encode(claims, get_demo_private_key(), algorithm="RS256"),
            "expiresAt": expires_at}


def clinic_by_id(clinic_id: str) -> dict[str, Any] | None:
    return next((clinic for clinic in CLINICS_CATALOG if clinic["id"] == clinic_id), None)
