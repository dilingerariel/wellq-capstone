"""Verification boundary for the parent identity platform; never issues JWT."""
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

security = HTTPBearer(auto_error=False)
current_identity: ContextVar[Optional["TokenPayload"]] = ContextVar("identity", default=None)

@dataclass(frozen=True)
class TokenPayload:
    sub: str
    role: str
    client_id: str
    patient_id: Optional[str] = None
    clinician_id: Optional[str] = None
    permissions: frozenset[str] = field(default_factory=frozenset)
    capabilities: frozenset[str] = field(default_factory=frozenset)
    expires_at: int | None = None

def unauthorized():
    return HTTPException(401, detail={"code": "UNAUTHORIZED", "message": "Invalid authentication"},
                         headers={"WWW-Authenticate": "Bearer"})

def verify_token(token: str) -> TokenPayload:
    try:
        settings.validate_identity()
    except RuntimeError:
        raise HTTPException(503, detail={"code": "IDENTITY_NOT_CONFIGURED", "message": "Identity unavailable"})
    try:
        p = jwt.decode(token, settings.JWT_PUBLIC_KEY, algorithms=["RS256"],
                       issuer=settings.JWT_ISSUER, audience=settings.JWT_AUDIENCE,
                       options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "client_id",
                                            "role", "resource_id", "permissions", "capabilities"]})
        for name in ("sub", "client_id", "resource_id"):
            if not isinstance(p[name], str) or not p[name] or len(p[name]) > 200:
                raise ValueError("Invalid identity")
        if any(not isinstance(p[k], int) or isinstance(p[k], bool) for k in ("iat", "exp", "nbf")):
            raise ValueError("Invalid timestamp")
        if not (p["iat"] <= p["nbf"] < p["exp"] <= p["iat"] + settings.JWT_MAX_LIFETIME_SECONDS):
            raise ValueError("Invalid lifetime")
        role = p["role"]
        if role not in ("patient", "clinician"):
            raise ValueError("Invalid role")
        own = "patient_id" if role == "patient" else "clinician_id"
        other = "clinician_id" if role == "patient" else "patient_id"
        if p.get(own) != p["resource_id"] or p.get(other) is not None:
            raise ValueError("Inconsistent identity")
        for name in ("permissions", "capabilities"):
            if not isinstance(p[name], list) or any(not isinstance(x, str) for x in p[name]):
                raise ValueError("Invalid grants")
        return TokenPayload(p["sub"], role, p["client_id"], p.get("patient_id"), p.get("clinician_id"),
                            frozenset(p["permissions"]), frozenset(p["capabilities"]), p["exp"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise unauthorized()

async def get_current_user(request: Request,
                           credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    user = verify_token(credentials.credentials)
    current_identity.set(user)
    request.state.identity = user
    template = getattr(request.scope.get("route"), "path", "")
    permission = "clinical:read" if request.method == "GET" else "clinical:write"
    if template.endswith("/export"):
        permission = "reports:export"
    elif template.endswith("/download-url"):
        permission = "documents:download"
    elif template.endswith("/validate"):
        permission = "extractions:validate"
    elif template.endswith("/review"):
        permission = "clinical:review"
    elif template.endswith("/extraction") and request.method == "PATCH":
        permission = "extractions:confirm"
    if permission not in user.permissions:
        raise HTTPException(403, detail={"code": "PERMISSION_DENIED", "message": "Permission required"})
    if template.endswith("/export") and "report_export" not in user.capabilities:
        raise HTTPException(403, detail={"code": "CAPABILITY_DISABLED", "message": "Capability unavailable"})
    # Shared tenant/subject limiter; no per-process in-memory counter.
    import hashlib
    from datetime import datetime, timedelta
    from app.database import get_database
    db = get_database()
    now = datetime.utcnow()
    key = "rate:" + hashlib.sha256(user.sub.encode()).hexdigest() + ":" + now.strftime("%Y%m%d%H%M")
    db.request_limits.update_one({"key": key}, {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": now + timedelta(minutes=2)}}, upsert=True)
    if db.request_limits.find_one({"key": key})["count"] > settings.MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(429, detail={"code": "RATE_LIMITED", "message": "Request limit"}, headers={"Retry-After": "60"})
    return user

async def get_current_patient(user: TokenPayload = Depends(get_current_user)) -> str:
    if user.role != "patient" or not user.patient_id:
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Patient role required"})
    return user.patient_id

async def get_current_clinician(user: TokenPayload = Depends(get_current_user)) -> str:
    if user.role != "clinician" or not user.clinician_id:
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Clinician role required"})
    return user.clinician_id
