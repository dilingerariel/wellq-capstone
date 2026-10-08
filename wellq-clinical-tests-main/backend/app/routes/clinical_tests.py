from fastapi import APIRouter, Depends, HTTPException, status, Header, BackgroundTasks, Query
from pymongo.database import Database
from pydantic import BaseModel, Field
from bson import ObjectId
from typing import Optional, List
from xml.sax.saxutils import escape as _xml_escape
import uuid
import time
import base64
import calendar
import hashlib
import io
import json
from datetime import datetime, date as _date

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
from app.services.catalog import catalog_service
from app.config import settings
from app.models.scoring import LabScoreResponse

router = APIRouter()

def process_upload_validation(upload_id: str):
    """Tarea en segundo plano: escaneo de seguridad y ejecución del pipeline de extracción (Componente B)"""
    time.sleep(2)  # Simula tiempo de escaneo
    try:
        db = get_database()
        test_doc = db.clinical_tests.find_one({"upload.upload_id": upload_id})
        if test_doc:
            db.clinical_tests.update_one(
                {"_id": test_doc["_id"]},
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
            # Ejecutar el motor de extracción automáticamente (Componente B)
            from app.services.extractor import extraction_engine
            extraction_engine.run_extraction_pipeline(test_doc["clinical_test_id"], db)
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

# ============ ENDPOINT 18: GET LAB SCORE (SOLO CLÍNICO) ============

def _audit_denied_access(db: Database, resource: str, patient_id: str, user: TokenPayload, reason: str) -> None:
    """Registra en auditoría un intento de acceso denegado (§13.8). Nunca debe romper la petición."""
    try:
        db.audit_events.insert_one({
            "event": "access_denied",
            "resource": resource,
            "patient_id": patient_id,
            "actor_role": getattr(user, "role", None),
            "actor_id": getattr(user, "clinician_id", None) or getattr(user, "patient_id", None),
            "reason": reason,
            "occurred_at": datetime.utcnow(),
        })
    except Exception as e:
        print(f"No se pudo registrar auditoría de acceso denegado: {e}")


@router.get(
    "/patients/{patient_id}/lab-score",
    response_model=LabScoreResponse,
)
async def get_lab_score(
    patient_id: str,
    history: bool = False,
    user: TokenPayload = Depends(get_current_user),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #18: GET /api/v1/patients/{patient_id}/lab-score
    Consultar puntaje vigente e histórico del paciente.
    Solo clínico con relación verificada (§4.2, §9.5.3). El paciente NO ve el puntaje (§1.2).
    Nunca calcula al vuelo: si no hay snapshot, responde 404 NO_SCORE_AVAILABLE con el motivo.
    """
    # Control de acceso: solo clínicos
    if user.role != "clinician":
        _audit_denied_access(db, "lab-score", patient_id, user, "role_not_allowed")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Solo un clínico autorizado puede consultar el puntaje"}
        )

    # Relación asistencial verificada (403 si no existe) + auditoría del intento
    try:
        await require_clinician_access(patient_id, user.clinician_id)
    except HTTPException:
        _audit_denied_access(db, "lab-score", patient_id, user, "no_clinical_relationship")
        raise

    # Snapshot vigente (más reciente; desempate por _id)
    current_snapshot = db.score_snapshots.find_one(
        {"patient_id": patient_id},
        sort=[("computed_at", -1), ("_id", -1)]
    )

    if not current_snapshot:
        # Motivo: sin exámenes confirmados vs. datos insuficientes
        has_markers = db.clinical_markers.count_documents({"patient_id": patient_id}) > 0
        reason = "insufficient_coverage" if has_markers else "no_confirmed_exams"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NO_SCORE_AVAILABLE",
                "reason": reason,
                "message": "No hay puntaje calculado para este paciente"
            }
        )

    current_snapshot.pop("_id", None)

    history_snapshots = None
    if history:
        # §9.5.3: "la lista de snapshots anteriores" => se excluye el vigente
        history_snapshots = list(
            db.score_snapshots.find(
                {"patient_id": patient_id, "snapshot_id": {"$ne": current_snapshot.get("snapshot_id")}}
            ).sort([("computed_at", -1), ("_id", -1)]).limit(50)
        )
        for snap in history_snapshots:
            snap.pop("_id", None)

    return LabScoreResponse(
        current_snapshot=current_snapshot,
        history=history_snapshots
    )
# ============ ENDPOINT 17: SERIE LONGITUDINAL DE MARCADORES (SOLO CLÍNICO) ============

MAX_MARKER_CODES = 20


def _parse_iso_date(value: Optional[str], field: str) -> Optional[str]:
    """Valida YYYY-MM-DD y lo devuelve como string (measured_on se guarda como string ISO)."""
    if value is None:
        return None
    try:
        return _date.fromisoformat(value).isoformat()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_PARAMETER", "message": f"'{field}' debe tener formato YYYY-MM-DD"}
        )


@router.get("/patients/{patient_id}/markers")
async def get_marker_series(
    patient_id: str,
    marker_codes: str = Query(..., description="Lista separada por comas, máximo 20"),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    only_confirmed: bool = True,
    user: TokenPayload = Depends(get_current_user),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #17: GET /api/v1/patients/{patient_id}/markers
    Serie longitudinal por marcador (§9.5.2). Solo clínico con relación verificada.
    Devuelve, por marcador, los puntos con valor canónico, unidad, rango aplicado,
    estado, subscore y clinical_test_id de origen.
    """
    # Control de acceso: solo clínicos con relación asistencial
    if user.role != "clinician":
        _audit_denied_access(db, "markers", patient_id, user, "role_not_allowed")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Solo un clínico autorizado puede consultar la serie de marcadores"}
        )
    try:
        await require_clinician_access(patient_id, user.clinician_id)
    except HTTPException:
        _audit_denied_access(db, "markers", patient_id, user, "no_clinical_relationship")
        raise

    # Parámetros
    codes = list(dict.fromkeys(c.strip() for c in marker_codes.split(",") if c.strip()))
    if not codes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_PARAMETER", "message": "Debes indicar al menos un marker_code"}
        )
    if len(codes) > MAX_MARKER_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_PARAMETER", "message": f"Máximo {MAX_MARKER_CODES} marker_codes por consulta"}
        )
    d_from = _parse_iso_date(date_from, "from")
    d_to = _parse_iso_date(date_to, "to")

    # Consulta: nunca incluye marcadores invalidados (reemplazados por correcciones)
    query = {
        "patient_id": patient_id,
        "marker_code": {"$in": codes},
        "invalidated_at": None,
    }
    if only_confirmed:
        query["confirmation_level"] = {"$nin": [None, "proposed", "unconfirmed"]}
    if d_from or d_to:
        rng = {}
        if d_from:
            rng["$gte"] = d_from
        if d_to:
            rng["$lte"] = d_to
        query["measured_on"] = rng

    docs = db.clinical_markers.find(query).sort(
        [("measured_on", 1), ("created_at", 1), ("_id", 1)]
    )

    series = {code: {"marker_code": code, "unit": None, "points": []} for code in codes}
    for d in docs:
        s = series[d["marker_code"]]
        if s["unit"] is None:
            s["unit"] = d.get("unit_canonical")
        s["points"].append({
            "measured_on": d.get("measured_on"),
            "value": d.get("value_canonical"),
            "unit": d.get("unit_canonical"),
            "reference": d.get("reference"),
            "status": d.get("status"),
            "subscore": d.get("subscore"),
            "clinical_test_id": d.get("clinical_test_id"),
            "confirmation_level": d.get("confirmation_level"),
            "edited": d.get("edited", False),
        })

    return {
        "patient_id": patient_id,
        "from": d_from,
        "to": d_to,
        "only_confirmed": only_confirmed,
        "series": [series[c] for c in codes],  # mismo orden que se pidió
    }
# ============ ENDPOINT 19: PAYLOAD DEL REPORTE DE LABORATORIO (SOLO CLÍNICO) ============

_SEVERITY_ORDER = {"critical": 0, "high": 1, "info": 2}
_NOT_CONFIRMED = [None, "proposed", "unconfirmed"]


def _json_safe(v):
    """Convierte ObjectId/datetime a tipos JSON y quita _id (para devolver documentos de Mongo)."""
    if isinstance(v, dict):
        return {k: _json_safe(x) for k, x in v.items() if k != "_id"}
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(v, ObjectId):
        return str(v)
    return v


def _months_ago(d, months: int):
    idx = d.year * 12 + (d.month - 1) - months
    y, m = divmod(idx, 12)
    m += 1
    return _date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _delta_vs_previous(cur: dict, prev: Optional[dict]):
    """Δ anterior (§9.3): absoluto y porcentual, con fecha de la medición previa. Sin juicio de valor."""
    if not prev:
        return None
    cv, pv = cur.get("value_canonical"), prev.get("value_canonical")
    if cv is None or pv is None:
        return None
    diff = round(cv - pv, 4)
    return {
        "absolute": diff,
        "percent": round(diff / pv * 100, 2) if pv else None,
        "previous_value": pv,
        "previous_measured_on": prev.get("measured_on"),
        "previous_clinical_test_id": prev.get("clinical_test_id"),
    }


def _result_row(m: dict, prev: Optional[dict], info: dict) -> dict:
    ref = m.get("reference") or {}
    subscore = m.get("subscore")
    blank_reason = None
    if subscore is None:
        blank_reason = "no_reference_range" if (ref.get("low") is None and ref.get("high") is None) else "not_scored"
    return {
        "marker_code": m.get("marker_code"),
        "name": info.get("canonical_name") or info.get("raw_name") or m.get("marker_code"),
        "raw_name": info.get("raw_name"),
        "panel_code": m.get("panel_code"),
        "value": m.get("value_canonical"),
        "unit": m.get("unit_canonical"),
        "censoring": m.get("censoring"),
        "edited": bool(m.get("edited", False)),
        "reference": {
            "low": ref.get("low"), "high": ref.get("high"),
            "unit": ref.get("unit"), "source": ref.get("source"),  # document | catalog
        },
        "status": m.get("status"),
        "delta": _delta_vs_previous(m, prev),
        "subscore": subscore,
        "subscore_blank_reason": blank_reason,
        "origin": {"clinical_test_id": m.get("clinical_test_id"), "measured_on": m.get("measured_on")},
        "original": {  # valor y unidad originales + factor aplicado (tooltip de conversión)
            "value_raw": m.get("value_raw"),
            "unit_raw": m.get("unit_raw"),
            "conversion_factor": info.get("conversion_factor"),
        },
    }


@router.get("/patients/{patient_id}/lab-report")
async def get_lab_report(
    patient_id: str,
    clinical_test_id: Optional[str] = None,
    window_months: int = Query(12, ge=1, le=60),
    include_series: bool = False,
    include_snapshot: bool = False,
    user: TokenPayload = Depends(get_current_user),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #19: GET /api/v1/patients/{patient_id}/lab-report  (§9.5.1)
    Payload completo del reporte, resuelto en servidor (el portal no recalcula nada).
      - con clinical_test_id  -> modo "exam": solo los marcadores de ese documento
      - sin clinical_test_id  -> modo "aggregate": último valor de cada marcador dentro de window_months
    include_snapshot=true incluye el desglose de contribuciones por pilar.
    include_series=true incluye series de marcadores y de pilares.
    """
    # --- Control de acceso: solo clínico con relación verificada ---
    if user.role != "clinician":
        _audit_denied_access(db, "lab-report", patient_id, user, "role_not_allowed")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Solo un clínico autorizado puede consultar el reporte"}
        )
    try:
        await require_clinician_access(patient_id, user.clinician_id)
    except HTTPException:
        _audit_denied_access(db, "lab-report", patient_id, user, "no_clinical_relationship")
        raise

    # --- Ventana y modo ---
    today = datetime.utcnow().date()
    window_from = _months_ago(today, window_months).isoformat()
    window_to = today.isoformat()
    mode = "exam" if clinical_test_id else "aggregate"

    if clinical_test_id:
        exam_doc = db.clinical_tests.find_one(
            {"clinical_test_id": clinical_test_id, "patient_id": patient_id, "deleted_at": None}
        )
        if not exam_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Examen no encontrado para este paciente"}
            )

    # --- Marcadores vigentes y confirmados del paciente (orden cronológico) ---
    all_markers = list(
        db.clinical_markers.find({
            "patient_id": patient_id,
            "invalidated_at": None,
            "confirmation_level": {"$nin": _NOT_CONFIRMED},
        }).sort([("measured_on", 1), ("created_at", 1), ("_id", 1)])
    )

    # medición anterior de cada marcador (misma serie, posición previa)
    by_code, prev_of = {}, {}
    for m in all_markers:
        series_list = by_code.setdefault(m["marker_code"], [])
        prev_of[m["_id"]] = series_list[-1] if series_list else None
        series_list.append(m)

    if mode == "exam":
        source = [m for m in all_markers if m.get("clinical_test_id") == clinical_test_id]
    else:
        latest = {}
        for m in all_markers:  # ascendente: el último gana
            if m.get("measured_on") is None or m["measured_on"] >= window_from:
                latest[m["marker_code"]] = m
        source = list(latest.values())

    # --- Exámenes y extracciones involucrados ---
    ct_ids = {m.get("clinical_test_id") for m in source if m.get("clinical_test_id")}
    if clinical_test_id:
        ct_ids.add(clinical_test_id)

    tests = {t["clinical_test_id"]: t for t in db.clinical_tests.find({"clinical_test_id": {"$in": list(ct_ids)}})}
    extractions = {}
    for e in db.clinical_test_extractions.find(
        {"clinical_test_id": {"$in": list(ct_ids)}}
    ).sort([("created_at", -1), ("_id", -1)]):
        cur = extractions.get(e["clinical_test_id"])
        if cur is None or (cur.get("status") == "discarded" and e.get("status") != "discarded"):
            extractions[e["clinical_test_id"]] = e

    # nombre original / factor de conversión por (examen, marcador)
    marker_info = {}
    for ct, e in extractions.items():
        for panel in e.get("panels", []) or []:
            for mk in panel.get("markers", []) or []:
                marker_info[(ct, mk.get("marker_code"))] = {
                    "raw_name": mk.get("raw_name"),
                    "conversion_factor": mk.get("conversion_factor"),
                }

    # --- Sección 1: cabecera ---
    exams = []
    for ct in sorted(ct_ids):
        t, e = tests.get(ct, {}), extractions.get(ct, {})
        doc_meta = e.get("document", {}) or {}
        exams.append({
            "clinical_test_id": ct,
            "title": t.get("title"),
            "test_date": t.get("test_date"),
            "test_type": t.get("test_type"),
            "file_name": (t.get("file") or {}).get("original_name"),
            "issuer": doc_meta.get("issuer"),  # el esquema actual no lo extrae todavía
            "document_type": doc_meta.get("document_type"),
            "description": doc_meta.get("description"),
            "collection_date": doc_meta.get("collection_date"),
            "validation_status": e.get("status"),  # confirmed | clinically_validated | ...
            "review_status": (t.get("review") or {}).get("status"),
            "original_document": {"download_url_endpoint": f"/api/v1/clinical-tests/{ct}/download-url"},
        })
    header = {
        "patient_id": patient_id,
        "mode": mode,
        "window": {"months": window_months, "from": window_from, "to": window_to},
        "exam": next((x for x in exams if x["clinical_test_id"] == clinical_test_id), None) if mode == "exam" else None,
        "exams": exams,
    }

    # --- Secciones 2 y 3: puntaje y banderas (último snapshot; nunca se calcula al vuelo) ---
    snap = db.score_snapshots.find_one({"patient_id": patient_id}, sort=[("computed_at", -1), ("_id", -1)])
    score, flags = None, []
    if snap:
        pillars = {
            name: {k: v for k, v in p.items() if include_snapshot or k != "contributions"}
            for name, p in (snap.get("pillars") or {}).items()
        }
        score = _json_safe({
            "snapshot_id": snap.get("snapshot_id"),
            "computed_at": snap.get("computed_at"),
            "trigger": snap.get("trigger"),
            "scoring_version": snap.get("scoring_version"),
            "catalog_version": snap.get("catalog_version"),
            "window": snap.get("window"),
            "lab_index": snap.get("lab_index"),
            "base_score": snap.get("base_score"),
            "penalty_applied": snap.get("penalty_applied"),
            "pillars": pillars,
        })
        flags = sorted(
            _json_safe(snap.get("flags") or []),
            key=lambda f: (_SEVERITY_ORDER.get(f.get("severity"), 9), f.get("marker_code") or ""),
        )

    # --- Sección 4: tabla de resultados agrupada por panel ---
    try:
        catalog_names = {i["marker_code"]: i["name"] for i in catalog_service.list_catalog(db)}
    except Exception as e:
        print(f"No se pudo leer el catálogo para los nombres canónicos: {e}")
        catalog_names = {}
    panels = {}
    for m in sorted(source, key=lambda x: (x.get("panel_code") or "", x.get("marker_code") or "")):
        info = dict(marker_info.get((m.get("clinical_test_id"), m.get("marker_code")), {}))
        info["canonical_name"] = catalog_names.get(m.get("marker_code"))
        p = panels.setdefault(m.get("panel_code"), {
            "panel_code": m.get("panel_code"), "specimen": m.get("specimen"), "rows": []
        })
        p["rows"].append(_result_row(m, prev_of.get(m["_id"]), info))

    # --- Sección 5: evolución longitudinal (opcional) ---
    longitudinal = None
    if include_series:
        marker_series = []
        for code, pts in by_code.items():
            if len(pts) < 2:
                continue
            marker_series.append({
                "marker_code": code,
                "unit": pts[-1].get("unit_canonical"),
                "reference": _json_safe(pts[-1].get("reference")),
                "points": [{
                    "measured_on": p.get("measured_on"), "value": p.get("value_canonical"),
                    "status": p.get("status"), "clinical_test_id": p.get("clinical_test_id"),
                } for p in pts],
            })
        pillar_points, version_changes, last_version = [], [], None
        for s in db.score_snapshots.find({"patient_id": patient_id}).sort(
            [("computed_at", 1), ("_id", 1)]
        ).limit(200):
            pillar_points.append(_json_safe({
                "computed_at": s.get("computed_at"),
                "trigger": s.get("trigger"),
                "scoring_version": s.get("scoring_version"),
                "lab_index": s.get("lab_index"),
                "pillars": {n: {"score": p.get("score"), "coverage": p.get("coverage")}
                            for n, p in (s.get("pillars") or {}).items()},
            }))
            v = s.get("scoring_version")
            if last_version is not None and v != last_version:
                version_changes.append({"at": _json_safe(s.get("computed_at")), "from": last_version, "to": v})
            last_version = v
        longitudinal = {
            "marker_series": marker_series,
            "pillar_series": pillar_points,
            "scoring_version_changes": version_changes,
        }

    # --- Sección 6: hallazgos de imagen (solo informes de imagen) ---
    imaging_findings = [
        {"clinical_test_id": ct, "findings": _json_safe(extractions[ct].get("imaging"))}
        for ct in sorted(ct_ids)
        if (extractions.get(ct, {}).get("document") or {}).get("document_type") == "imaging_report"
    ]

    # --- Sección 7: trazabilidad ---
    traceability = {
        "extractions": [
            {"clinical_test_id": ct, "extraction_id": e.get("extraction_id"), "status": e.get("status"),
             "extraction_meta": _json_safe(e.get("extraction_meta") or {})}
            for ct, e in extractions.items()
        ],
        "scoring_version": (snap or {}).get("scoring_version"),
        "catalog_version": (snap or {}).get("catalog_version"),
        "edited_markers": [
            {"marker_code": m.get("marker_code"), "clinical_test_id": m.get("clinical_test_id"),
             "confirmation_level": m.get("confirmation_level"), "edited_by": m.get("edited_by")}
            for m in source if m.get("edited")
        ],
        "excluded_markers": _json_safe((snap or {}).get("excluded_markers") or []),
    }

    # --- Sección 8: acciones disponibles (rutas que consume el portal) ---
    actions = {
        "validate": "POST /api/v1/clinical-tests/{clinical_test_id}/extraction/validate",
        "review": "PATCH /api/v1/clinical-tests/{clinical_test_id}/review",
        "export_pdf": f"POST /api/v1/patients/{patient_id}/lab-report/export",
    }

    return {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "header": header,
        "score": score,  # null si aún no hay snapshot (motivo: NO_SCORE_AVAILABLE en el endpoint 18)
        "flags": flags,
        "results": {"panels": list(panels.values())},
        "longitudinal": longitudinal,
        "imaging_findings": imaging_findings,
        "traceability": traceability,
        "actions": actions,
    }
# ============ ENDPOINT 20: EXPORTAR EL REPORTE A PDF (SOLO CLÍNICO) ============
# Requiere reportlab==4.2.5 en requirements.txt

_STATUS_ES = {
    "low": "Bajo", "normal": "Normal", "high": "Alto",
    "critical_low": "Critico bajo", "critical_high": "Critico alto",
    "indeterminate": "Indeterminado",
}
_SEVERITY_ES = {"critical": "CRITICA", "high": "ALTA", "info": "INFO"}
_PDF_LEGEND = "El puntaje es una medida de resumen y no constituye un diagnostico."


class LabReportExportRequest(BaseModel):
    clinical_test_id: Optional[str] = None
    window_months: int = Field(12, ge=1, le=60)
    include_series: bool = True


def _f(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def _build_lab_report_pdf(report: dict, patient_id: str, clinician_id: str) -> bytes:
    """Genera el PDF en servidor a partir del MISMO payload del endpoint 19 (§9.5.4)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    trace = report.get("traceability") or {}
    page_w, _ = landscape(A4)
    footer_line = (
        f"Paciente: {patient_id} | Generado: {report.get('generated_at')} | Clinico: {clinician_id} | "
        f"Catalogo: {trace.get('catalog_version') or 'n/d'} | Formula: {trace.get('scoring_version') or 'n/d'}"
    )

    def footer(canvas, doc):  # pie de CADA página
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.line(36, 34, page_w - 36, 34)
        canvas.drawString(36, 24, footer_line)
        canvas.drawString(36, 14, _PDF_LEGEND)
        canvas.drawRightString(page_w - 36, 14, f"Pagina {doc.page}")
        canvas.restoreState()

    base = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=base["BodyText"], fontSize=8, leading=10)
    h2 = ParagraphStyle("h2k", parent=base["Heading2"], keepWithNext=1)
    h3 = ParagraphStyle("h3k", parent=base["Heading3"], keepWithNext=1)
    title = base["Title"]

    def P(text, style=small):
        return Paragraph(_xml_escape(str(text)), style)

    def table(data, widths, header=True):
        t = Table([[P(c) if not hasattr(c, "wrap") else c for c in row] for row in data],
                  colWidths=widths, repeatRows=1 if header else 0)
        style = [("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        if header:
            style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF4")))
        t.setStyle(TableStyle(style))
        return t

    story = [P("Reporte de laboratorio", title)]
    hdr = report.get("header") or {}
    win = hdr.get("window") or {}
    story.append(P(f"Paciente: {patient_id} | Modo: {hdr.get('mode')} | Ventana: {win.get('months')} meses "
                   f"({win.get('from')} a {win.get('to')})"))
    for ex in hdr.get("exams") or []:
        story.append(P(f"Examen {ex.get('clinical_test_id')}: {ex.get('title') or '-'} | fecha {ex.get('test_date') or '-'} | "
                       f"tipo documento {ex.get('document_type') or '-'} | validacion {ex.get('validation_status') or '-'} | "
                       f"revision clinica {ex.get('review_status') or '-'}"))
    story.append(Spacer(1, 8))

    # --- 2. Puntaje ---
    story.append(P("Puntaje", h2))
    score = report.get("score")
    if score:
        story.append(P(f"Indice de laboratorio: {_f(score.get('lab_index'))} (base {_f(score.get('base_score'))}, "
                       f"penalizacion por banderas {_f(score.get('penalty_applied'))}). "
                       f"Calculado {score.get('computed_at')} - motivo: {score.get('trigger')}."))
        rows = [["Pilar", "Score", "Cobertura", "Confianza", "Estado"]]
        for name, p in (score.get("pillars") or {}).items():
            rows.append([name, _f(p.get("score")), _f(p.get("coverage")), _f(p.get("confidence")), _f(p.get("status"))])
        story += [Spacer(1, 4), table(rows, [150, 80, 80, 100, 100])]
        for name, p in (score.get("pillars") or {}).items():
            contribs = p.get("contributions") or []
            if contribs:
                story += [P(f"Marcadores del pilar {name}", h3)]
                crow = [["Marcador", "Valor", "Unidad", "Subscore", "Peso"]]
                for c in contribs:
                    crow.append([c.get("name") or c.get("marker_code"), _f(c.get("value")), _f(c.get("unit")),
                                 _f(c.get("subscore")), _f(c.get("weight"))])
                story.append(table(crow, [260, 80, 80, 80, 80]))
    else:
        story.append(P("Sin puntaje calculado: no hay examenes confirmados o la cobertura es insuficiente."))

    # --- 3. Banderas ---
    story.append(P("Banderas activas", h2))
    flags = report.get("flags") or []
    if flags:
        rows = [["Severidad", "Marcador", "Valor", "Detalle"]]
        for fl in flags:
            rows.append([_SEVERITY_ES.get(fl.get("severity"), fl.get("severity")), fl.get("marker_code"),
                         f"{_f(fl.get('value'))} {fl.get('unit') or ''}".strip(), fl.get("message")])
        story.append(table(rows, [70, 130, 90, 480]))
    else:
        story.append(P("Sin banderas activas."))

    # --- 4. Tabla de resultados ---
    story.append(P("Resultados", h2))
    panels = (report.get("results") or {}).get("panels") or []
    if not panels:
        story.append(P("Sin marcadores confirmados en el periodo."))
    for panel in panels:
        story.append(P(f"Panel: {panel.get('panel_code')} ({panel.get('specimen') or '-'})", h3))
        rows = [["Marcador", "Valor", "Unidad", "Rango de referencia", "Estado", "Variacion vs anterior",
                 "Subscore", "Origen"]]
        for r in panel.get("rows") or []:
            ref = r.get("reference") or {}
            ref_txt = f"{_f(ref.get('low'))} - {_f(ref.get('high'))} {ref.get('unit') or ''} ({ref.get('source') or 'n/d'})"
            d = r.get("delta")
            delta_txt = "-" if not d else (
                f"{d['absolute']:+g} ({_f(d.get('percent'))}%) vs {d.get('previous_measured_on')}")
            value_txt = _f(r.get("value")) + (" (editado)" if r.get("edited") else "")
            if r.get("censoring"):
                value_txt = f"{r['censoring']} {value_txt}"
            sub = _f(r.get("subscore")) if r.get("subscore") is not None else f"- ({r.get('subscore_blank_reason')})"
            org = r.get("origin") or {}
            name_txt = r.get("name") or r.get("marker_code")
            if r.get("raw_name") and r["raw_name"] != name_txt:
                name_txt = f"{name_txt} (documento: {r['raw_name']})"
            rows.append([name_txt, value_txt, _f(r.get("unit")), ref_txt,
                         _STATUS_ES.get(r.get("status"), _f(r.get("status"))), delta_txt, sub,
                         f"{org.get('clinical_test_id')} ({org.get('measured_on')})"])
        story.append(table(rows, [140, 70, 55, 120, 70, 120, 70, 125]))

    # --- 5. Evolución longitudinal (resumen) ---
    lon = report.get("longitudinal")
    if lon and lon.get("marker_series"):
        story.append(P("Evolucion de marcadores con 2 o mas mediciones", h2))
        rows = [["Marcador", "Mediciones", "Primera", "Ultima", "Variacion absoluta"]]
        for s in lon["marker_series"]:
            pts = s.get("points") or []
            first, last = pts[0], pts[-1]
            diff = (last["value"] - first["value"]) if first.get("value") is not None and last.get("value") is not None else None
            rows.append([s.get("marker_code"), len(pts), f"{_f(first.get('value'))} ({first.get('measured_on')})",
                         f"{_f(last.get('value'))} ({last.get('measured_on')})", "-" if diff is None else f"{diff:+g}"])
        story.append(table(rows, [180, 80, 170, 170, 120]))
        changes = lon.get("scoring_version_changes") or []
        if changes:
            story.append(P("Cambios de version de formula: " + "; ".join(
                f"{c['at']}: {c['from']} -> {c['to']}" for c in changes)))

    # --- 6. Imagen ---
    for img in report.get("imaging_findings") or []:
        story.append(P(f"Hallazgos de imagen ({img.get('clinical_test_id')})", h2))
        story.append(P(json.dumps(img.get("findings"), ensure_ascii=False)))

    # --- 7. Trazabilidad ---
    story.append(P("Trazabilidad", h2))
    story.append(P(f"Version del catalogo: {trace.get('catalog_version') or 'n/d'} | "
                   f"Version de formula: {trace.get('scoring_version') or 'n/d'}"))
    for e in trace.get("extractions") or []:
        story.append(P(f"Extraccion {e.get('extraction_id')} (examen {e.get('clinical_test_id')}, "
                       f"estado {e.get('status')}): {json.dumps(e.get('extraction_meta'), ensure_ascii=False)}"))
    edited = trace.get("edited_markers") or []
    story.append(P("Valores editados: " + (", ".join(
        f"{m['marker_code']} (nivel {m.get('confirmation_level')})" for m in edited) if edited else "ninguno")))
    excluded = trace.get("excluded_markers") or []
    story.append(P("Marcadores excluidos del puntaje: " + (", ".join(
        f"{m.get('marker_code') or m.get('raw_name')}: {m.get('reason')}" for m in excluded) if excluded else "ninguno")))

    buf = io.BytesIO()
    SimpleDocTemplate(
        buf, pagesize=landscape(A4), leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=48,
        title=f"Reporte de laboratorio {patient_id}", author="WellQ", pageCompression=0,
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def _store_export_pdf(object_key: str, pdf: bytes) -> str:
    """Guarda el PDF en el prefijo privado de GCS (o en ./exports en modo desarrollo).
    Devuelve el modo de almacenamiento: "gcs" | "local"."""
    return storage_service.upload_bytes(object_key=object_key, data=pdf, content_type="application/pdf")


def _export_response(rec: dict, replayed: bool) -> dict:
    url, expires_at = None, None
    try:
        info = storage_service.generate_download_url(
            object_key=rec["object_key"], expiration_minutes=settings.DOWNLOAD_URL_EXPIRATION_MINUTES,
        )
        url, expires_at = info.get("url"), info.get("expires_at")
    except Exception as e:
        print(f"No se pudo firmar la URL del export {rec.get('export_id')}: {e}")
    return {
        "export_id": rec["export_id"],
        "patient_id": rec["patient_id"],
        "status": "ready",
        "file_name": rec["file_name"],
        "download_url": url,
        "expires_at": expires_at,
        "size_bytes": rec["size_bytes"],
        "sha256": rec["sha256"],
        "storage": rec["storage"],
        "replayed": replayed,
        "generated_at": _json_safe(rec["created_at"]),
    }


@router.post("/patients/{patient_id}/lab-report/export")
async def export_lab_report(
    patient_id: str,
    body: Optional[LabReportExportRequest] = None,
    idempotency_key: str = Header(...),
    user: TokenPayload = Depends(get_current_user),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #20: POST /api/v1/patients/{patient_id}/lab-report/export  (§9.5.4)
    Genera el PDF en servidor con el mismo payload del endpoint 19, lo guarda en un prefijo privado
    y devuelve una URL firmada de corta duración. Idempotente por (clínico, paciente, Idempotency-Key).
    Cada exportación nueva queda registrada en audit_events.
    """
    body = body or LabReportExportRequest()
    params = body.dict()

    # Mismo payload que consume el portal (incluye el control de acceso y su auditoría de denegados)
    report = await get_lab_report(
        patient_id=patient_id,
        clinical_test_id=body.clinical_test_id,
        window_months=body.window_months,
        include_series=body.include_series,
        include_snapshot=True,
        user=user,
        db=db,
    )
    clinician_id = user.clinician_id

    # Idempotencia
    existing = db.lab_report_exports.find_one(
        {"patient_id": patient_id, "clinician_id": clinician_id, "idempotency_key": idempotency_key}
    )
    if existing:
        if existing.get("params") != params:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "IDEMPOTENCY_CONFLICT",
                        "message": "El Idempotency-Key ya se usó con parámetros distintos"}
            )
        return _export_response(existing, replayed=True)

    # Generar PDF
    try:
        pdf = _build_lab_report_pdf(report, patient_id, clinician_id)
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "PDF_ENGINE_UNAVAILABLE",
                    "message": "Falta 'reportlab' en el servidor: agrégalo a requirements.txt y reconstruye la imagen"}
        )

    export_id = f"lrx_{uuid.uuid4().hex[:12]}"
    object_key = f"private/lab-reports/{patient_id}/{export_id}.pdf"
    try:
        storage_mode = _store_export_pdf(object_key, pdf)
    except Exception as e:
        print(f"Error guardando el PDF {export_id} en el almacenamiento: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "STORAGE_ERROR", "message": "No se pudo guardar el PDF en el almacenamiento"}
        )

    now = datetime.utcnow()
    payload_for_hash = {k: v for k, v in report.items() if k != "generated_at"}
    trace = report.get("traceability") or {}
    rec = {
        "export_id": export_id,
        "patient_id": patient_id,
        "clinician_id": clinician_id,
        "idempotency_key": idempotency_key,
        "params": params,
        "object_key": object_key,
        "storage": storage_mode,
        "file_name": f"lab-report_{patient_id}_{now.strftime('%Y%m%d')}.pdf",
        "size_bytes": len(pdf),
        "sha256": hashlib.sha256(pdf).hexdigest(),
        "payload_sha256": hashlib.sha256(
            json.dumps(payload_for_hash, sort_keys=True, default=str).encode("utf-8")).hexdigest(),
        "catalog_version": trace.get("catalog_version"),
        "scoring_version": trace.get("scoring_version"),
        "created_at": now,
    }
    db.lab_report_exports.insert_one(dict(rec))

    # Auditoría de la exportación (sujeto, momento, recurso y resultado)
    try:
        db.audit_events.insert_one({
            "event": "lab_report_export",
            "resource": "lab-report",
            "patient_id": patient_id,
            "actor_role": user.role,
            "actor_id": clinician_id,
            "export_id": export_id,
            "object_key": object_key,
            "sha256": rec["sha256"],
            "result": "success",
            "occurred_at": now,
        })
    except Exception as e:
        print(f"No se pudo registrar la auditoría de exportación {export_id}: {e}")

    return _export_response(rec, replayed=False)