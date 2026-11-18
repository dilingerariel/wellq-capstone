"""Endpoints dummy de demostración y multi-tenancy para WellQ.

Permite:
1. Listar clínicas disponibles para el selector de login (GET /api/v1/demo/clinics).
2. Vincular un paciente a una clínica/médico en `patient_access` (POST /api/v1/demo/link-patient).
3. Obtener un token JWT RS256 firmado para pruebas (POST /api/v1/demo/login y POST /api/v1/demo/token).
4. Consultar los accesos de un paciente (GET /api/v1/demo/patient-links/{patient_id}).
"""

from datetime import datetime
import time
from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import settings
from app.database import mongodb

router = APIRouter(prefix="/demo", tags=["Demo & Multi-Tenancy"])
SYNTHETIC_PDF_SHA256 = "3331e1f6f50397609563dacbdf46d5c6f41d3d530c9f8e3697d136915c4907a6"
SYNTHETIC_PDF_SIZE = 2485

# Catálogo oficial de clínicas y profesionales para la demostración
CLINICS_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "clinica_alemana",
        "name": "Clinica Alemana",
        "clinicians": [
            {"id": "rene_faundez", "name": "Rene Faundez"},
            {"id": "medico_demo_alemana", "name": "Clinico sintetico Alemana"},
        ],
    },
    {
        "id": "clinica_santa_maria",
        "name": "Clinica Santa Maria",
        "clinicians": [
            {"id": "dra_soto", "name": "Clinico sintetico Santa Maria"},
            {"id": "clinico_demo_sm", "name": "Clinico alternativo Santa Maria"},
        ],
    },
]

# Clave privada RSA singleton en memoria para firmar tokens en entorno demo si no existe otra
_demo_private_key: Optional[rsa.RSAPrivateKey] = None


def require_demo_auth() -> None:
    # This issuer is intentionally limited to synthetic, non-production runs.
    if not settings.DEMO_AUTH_ENABLED or settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Not found"})


def require_legacy_demo_login() -> None:
    """Legacy public token minting is off unless an operator explicitly enables it."""
    if not settings.LEGACY_DEMO_LOGIN_ENABLED:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Not found"})
    require_demo_auth()


def require_demo_storage() -> None:
    require_demo_auth()
    if not settings.DEMO_MONGO_STORAGE_ENABLED:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Not found"})


def verify_storage_capability(token: str, purpose: str) -> Dict[str, Any]:
    try:
        claims = jwt.decode(token, settings.JWT_PUBLIC_KEY, algorithms=["RS256"],
                            issuer=settings.JWT_ISSUER, audience=settings.JWT_AUDIENCE)
        if claims.get("purpose") != purpose or claims.get("client_id") != "clinica_alemana":
            raise ValueError()
        return claims
    except Exception:
        raise HTTPException(status_code=403, detail={"code": "INVALID_STORAGE_CAPABILITY", "message": "Upload authorization expired or invalid"})


@router.put("/storage/upload", status_code=204, include_in_schema=False)
async def upload_synthetic_object(request: Request):
    """Accept only the immutable sample PDF; never a patient supplied document."""
    require_demo_storage()
    token = request.headers.get("x-wellq-upload-token", "")
    claims = verify_storage_capability(token, "demo_upload")
    object_key = claims.get("object_key")
    patient_id = claims.get("patient_id")
    from app.database import mongodb
    account = mongodb.db.user_accounts.find_one({"client_id": claims["client_id"],
        "patient_id": patient_id, "role": "patient", "active": True}, {"_id": 1})
    access = mongodb.db.patient_access.find_one({"client_id": claims["client_id"],
        "patient_id": patient_id}, {"_id": 1})
    if (not isinstance(object_key, str) or not object_key.startswith("quarantine/clinical-tests/")
            or not isinstance(patient_id, str) or not patient_id or not account or not access
            or claims.get("expected_size") != SYNTHETIC_PDF_SIZE
            or claims.get("expected_sha256") != SYNTHETIC_PDF_SHA256
            or request.headers.get("x-wellq-if-absent") != "true"
            or request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/pdf"):
        raise HTTPException(status_code=403, detail={"code": "SYNTHETIC_FILE_REQUIRED", "message": "Only the fixed synthetic PDF is accepted"})
    length = request.headers.get("content-length")
    if length and length != str(SYNTHETIC_PDF_SIZE):
        raise HTTPException(status_code=413, detail={"code": "FILE_TOO_LARGE", "message": "Synthetic file size mismatch"})
    data = await request.body()
    import hashlib
    if len(data) != SYNTHETIC_PDF_SIZE or hashlib.sha256(data).hexdigest() != SYNTHETIC_PDF_SHA256:
        raise HTTPException(status_code=422, detail={"code": "SYNTHETIC_FILE_REQUIRED", "message": "Only the fixed synthetic PDF is accepted"})
    from pymongo.errors import DuplicateKeyError
    document = {"client_id": claims["client_id"], "object_key": object_key,
                "patient_id": patient_id,
                "capability_id": claims["jti"],
                "content_type": "application/pdf", "size_bytes": len(data),
                "sha256": SYNTHETIC_PDF_SHA256, "generation": 1, "data": data,
                "created_at": datetime.utcnow()}
    try:
        mongodb.db.demo_objects.insert_one(document)
    except DuplicateKeyError:
        existing = mongodb.db.demo_objects.find_one({"client_id": claims["client_id"], "capability_id": claims["jti"]})
        if (not existing or existing.get("sha256") != SYNTHETIC_PDF_SHA256
                or existing.get("object_key") != object_key):
            raise HTTPException(status_code=412, detail={"code": "OBJECT_CONFLICT", "message": "Object already exists"})
    return Response(status_code=204)


@router.get("/storage/download", include_in_schema=False)
async def download_synthetic_object(token: str):
    require_demo_storage()
    claims = verify_storage_capability(token, "demo_download")
    object_key = claims.get("object_key")
    from app.database import mongodb
    stored = mongodb.db.demo_objects.find_one({"client_id": claims["client_id"], "object_key": object_key,
                                               "generation": claims.get("generation")})
    if not stored:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Not found"})
    return Response(bytes(stored["data"]), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="synthetic.pdf"',
                             "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


def clinic_and_clinician_exist(clinic_id: str, clinician_id: Optional[str]) -> bool:
    clinic = next((item for item in CLINICS_CATALOG if item["id"] == clinic_id), None)
    return bool(clinic and (clinician_id is None or any(d["id"] == clinician_id for d in clinic["clinicians"])))


def get_demo_private_key() -> rsa.RSAPrivateKey:
    global _demo_private_key
    if _demo_private_key is None:
        configured_key = settings.DEMO_JWT_PRIVATE_KEY
        if configured_key:
            key = load_pem_private_key(configured_key.replace("\\n", "\n").encode("utf-8"), password=None)
            if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
                raise RuntimeError("Demo identity requires an RSA private key of at least 2048 bits")
            _demo_private_key = key
        elif settings.DEMO_MONGO_STORAGE_ENABLED:
            raise RuntimeError("A stable RSA private key is required for the deployed demo")
        elif settings.JWT_PUBLIC_KEY:
            raise RuntimeError("Demo JWT private key is required when a public verification key is configured")
        else:
            _demo_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    public_key = _demo_private_key.public_key()
    public_pem = public_key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    if settings.JWT_PUBLIC_KEY:
        configured_public = serialization.load_pem_public_key(settings.JWT_PUBLIC_KEY.encode("utf-8"))
        if configured_public.public_numbers() != public_key.public_numbers():
            raise RuntimeError("Demo signing key does not match the configured JWT public key")
    else:
        settings.JWT_PUBLIC_KEY = public_pem
    if not settings.JWT_ISSUER:
        settings.JWT_ISSUER = "https://identity.wellq-demo.invalid"
    if not settings.JWT_AUDIENCE:
        settings.JWT_AUDIENCE = "wellq-demo"
    return _demo_private_key


def set_demo_private_key(key: rsa.RSAPrivateKey) -> None:
    """Permite fijar la clave privada desde fixtures o pruebas."""
    global _demo_private_key
    _demo_private_key = key


def prepare_demo_identity() -> None:
    """Prepare a stable verifier before startup in an isolated non-production demo."""
    require_demo_auth()
    get_demo_private_key()
    settings.validate_identity()


class LinkPatientRequest(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=200, description="ID del paciente")
    clinic_id: str = Field(..., min_length=1, max_length=200, description="ID de la clínica (tenant)")
    clinician_id: str = Field(..., min_length=1, max_length=200, description="ID del médico autorizado")


class DemoLoginRequest(BaseModel):
    role: Literal["clinician", "patient"] = "clinician"
    client_id: str = Field("clinica_alemana", min_length=1, max_length=200)
    clinician_id: Optional[str] = Field(None, max_length=200)
    patient_id: Optional[str] = Field(None, max_length=200)


@router.get("/clinics", summary="Lista de clínicas disponibles")
async def list_clinics() -> List[Dict[str, Any]]:
    """Devuelve la lista de clínicas y médicos disponibles para poblar el login."""
    return CLINICS_CATALOG


@router.post("/link-patient", summary="Vincular paciente a una clínica y médico")
async def link_patient(request: LinkPatientRequest) -> Dict[str, Any]:
    """
    Asocia un `patient_id` con un `clinic_id` (y opcionalmente `clinician_id`)
    guardando o actualizando la relación en la colección `patient_access`.
    """
    require_legacy_demo_login()
    if (request.patient_id != "paciente_ariel_demo" or request.clinic_id != "clinica_alemana"
            or request.clinician_id != "rene_faundez"):
        raise HTTPException(status_code=422, detail={"code": "INVALID_DEMO_LINK", "message": "Invalid demo identity"})
    if not clinic_and_clinician_exist(request.clinic_id, request.clinician_id):
        raise HTTPException(status_code=422, detail={"code": "INVALID_DEMO_LINK", "message": "Invalid demo identity"})

    raw_db = mongodb.db
    if raw_db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DATABASE_UNAVAILABLE", "message": "Database unavailable"},
        )

    now = datetime.utcnow()
    filter_doc = {"client_id": request.clinic_id, "patient_id": request.patient_id}
    update_doc: Dict[str, Any] = {
        "$set": {
            "clinic_id": request.clinic_id,
            "patient_id": request.patient_id,
            "updated_at": now,
        },
        "$setOnInsert": {
            "created_at": now,
        },
    }

    update_doc["$addToSet"] = {
        "authorised_clinicians": request.clinician_id,
        "authorized_clinicians": request.clinician_id,
    }

    raw_db.patient_access.update_one(filter_doc, update_doc, upsert=True)

    return {
        "status": "linked",
        "patient_id": request.patient_id,
        "clinic_id": request.clinic_id,
        "clinician_id": request.clinician_id,
        "message": f"Paciente '{request.patient_id}' vinculado exitosamente a '{request.clinic_id}'",
    }


@router.get("/patient-links/{patient_id}", summary="Consultar clínicas vinculadas a un paciente")
async def get_patient_links(patient_id: str) -> Dict[str, Any]:
    """Devuelve los registros en patient_access para este paciente."""
    require_legacy_demo_login()
    if patient_id != "paciente_ariel_demo":
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Not found"})
    raw_db = mongodb.db
    if raw_db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DATABASE_UNAVAILABLE", "message": "Database unavailable"},
        )
    cursor = raw_db.patient_access.find({"patient_id": patient_id})
    links = []
    for doc in cursor:
        doc_copy = dict(doc)
        doc_copy.pop("_id", None)
        links.append(doc_copy)
    return {"patient_id": patient_id, "links": links}


@router.post("/login", summary="Login demo que emite JWT firmado con RS256")
@router.post("/token", summary="Alias de login demo")
async def demo_login(request: DemoLoginRequest) -> Dict[str, Any]:
    """
    Genera un token JWT RS256 válido para la clínica y médico o paciente seleccionados.
    Cumple con el esquema requerido por el Portal React y la App Móvil.
    """
    require_legacy_demo_login()
    clinic = next((item for item in CLINICS_CATALOG if item["id"] == request.client_id), None)
    clinician_id = request.clinician_id
    if request.role == "clinician" and clinician_id is None and clinic:
        clinician_id = clinic["clinicians"][0]["id"]
    if not clinic_and_clinician_exist(request.client_id, clinician_id if request.role == "clinician" else None):
        raise HTTPException(status_code=422, detail={"code": "INVALID_DEMO_IDENTITY", "message": "Invalid demo identity"})
    if request.role == "patient" and (request.patient_id not in (None, "paciente_ariel_demo") or request.client_id != "clinica_alemana"):
        raise HTTPException(status_code=422, detail={"code": "INVALID_DEMO_IDENTITY", "message": "Invalid demo identity"})

    role = request.role
    client_id = request.client_id
    if role == "clinician":
        resource_id = clinician_id
        clinician_id = resource_id
        patient_id = None
        permissions = [
            "clinical:read",
            "clinical:write",
            "documents:download",
            "extractions:validate",
            "clinical:review",
            "reports:export",
        ]
        capabilities = ["report_export"]
    else:
        resource_id = request.patient_id or "paciente_ariel_demo"
        patient_id = resource_id
        clinician_id = None
        permissions = [
            "clinical:read",
            "clinical:write",
            "documents:download",
            "extractions:confirm",
        ]
        capabilities = []

    now = int(time.time())
    expires_at = now + settings.JWT_MAX_LIFETIME_SECONDS

    issuer = settings.JWT_ISSUER or "https://identity.wellq-demo.invalid"
    audience = settings.JWT_AUDIENCE or "wellq-demo"

    payload: Dict[str, Any] = {
        "sub": f"demo:{role}:{resource_id}",
        "role": role,
        "client_id": client_id,
        "resource_id": resource_id,
        "iat": now,
        "nbf": now,
        "exp": expires_at,
        "iss": issuer,
        "aud": audience,
        "permissions": permissions,
        "capabilities": capabilities,
    }
    if role == "patient":
        payload["patient_id"] = patient_id
    else:
        payload["clinician_id"] = clinician_id

    private_key = get_demo_private_key()
    token = jwt.encode(payload, private_key, algorithm="RS256")

    return {
        "accessToken": token,
        "role": role,
        "tenantId": client_id,
        "resourceId": resource_id,
        "permissions": permissions,
        "capabilities": capabilities,
        "expiresAt": expires_at,
    }
