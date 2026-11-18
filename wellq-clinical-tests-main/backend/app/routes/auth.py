"""Password authentication for the isolated synthetic account demo.

Only patients self-register. Clinician accounts are issued by the one platform
administrator configured outside the repository in deployment secrets.
"""
from datetime import datetime
import hashlib
import hmac
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, Field

from app.config import settings
from app.database import mongodb
from app.dependencies.auth import get_platform_admin
from app.routes.demo import CLINICS_CATALOG
from app.services.account_auth import (
    _DUMMY_PASSWORD_HASH, _rate_limit, clinic_by_id, hash_password, issue_admin_session,
    issue_session, normalize_email, require_account_auth,
    validate_password, verify_password,
)

router = APIRouter(prefix="/auth", tags=["Account authentication"])


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)
    role: str = Field(..., pattern="^(patient|clinician)$")


class PatientRegistration(BaseModel):
    display_name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=12, max_length=128)
    clinic_id: str = Field(..., min_length=1, max_length=100)
    clinician_id: str = Field(..., min_length=1, max_length=100)


class AdminLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class ClinicianCreateRequest(BaseModel):
    display_name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=12, max_length=128)
    clinic_id: str = Field(..., min_length=1, max_length=100)


def _account_collection():
    if mongodb.db is None:
        raise HTTPException(503, detail={"code": "DATABASE_UNAVAILABLE", "message": "Service unavailable"})
    return mongodb.db.user_accounts


def _create_link_in_session(session: Any, patient_id: str, clinic_id: str, clinician_id: str) -> None:
    now = datetime.utcnow()
    mongodb.db.patient_access.update_one(
        {"client_id": clinic_id, "patient_id": patient_id},
        {"$set": {"clinic_id": clinic_id, "patient_id": patient_id,
                   "care_clinician_id": clinician_id, "updated_at": now},
         "$setOnInsert": {"created_at": now},
         "$addToSet": {"authorised_clinicians": clinician_id, "authorized_clinicians": clinician_id}},
        upsert=True, session=session,
    )


@router.get("/clinics", summary="Clínicas con clínicos habilitados para registro")
def list_registration_clinics() -> list[dict[str, Any]]:
    require_account_auth()
    accounts = _account_collection()
    result = []
    for clinic in CLINICS_CATALOG:
        clinicians = list(accounts.find(
            {"client_id": clinic["id"], "role": "clinician", "active": True},
            {"_id": 0, "clinician_id": 1, "display_name": 1},
        ).sort("display_name", 1))
        if clinicians:
            result.append({"id": clinic["id"], "name": clinic["name"],
                           "clinicians": [{"id": row["clinician_id"], "name": row["display_name"]}
                                          for row in clinicians]})
    return result


@router.get("/catalog/clinics", summary="Catálogo de clínicas para el alta administrada")
def list_clinic_catalog() -> list[dict[str, str]]:
    require_account_auth()
    return [{"id": clinic["id"], "name": clinic["name"]} for clinic in CLINICS_CATALOG]


@router.post("/patient/register", summary="Auto-registro de paciente")
def register_patient(body: PatientRegistration, request: Request) -> dict[str, Any]:
    require_account_auth()
    email = normalize_email(body.email)
    password = validate_password(body.password)
    name = " ".join(body.display_name.split())
    if len(name) < 2:
        raise HTTPException(422, detail={"code": "INVALID_NAME", "message": "Enter the patient's name"})
    _rate_limit(request, "register", email, maximum=5)
    clinic = clinic_by_id(body.clinic_id)
    clinician = _account_collection().find_one({"client_id": body.clinic_id,
        "clinician_id": body.clinician_id, "role": "clinician", "active": True}, {"_id": 1})
    if not clinic or not clinician:
        raise HTTPException(422, detail={"code": "CLINICIAN_UNAVAILABLE", "message": "Choose an active clinician at an available clinic"})
    patient_id = uuid4().hex
    now = datetime.utcnow()
    account = {"client_id": body.clinic_id, "account_id": patient_id, "patient_id": patient_id,
        "role": "patient", "display_name": name, "email": email,
        "password_hash": hash_password(password), "active": True, "created_at": now,
        "updated_at": now, "password_changed_at": now}
    try:
        with mongodb.client.start_session() as session:
            with session.start_transaction():
                _account_collection().insert_one(account, session=session)
                _create_link_in_session(session, patient_id, body.clinic_id, body.clinician_id)
    except DuplicateKeyError:
        raise HTTPException(409, detail={"code": "ACCOUNT_EXISTS", "message": "An account with these details already exists"})
    return issue_session(role="patient", client_id=body.clinic_id, resource_id=patient_id,
                         display_name=name)


@router.post("/login", summary="Iniciar sesión de paciente o clínico")
def login(body: LoginRequest, request: Request) -> dict[str, Any]:
    require_account_auth()
    try:
        email = normalize_email(body.email)
    except HTTPException:
        email = "invalid"
    _rate_limit(request, "login", email, maximum=12)
    account = _account_collection().find_one({"email": email, "role": body.role, "active": True})
    password_ok = verify_password(body.password, account.get("password_hash", "") if account else _DUMMY_PASSWORD_HASH)
    valid = bool(account and password_ok)
    if not valid:
        raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect"},
                            headers={"WWW-Authenticate": "Bearer"})
    resource_id = account["patient_id"] if body.role == "patient" else account["clinician_id"]
    return issue_session(role=body.role, client_id=account["client_id"], resource_id=resource_id,
                         display_name=account.get("display_name"))


@router.post("/admin/login", summary="Inicio de sesión del administrador de plataforma")
def admin_login(body: AdminLoginRequest, request: Request) -> dict[str, Any]:
    require_account_auth()
    configured_email = (settings.PLATFORM_ADMIN_EMAIL or "").strip().lower()
    password_hash = settings.PLATFORM_ADMIN_PASSWORD_HASH or ""
    try:
        email = normalize_email(body.email)
    except HTTPException:
        email = "invalid"
    _rate_limit(request, "admin-login", email, maximum=6)
    if not configured_email or not password_hash:
        raise HTTPException(503, detail={"code": "ADMIN_NOT_CONFIGURED", "message": "Platform administrator is not configured"})
    password_ok = verify_password(body.password, password_hash or _DUMMY_PASSWORD_HASH)
    valid = hmac.compare_digest(email.encode(), configured_email.encode()) and password_ok
    if not valid:
        raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect"},
                            headers={"WWW-Authenticate": "Bearer"})
    return issue_admin_session(email)


@router.get("/admin/clinicians", summary="Listar clínicos activos (solo admin)")
def list_clinicians(_admin=Depends(get_platform_admin)) -> list[dict[str, Any]]:
    require_account_auth()
    rows = _account_collection().find({"role": "clinician"},
        {"_id": 0, "clinician_id": 1, "display_name": 1, "email": 1, "client_id": 1, "active": 1}).sort("display_name", 1)
    return [{"id": r["clinician_id"], "name": r["display_name"], "email": r["email"],
             "clinic_id": r["client_id"], "active": bool(r.get("active"))} for r in rows]


@router.post("/admin/clinicians", status_code=201, summary="Crear cuenta clínica (solo admin)")
def create_clinician(body: ClinicianCreateRequest,
                           admin=Depends(get_platform_admin)) -> dict[str, Any]:
    require_account_auth()
    email = normalize_email(body.email)
    password = validate_password(body.password)
    name = " ".join(body.display_name.split())
    clinic = clinic_by_id(body.clinic_id)
    if len(name) < 2 or not clinic:
        raise HTTPException(422, detail={"code": "INVALID_CLINICIAN", "message": "Enter a valid name and clinic"})
    clinician_id = uuid4().hex
    now = datetime.utcnow()
    account = {"client_id": body.clinic_id, "account_id": clinician_id, "clinician_id": clinician_id,
        "role": "clinician", "display_name": name, "email": email,
        "password_hash": hash_password(password), "active": True, "created_at": now,
        "updated_at": now, "password_changed_at": now}
    try:
        with mongodb.client.start_session() as session:
            with session.start_transaction():
                _account_collection().insert_one(account, session=session)
                mongodb.db.audit_events.insert_one({"client_id": "wellq_platform", "event_type": "clinician_account_created",
                    "actor_id": admin.admin_id, "target_id": clinician_id, "clinic_id": body.clinic_id,
                    "email_hash": hashlib.sha256(email.encode()).hexdigest(), "occurred_at": now}, session=session)
    except DuplicateKeyError:
        raise HTTPException(409, detail={"code": "ACCOUNT_EXISTS", "message": "An account with these details already exists"})
    return {"id": clinician_id, "name": name, "email": email, "clinic_id": body.clinic_id, "active": True}


@router.delete("/admin/clinicians/{clinician_id}", summary="Desactivar cuenta clínica (solo admin)")
def deactivate_clinician(clinician_id: str,
                               admin=Depends(get_platform_admin)) -> dict[str, str]:
    require_account_auth()
    now = datetime.utcnow()
    with mongodb.client.start_session() as session:
        with session.start_transaction():
            result = _account_collection().update_one({"role": "clinician", "clinician_id": clinician_id},
                {"$set": {"active": False, "updated_at": now}}, session=session)
            if result.matched_count != 1:
                raise HTTPException(404, detail={"code": "CLINICIAN_NOT_FOUND", "message": "Clinician not found"})
            mongodb.db.audit_events.insert_one({"client_id": "wellq_platform", "event_type": "clinician_account_disabled",
                "actor_id": admin.admin_id, "target_id": clinician_id, "occurred_at": now}, session=session)
    return {"status": "disabled", "clinician_id": clinician_id}
