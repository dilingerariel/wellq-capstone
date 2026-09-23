from fastapi import APIRouter, Depends, HTTPException, status, Header, BackgroundTasks
from pymongo.database import Database
from typing import Optional, List
import uuid
import time
import base64
from datetime import datetime

from app.models.schemas import (
    InitiateUploadRequest, InitiateUploadResponse,
    RefreshUrlRequest, RefreshUrlResponse,
    CompleteUploadRequest, CompleteUploadResponse,
    UploadStatusResponse, SignedUrlResponse, ProcessingStatus,
    EditClinicalTestRequest, ReviewRequest, DownloadUrlResponse,
    ClinicalTestResponse, ListClinicalTestsResponse, FileInfo, ReviewInfo
)
from app.models.enums import UploadStatus, ReviewStatus, ScanStatus, ErrorCode, TestType
from app.dependencies.auth import get_current_patient, get_current_clinician, TokenPayload, get_current_user
from app.dependencies.access import require_clinician_access, require_patient_access
from app.database import get_database
from app.services.storage import storage_service
from app.config import settings

router = APIRouter()

def process_upload_validation(upload_id: str):
    """Tarea en segundo plano que simula validación de MIME y escaneo de malware"""
    time.sleep(2)  # Simula tiempo de escaneo
    try:
        db = get_database()
        db.clinical_tests.update_one(
            {"upload.upload_id": upload_id},
            {
                "$set": {
                    "upload.status": UploadStatus.READY_FOR_REVIEW.value,
                    "upload.validated_at": datetime.utcnow(),
                    "upload.processing_status": {
                        "malware_scan": ScanStatus.PASSED.value,
                        "mime_validation": ScanStatus.PASSED.value,
                    },
                    "updated_at": datetime.utcnow(),
                }
            }
        )
    except Exception as e:
        print(f"Error procesando validación para {upload_id}: {e}")

# ============ ENDPOINT 1: INITIATE UPLOAD ============

@router.post(
    "/clinical-tests/uploads/initiate",
    response_model=InitiateUploadResponse,
    status_code=201,
)
async def initiate_upload(
    request: InitiateUploadRequest,
    idempotency_key: str = Header(...),
    current_patient: str = Depends(get_current_patient),
    db: Database = Depends(get_database),
):
    """
    POST /api/v1/clinical-tests/uploads/initiate
    Crear sesión de subida e obtener URL firmada de GCS
    """
    # 1. Validación de MIME Type en lista blanca
    if request.mime_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": ErrorCode.INVALID_METADATA.value,
                "message": f"MIME type no permitido: '{request.mime_type}'. Permitidos: {settings.ALLOWED_MIME_TYPES}"
            }
        )

    # 2. Validación de tamaño máximo
    if request.size_bytes > settings.MAX_CLINICAL_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_METADATA.value,
                "message": f"Tamaño de archivo excede el máximo permitido ({settings.MAX_CLINICAL_FILE_BYTES // (1024 * 1024)}MB)"
            }
        )

    # 3. Límite de subidas pendientes simultáneas por paciente
    pending_count = db.clinical_tests.count_documents({
        "patient_id": current_patient,
        "upload.status": UploadStatus.INITIATED.value,
        "deleted_at": None,
    })
    if pending_count >= settings.MAX_PENDING_UPLOADS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": ErrorCode.RATE_LIMITED.value,
                "message": f"Límite de subidas pendientes alcanzado ({settings.MAX_PENDING_UPLOADS})"
            }
        )

    # 4. Idempotencia: Verificar client_upload_id existente para este paciente
    existing = db.clinical_tests.find_one({
        "patient_id": current_patient,
        "upload.client_upload_id": request.client_upload_id,
        "deleted_at": None,
    })
    if existing:
        if existing.get("file", {}).get("sha256") == request.sha256:
            # Reintento idempotente: Devolver sesión existente
            upload_info = storage_service.generate_upload_url(
                object_key=existing["file"]["gcs_object_key"],
                content_type=request.mime_type,
                expiration_minutes=settings.SIGNED_URL_EXPIRATION_MINUTES,
            )
            return InitiateUploadResponse(
                upload_id=existing["upload"]["upload_id"],
                clinical_test_id=existing["clinical_test_id"],
                status=UploadStatus(existing["upload"]["status"]),
                upload=SignedUrlResponse(**upload_info),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": ErrorCode.UPLOAD_CONFLICT.value,
                    "message": "El client_upload_id ya existe con datos o checksum diferentes"
                }
            )

    # 5. Generar identificadores y clave de almacenamiento en GCS
    unique_id = uuid.uuid4().hex[:12]
    clinical_test_id = f"ct_{unique_id}"
    upload_id = f"ctu_{unique_id}"
    object_key = f"private/clinical-tests/{current_patient}/{clinical_test_id}/original"

    # 6. Generar URL firmada V4
    upload_info = storage_service.generate_upload_url(
        object_key=object_key,
        content_type=request.mime_type,
        expiration_minutes=settings.SIGNED_URL_EXPIRATION_MINUTES,
    )

    # 7. Persistir documento en MongoDB
    doc = {
        "clinical_test_id": clinical_test_id,
        "patient_id": current_patient,
        "title": request.title,
        "test_type": request.test_type.value,
        "test_date": request.test_date,
        "patient_notes": request.notes,
        "case_id": request.case_id,
        "appointment_id": request.appointment_id,
        "file": {
            "original_name": request.file_name,
            "mime_type": request.mime_type,
            "size_bytes": request.size_bytes,
            "sha256": request.sha256,
            "gcs_object_key": object_key,
            "media_id": None,
        },
        "upload": {
            "upload_id": upload_id,
            "client_upload_id": request.client_upload_id,
            "idempotency_key": idempotency_key,
            "status": UploadStatus.INITIATED.value,
            "refresh_count": 0,
            "expires_at": upload_info["expires_at"],
            "validated_at": None,
            "rejection": None,
            "processing_status": {
                "malware_scan": ScanStatus.PENDING.value,
                "mime_validation": ScanStatus.PENDING.value,
            }
        },
        "review": {
            "status": ReviewStatus.NOT_REVIEWED.value,
            "reviewed_at": None,
            "reviewed_by": None,
            "private_note": None,
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "deleted_at": None,
    }

    db.clinical_tests.insert_one(doc)

    return InitiateUploadResponse(
        upload_id=upload_id,
        clinical_test_id=clinical_test_id,
        status=UploadStatus.INITIATED,
        upload=SignedUrlResponse(**upload_info),
    )

# ============ ENDPOINT 2: REFRESH URL ============

@router.post(
    "/clinical-tests/uploads/{upload_id}/refresh-url",
    response_model=RefreshUrlResponse,
)
async def refresh_url(
    upload_id: str,
    request: RefreshUrlRequest,
    idempotency_key: str = Header(...),
    current_patient: str = Depends(get_current_patient),
    db: Database = Depends(get_database),
):
    """
    POST /api/v1/clinical-tests/uploads/{upload_id}/refresh-url
    Reemplazar URL firmada expirada sin duplicar registro
    """
    doc = db.clinical_tests.find_one({
        "upload.upload_id": upload_id,
        "patient_id": current_patient,
        "deleted_at": None,
    })

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.UPLOAD_NOT_FOUND.value,
                "message": "Sesión de subida no encontrada"
            }
        )

    # Validar que la sesión siga en estado initiated
    if doc["upload"]["status"] != UploadStatus.INITIATED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": ErrorCode.UPLOAD_NOT_REFRESHABLE.value,
                "message": f"La sesión no puede refrescarse en estado '{doc['upload']['status']}'"
            }
        )

    # Validar integridad: SHA-256 y client_upload_id coinciden
    if doc["file"]["sha256"] != request.sha256 or doc["upload"]["client_upload_id"] != request.client_upload_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.OBJECT_MISMATCH.value,
                "message": "El SHA-256 o client_upload_id no coinciden con la sesión original"
            }
        )

    # Rate limiting: máximo 10 refrescos por sesión
    refresh_count = doc["upload"].get("refresh_count", 0)
    if refresh_count >= settings.MAX_URL_REFRESHES_PER_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": ErrorCode.RATE_LIMITED.value,
                "message": f"Límite de refrescos alcanzado (máximo {settings.MAX_URL_REFRESHES_PER_UPLOAD})"
            }
        )

    # Generar nueva URL firmada
    upload_info = storage_service.generate_upload_url(
        object_key=doc["file"]["gcs_object_key"],
        content_type=doc["file"]["mime_type"],
        expiration_minutes=settings.SIGNED_URL_EXPIRATION_MINUTES,
    )

    # Actualizar contador y expiración en MongoDB
    db.clinical_tests.update_one(
        {"_id": doc["_id"]},
        {
            "$inc": {"upload.refresh_count": 1},
            "$set": {
                "upload.expires_at": upload_info["expires_at"],
                "updated_at": datetime.utcnow(),
            }
        }
    )

    return RefreshUrlResponse(
        upload_id=upload_id,
        status=UploadStatus.INITIATED,
        upload=SignedUrlResponse(**upload_info),
    )

# ============ ENDPOINT 3: COMPLETE UPLOAD ============

@router.post(
    "/clinical-tests/uploads/{upload_id}/complete",
    response_model=CompleteUploadResponse,
)
async def complete_upload(
    upload_id: str,
    request: CompleteUploadRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(...),
    current_patient: str = Depends(get_current_patient),
    db: Database = Depends(get_database),
):
    """
    POST /api/v1/clinical-tests/uploads/{upload_id}/complete
    Señalar que transferencia terminó. Verificar y encolar validación.
    REGLA: local_file_can_be_deleted = false SIEMPRE en esta etapa.
    """
    doc = db.clinical_tests.find_one({
        "upload.upload_id": upload_id,
        "patient_id": current_patient,
        "deleted_at": None,
    })

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.UPLOAD_NOT_FOUND.value,
                "message": "Sesión de subida no encontrada"
            }
        )

    # Idempotencia: Si ya está en processing o ready_for_review, devolver respuesta exitosa
    if doc["upload"]["status"] in [UploadStatus.PROCESSING.value, UploadStatus.READY_FOR_REVIEW.value]:
        return CompleteUploadResponse(
            clinical_test_id=doc["clinical_test_id"],
            upload_id=upload_id,
            status=UploadStatus(doc["upload"]["status"]),
            local_file_can_be_deleted=False,  # REGLA CRÍTICA
            status_url=f"/api/v1/clinical-tests/uploads/{upload_id}/status",
        )

    # Validar que esté en initiated
    if doc["upload"]["status"] != UploadStatus.INITIATED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": ErrorCode.UPLOAD_CONFLICT.value,
                "message": f"No se puede completar una subida en estado '{doc['upload']['status']}'"
            }
        )

    # Validar tamaño y SHA-256
    if doc["file"]["sha256"] != request.sha256 or doc["file"]["size_bytes"] != request.size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.OBJECT_MISMATCH.value,
                "message": "El tamaño o SHA-256 no coinciden con la sesión iniciada"
            }
        )

    # Actualizar estado a processing
    db.clinical_tests.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "upload.status": UploadStatus.PROCESSING.value,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    # Encolar validación en segundo plano
    background_tasks.add_task(process_upload_validation, upload_id)

    return CompleteUploadResponse(
        clinical_test_id=doc["clinical_test_id"],
        upload_id=upload_id,
        status=UploadStatus.PROCESSING,
        local_file_can_be_deleted=False,  # REGLA CRÍTICA: SIEMPRE FALSE
        status_url=f"/api/v1/clinical-tests/uploads/{upload_id}/status",
    )

# ============ ENDPOINT 4: UPLOAD STATUS ============

@router.get(
    "/clinical-tests/uploads/{upload_id}/status",
    response_model=UploadStatusResponse,
)
async def get_upload_status(
    upload_id: str,
    current_patient: str = Depends(get_current_patient),
    db: Database = Depends(get_database),
):
    """
    GET /api/v1/clinical-tests/uploads/{upload_id}/status
    Consultar resultado del procesamiento.
    REGLA: local_file_can_be_deleted = true SOLO si status = ready_for_review
    """
    doc = db.clinical_tests.find_one({
        "upload.upload_id": upload_id,
        "patient_id": current_patient,
        "deleted_at": None,
    })

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.UPLOAD_NOT_FOUND.value,
                "message": "Sesión de subida no encontrada"
            }
        )

    current_status = UploadStatus(doc["upload"]["status"])
    proc_info = doc["upload"].get("processing_status", {})

    # Regla: local_file_can_be_deleted es True SOLO en ready_for_review
    if current_status == UploadStatus.READY_FOR_REVIEW:
        can_delete = True
        malware_scan = ScanStatus.PASSED
        mime_validation = ScanStatus.PASSED
    elif current_status in [UploadStatus.REJECTED, UploadStatus.FAILED]:
        can_delete = False
        malware_scan = ScanStatus.FAILED
        mime_validation = ScanStatus.FAILED
    else:  # INITIATED o PROCESSING
        can_delete = False
        malware_scan = ScanStatus(proc_info.get("malware_scan", ScanStatus.PENDING.value))
        mime_validation = ScanStatus(proc_info.get("mime_validation", ScanStatus.PENDING.value))

    completed_at = None
    if doc["upload"].get("validated_at"):
        completed_at = doc["upload"]["validated_at"].strftime("%Y-%m-%dT%H:%M:%SZ")

    return UploadStatusResponse(
        clinical_test_id=doc["clinical_test_id"],
        upload_id=upload_id,
        status=current_status,
        processing=ProcessingStatus(
            malware_scan=malware_scan,
            mime_validation=mime_validation,
        ),
        local_file_can_be_deleted=can_delete,
        error=doc["upload"].get("rejection"),
        completed_at=completed_at,
    )

# ============ ENDPOINTS 5-11 TODO ============

# ============ HELPER: FORMATEO DE RESPUESTA ============

def format_clinical_test_response(doc: dict) -> ClinicalTestResponse:
    created_at = doc["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", ""))
    updated_at = doc["updated_at"].strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(doc.get("updated_at"), datetime) else str(doc.get("updated_at", ""))
    reviewed_at = doc.get("review", {}).get("reviewed_at")
    if isinstance(reviewed_at, datetime):
        reviewed_at = reviewed_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    return ClinicalTestResponse(
        clinical_test_id=doc["clinical_test_id"],
        patient_id=doc["patient_id"],
        title=doc.get("title", ""),
        test_type=TestType(doc.get("test_type", TestType.OTHER.value)),
        test_date=doc.get("test_date", ""),
        notes=doc.get("patient_notes"),
        case_id=doc.get("case_id"),
        appointment_id=doc.get("appointment_id"),
        file=FileInfo(
            name=doc["file"]["original_name"],
            mime_type=doc["file"]["mime_type"],
            size_bytes=doc["file"]["size_bytes"],
        ),
        status=UploadStatus(doc["upload"]["status"]),
        review=ReviewInfo(
            status=ReviewStatus(doc.get("review", {}).get("status", ReviewStatus.NOT_REVIEWED.value)),
            reviewed_at=reviewed_at,
            reviewed_by=doc.get("review", {}).get("reviewed_by"),
        ),
        created_at=created_at,
        updated_at=updated_at,
    )

# ============ ENDPOINT 5: LIST CLINICAL TESTS (PACIENTE) ============

@router.get(
    "/clinical-tests",
    response_model=ListClinicalTestsResponse,
)
async def list_clinical_tests(
    status: Optional[UploadStatus] = None,
    test_type: Optional[TestType] = None,
    limit: int = 20,
    cursor: Optional[str] = None,
    current_patient: str = Depends(get_current_patient),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #5: GET /api/v1/clinical-tests - Listar resultados de paciente
    Paginación por cursor opaco, límite máx 100, ordenado por test_date desc, created_at desc.
    """
    limit = max(1, min(limit, 100))
    query = {
        "patient_id": current_patient,
        "deleted_at": None,
    }
    if status:
        query["upload.status"] = status.value
    if test_type:
        query["test_type"] = test_type.value

    if cursor:
        try:
            decoded = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
            cursor_dt = datetime.fromisoformat(decoded)
            query["created_at"] = {"$lt": cursor_dt}
        except Exception:
            pass

    docs = list(
        db.clinical_tests.find(query)
        .sort([("test_date", -1), ("created_at", -1)])
        .limit(limit + 1)
    )

    has_more = len(docs) > limit
    results = docs[:limit]
    next_cursor = None
    if has_more and results:
        last_dt = results[-1]["created_at"]
        next_cursor = base64.b64encode(last_dt.isoformat().encode("utf-8")).decode("utf-8")

    items = [format_clinical_test_response(d).dict() for d in results]
    return ListClinicalTestsResponse(items=items, next_cursor=next_cursor)

# ============ ENDPOINT 6: GET CLINICAL TEST DETAIL ============

@router.get(
    "/clinical-tests/{clinical_test_id}",
    response_model=ClinicalTestResponse,
)
async def get_clinical_test(
    clinical_test_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #6: GET /api/v1/clinical-tests/{clinical_test_id} - Detalle de examen
    Accesible por el paciente dueño o un clínico autorizado.
    """
    doc = db.clinical_tests.find_one({
        "clinical_test_id": clinical_test_id,
        "deleted_at": None,
    })
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.NOT_FOUND.value, "message": "Examen médico no encontrado"}
        )

    if user.role == "patient":
        if doc["patient_id"] != user.patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": ErrorCode.FORBIDDEN.value, "message": "No tienes permiso para ver este examen"}
            )
    elif user.role == "clinician":
        await require_clinician_access(doc["patient_id"], user.clinician_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": ErrorCode.FORBIDDEN.value, "message": "Rol no autorizado"}
        )

    return format_clinical_test_response(doc)

# ============ ENDPOINT 7: EDIT METADATA (PACIENTE) ============

@router.patch(
    "/clinical-tests/{clinical_test_id}",
    response_model=ClinicalTestResponse,
)
async def edit_clinical_test(
    clinical_test_id: str,
    request: EditClinicalTestRequest,
    current_patient: str = Depends(get_current_patient),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #7: PATCH /api/v1/clinical-tests/{clinical_test_id} - Editar metadatos
    REGLA CRÍTICA: Solo editable si review.status == not_reviewed.
    """
    doc = db.clinical_tests.find_one({
        "clinical_test_id": clinical_test_id,
        "patient_id": current_patient,
        "deleted_at": None,
    })
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.NOT_FOUND.value, "message": "Examen médico no encontrado"}
        )

    if doc.get("review", {}).get("status") == ReviewStatus.REVIEWED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": ErrorCode.ALREADY_REVIEWED.value,
                "message": "No se pueden editar metadatos de un examen que ya fue revisado por el clínico"
            }
        )

    update_fields = {}
    if request.title is not None:
        update_fields["title"] = request.title
    if request.test_type is not None:
        update_fields["test_type"] = request.test_type.value
    if request.test_date is not None:
        update_fields["test_date"] = request.test_date
    if request.notes is not None:
        update_fields["patient_notes"] = request.notes
    if request.case_id is not None:
        update_fields["case_id"] = request.case_id
    if request.appointment_id is not None:
        update_fields["appointment_id"] = request.appointment_id

    if update_fields:
        update_fields["updated_at"] = datetime.utcnow()
        db.clinical_tests.update_one({"_id": doc["_id"]}, {"$set": update_fields})
        doc = db.clinical_tests.find_one({"_id": doc["_id"]})

    return format_clinical_test_response(doc)

# ============ ENDPOINT 8: SOFT DELETE (PACIENTE) ============

@router.delete(
    "/clinical-tests/{clinical_test_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_clinical_test(
    clinical_test_id: str,
    current_patient: str = Depends(get_current_patient),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #8: DELETE /api/v1/clinical-tests/{clinical_test_id} - Soft delete
    """
    doc = db.clinical_tests.find_one({
        "clinical_test_id": clinical_test_id,
        "patient_id": current_patient,
        "deleted_at": None,
    })
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.NOT_FOUND.value, "message": "Examen médico no encontrado"}
        )

    now = datetime.utcnow()
    db.clinical_tests.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "deleted_at": now,
                "upload.status": UploadStatus.DELETED.value,
                "updated_at": now,
            }
        }
    )
    return {
        "clinical_test_id": clinical_test_id,
        "status": "deleted",
        "deleted_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

# ============ ENDPOINT 9: DOWNLOAD SECURE URL ============

@router.post(
    "/clinical-tests/{clinical_test_id}/download-url",
    response_model=DownloadUrlResponse,
)
async def create_download_url(
    clinical_test_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #9: POST /api/v1/clinical-tests/{clinical_test_id}/download-url
    URL firmada privada de corta duración (5 min) para descarga del archivo original.
    """
    doc = db.clinical_tests.find_one({
        "clinical_test_id": clinical_test_id,
        "deleted_at": None,
    })
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.NOT_FOUND.value, "message": "Examen médico no encontrado"}
        )

    if user.role == "patient":
        if doc["patient_id"] != user.patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": ErrorCode.FORBIDDEN.value, "message": "No tienes acceso a este examen"}
            )
    elif user.role == "clinician":
        await require_clinician_access(doc["patient_id"], user.clinician_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": ErrorCode.FORBIDDEN.value, "message": "Rol no autorizado"}
        )

    if doc["upload"]["status"] not in [UploadStatus.READY_FOR_REVIEW.value, UploadStatus.PROCESSING.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.DOCUMENT_NOT_READY.value,
                "message": "El documento aún no está listo para descarga"
            }
        )

    download_info = storage_service.generate_download_url(
        object_key=doc["file"]["gcs_object_key"],
        expiration_minutes=settings.DOWNLOAD_URL_EXPIRATION_MINUTES,
    )

    return DownloadUrlResponse(
        url=download_info["url"],
        expires_at=download_info["expires_at"],
        file_name=doc["file"]["original_name"],
    )

# ============ ENDPOINT 10: LIST PATIENT TESTS (CLÍNICO) ============

@router.get(
    "/patients/{patient_id}/clinical-tests",
    response_model=ListClinicalTestsResponse,
)
async def list_patient_clinical_tests(
    patient_id: str,
    status: Optional[UploadStatus] = None,
    test_type: Optional[TestType] = None,
    limit: int = 20,
    cursor: Optional[str] = None,
    current_clinician: str = Depends(get_current_clinician),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #10: GET /api/v1/patients/{patient_id}/clinical-tests - Listar para clínico
    """
    await require_clinician_access(patient_id, current_clinician)

    limit = max(1, min(limit, 100))
    query = {
        "patient_id": patient_id,
        "deleted_at": None,
    }
    if status:
        query["upload.status"] = status.value
    if test_type:
        query["test_type"] = test_type.value

    if cursor:
        try:
            decoded = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
            cursor_dt = datetime.fromisoformat(decoded)
            query["created_at"] = {"$lt": cursor_dt}
        except Exception:
            pass

    docs = list(
        db.clinical_tests.find(query)
        .sort([("test_date", -1), ("created_at", -1)])
        .limit(limit + 1)
    )

    has_more = len(docs) > limit
    results = docs[:limit]
    next_cursor = None
    if has_more and results:
        last_dt = results[-1]["created_at"]
        next_cursor = base64.b64encode(last_dt.isoformat().encode("utf-8")).decode("utf-8")

    items = [format_clinical_test_response(d).dict() for d in results]
    return ListClinicalTestsResponse(items=items, next_cursor=next_cursor)

# ============ ENDPOINT 11: REVIEW TEST (CLÍNICO) ============

@router.patch(
    "/clinical-tests/{clinical_test_id}/review",
    response_model=ClinicalTestResponse,
)
async def review_clinical_test(
    clinical_test_id: str,
    request: ReviewRequest,
    current_clinician: str = Depends(get_current_clinician),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #11: PATCH /api/v1/clinical-tests/{clinical_test_id}/review - Revisión clínica
    """
    doc = db.clinical_tests.find_one({
        "clinical_test_id": clinical_test_id,
        "deleted_at": None,
    })
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.NOT_FOUND.value, "message": "Examen médico no encontrado"}
        )

    await require_clinician_access(doc["patient_id"], current_clinician)

    now = datetime.utcnow()
    db.clinical_tests.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "review.status": ReviewStatus.REVIEWED.value,
                "review.reviewed_at": now,
                "review.reviewed_by": current_clinician,
                "review.private_note": request.review_note,
                "updated_at": now,
            }
        }
    )
    updated_doc = db.clinical_tests.find_one({"_id": doc["_id"]})
    return format_clinical_test_response(updated_doc)