import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pymongo.database import Database
from pydantic import BaseModel

from app.database import get_database
from app.dependencies.auth import get_current_patient, get_current_clinician, get_current_user, TokenPayload
from app.dependencies.access import require_clinician_access
from app.services.catalog import catalog_service
from app.services.extractor import extraction_engine
from app.services.scoring import scoring_engine
from app.models.extraction import (
    ExtractionStatus, DocumentType, MarkerStatus, ConfirmationLevel,
    ExtractionResponse, PatientConfirmationRequest, ClinicianValidationRequest,
    CatalogItemResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _public_confirmation(conf: Dict[str, Any]) -> Dict[str, Any]:
    """Bloque de confirmación sin datos internos (la clave de idempotencia no se expone)."""
    return {k: v for k, v in (conf or {}).items() if k != "idempotency_key"}


def _response_from_ext_doc(ext: Dict[str, Any]) -> ExtractionResponse:
    return ExtractionResponse(
        schema_version=ext.get("schema_version", "1.0"),
        clinical_test_id=ext["clinical_test_id"],
        extraction_id=ext["extraction_id"],
        status=ExtractionStatus(ext["status"]),
        document=ext["document"],
        panels=ext["panels"],
        flags=ext.get("flags", []),
        extraction_meta=ext.get("extraction_meta", {}),
        confirmation=_public_confirmation(ext.get("confirmation", {})),
    )


def _audit_event(db, event: str, patient_id: str, clinical_test_id: str, extraction_id: str,
                 actor_role: str, actor_id: str, **detail) -> None:
    """Evento de auditoría inmutable (§7.3, §12.8): sujeto, momento, recurso y resultado.
    Nunca debe romper la petición."""
    try:
        db.audit_events.insert_one({
            "event": event,
            "resource": "extraction",
            "patient_id": patient_id,
            "clinical_test_id": clinical_test_id,
            "extraction_id": extraction_id,
            "actor_role": actor_role,
            "actor_id": actor_id,
            "result": "success",
            "occurred_at": datetime.utcnow(),
            **detail,
        })
    except Exception as e:
        logger.warning(f"No se pudo registrar el evento de auditoría '{event}': {e}")

# ============ ENDPOINT 16: GET MARKER CATALOG ============

@router.get(
    "/marker-catalog",
    response_model=List[CatalogItemResponse],
    summary="Obtener catálogo canónico de marcadores",
)
async def get_marker_catalog(
    user: TokenPayload = Depends(get_current_user),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #16: GET /api/v1/marker-catalog
    Catálogo de marcadores soportados, unidades canónicas y rangos.
    """
    items = catalog_service.list_catalog(db)
    result = []
    for item in items:
        result.append(
            CatalogItemResponse(
                marker_code=item["marker_code"],
                name=item["name"],
                panel_code=item["panel_code"],
                specimen=item["specimen"],
                canonical_unit=item["canonical_unit"],
                supported_units=item.get("supported_units", [item["canonical_unit"]]),
                pillars=item.get("pillars", []),
                typical_range=item.get("default_reference", {}),
            )
        )
    return result

# ============ ENDPOINT 12: GET EXTRACTION ============

@router.get(
    "/clinical-tests/{clinical_test_id}/extraction",
    response_model=ExtractionResponse,
    summary="Leer extracción de un examen",
)
async def get_extraction(
    clinical_test_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #12: GET /api/v1/clinical-tests/{clinical_test_id}/extraction
    Devuelve la extracción vigente del examen.
    """
    doc = db.clinical_tests.find_one({"clinical_test_id": clinical_test_id, "deleted_at": None})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Examen médico no encontrado"}
        )

    # Control de acceso
    if user.role == "patient":
        if doc["patient_id"] != user.patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "No tienes acceso a este examen"}
            )
    elif user.role == "clinician":
        await require_clinician_access(doc["patient_id"], user.clinician_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Rol no autorizado"}
        )

    # §7.4.1: GET nunca lanza el extractor; 409 EXTRACTION_NOT_READY si está en cola o procesando
    extraction_info = doc.get("extraction")
    if not extraction_info or not extraction_info.get("extraction_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EXTRACTION_NOT_READY", "message": "La extracción aún no está lista (en cola o procesando)"}
        )

    extraction_id = extraction_info["extraction_id"]
    ext_doc = db.clinical_test_extractions.find_one({
        "extraction_id": extraction_id,
        "superseded_at": None,
    })

    if not ext_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Extracción no encontrada"}
        )

    if ext_doc["status"] in (ExtractionStatus.QUEUED.value, ExtractionStatus.EXTRACTING.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EXTRACTION_NOT_READY", "message": "La extracción aún no está lista (en cola o procesando)"}
        )

    # El clínico ve solo extracciones en estado confirmed o clinically_validated
    if user.role == "clinician" and ext_doc["status"] not in (
        ExtractionStatus.CONFIRMED.value, ExtractionStatus.CLINICALLY_VALIDATED.value,
        ExtractionStatus.NOT_APPLICABLE.value,  # §3.3.2: visible para paciente y clínico
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EXTRACTION_NOT_READY",
                    "message": "La extracción aún no ha sido confirmada por el paciente"}
        )

    return ExtractionResponse(
        schema_version=ext_doc.get("schema_version", "1.0"),
        clinical_test_id=ext_doc["clinical_test_id"],
        extraction_id=ext_doc["extraction_id"],
        status=ExtractionStatus(ext_doc["status"]),
        document=ext_doc["document"],
        panels=ext_doc["panels"],
        flags=ext_doc.get("flags", []),
        extraction_meta=ext_doc.get("extraction_meta", {}),
        confirmation=ext_doc.get("confirmation", {}),
    )

# ============ ENDPOINT 13: CONFIRM OR CORRECT (PATIENT) ============

@router.patch(
    "/clinical-tests/{clinical_test_id}/extraction",
    response_model=ExtractionResponse,
    summary="Confirmar o corregir extracción (Paciente)",
)
async def confirm_extraction(
    clinical_test_id: str,
    request: PatientConfirmationRequest,
    idempotency_key: str = Header(...),
    current_patient: str = Depends(get_current_patient),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #13: PATCH /api/v1/clinical-tests/{clinical_test_id}/extraction
    El paciente confirma, edita o descarta los valores propuestos.
    """
    doc = db.clinical_tests.find_one({"clinical_test_id": clinical_test_id, "deleted_at": None})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Examen médico no encontrado"}
        )

    if doc["patient_id"] != current_patient:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "No tienes acceso a este examen"}
        )

    ext_info = doc.get("extraction", {})
    current_extraction_id = ext_info.get("extraction_id")

    # Validar que coincida la extraction_id vigente (control de concurrencia)
    if not current_extraction_id or current_extraction_id != request.extraction_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EXTRACTION_SUPERSEDED", "message": "La extracción enviada no coincide con la versión vigente"}
        )

    ext_doc = db.clinical_test_extractions.find_one({"extraction_id": request.extraction_id})
    if not ext_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Extracción no encontrada"}
        )

    # Idempotencia: el reintento con la misma Idempotency-Key devuelve el resultado ya guardado
    stored_conf = ext_doc.get("confirmation") or {}
    if stored_conf.get("idempotency_key") == idempotency_key and ext_doc["status"] in (
        ExtractionStatus.CONFIRMED.value, ExtractionStatus.DISCARDED.value,
        ExtractionStatus.CLINICALLY_VALIDATED.value,
    ):
        return _response_from_ext_doc(ext_doc)

    # §7.4.2: solo se permite desde awaiting_confirmation
    if ext_doc["status"] != ExtractionStatus.AWAITING_CONFIRMATION.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_EXTRACTION_STATE",
                    "message": f"Solo se puede confirmar o descartar desde 'awaiting_confirmation'. Estado actual: {ext_doc['status']}"}
        )

    now = datetime.utcnow()

    # Si la acción es descartar
    if request.action == "discard":
        db.clinical_test_extractions.update_one(
            {"_id": ext_doc["_id"]},
            {
                "$set": {
                    "status": ExtractionStatus.DISCARDED.value,
                    "confirmation.status": "discarded",
                    "confirmation.confirmed_by": current_patient,
                    "confirmation.confirmed_at": now,
                    "confirmation.idempotency_key": idempotency_key,
                    "updated_at": now,
                }
            }
        )
        db.clinical_tests.update_one(
            {"clinical_test_id": clinical_test_id},
            {"$set": {"extraction.status": ExtractionStatus.DISCARDED.value, "updated_at": now}}
        )
        ext_doc["status"] = ExtractionStatus.DISCARDED.value
        _audit_event(db, "extraction_discarded", doc["patient_id"], clinical_test_id,
                     request.extraction_id, "patient", current_patient)
        return ExtractionResponse(
            schema_version=ext_doc.get("schema_version", "1.0"),
            clinical_test_id=ext_doc["clinical_test_id"],
            extraction_id=ext_doc["extraction_id"],
            status=ExtractionStatus.DISCARDED,
            document=ext_doc["document"],
            panels=ext_doc["panels"],
            flags=ext_doc.get("flags", []),
            extraction_meta=ext_doc.get("extraction_meta", {}),
            confirmation={"status": "discarded", "confirmed_at": now.isoformat()},
        )

    # Aplicar ediciones de metadatos si vienen
    if request.document_edits:
        if request.document_edits.collection_date:
            ext_doc["document"]["collection_date"] = request.document_edits.collection_date
        if request.document_edits.document_type:
            ext_doc["document"]["document_type"] = request.document_edits.document_type.value

    # Aplicar ediciones de marcadores
    panels = ext_doc.get("panels", [])
    if not panels:
        panels = [{"panel_code": "general", "panel_name_raw": "GENERAL", "specimen": "blood", "markers": []}]

    active_markers_map = {m["marker_code"]: m for m in panels[0].get("markers", [])}
    edit_count = 0
    applied_edits = []

    if request.marker_edits:
        for edit in request.marker_edits:
            m_code = edit.marker_code
            if edit.op == "remove":
                if m_code in active_markers_map:
                    del active_markers_map[m_code]
                    edit_count += 1
                    applied_edits.append({"op": "remove", "marker_code": m_code})
            elif edit.op in ["update", "add"]:
                if not edit.value_raw or not edit.unit_raw:
                    continue

                # Validación determinista contra el catálogo canónico
                norm = catalog_service.validate_and_convert(m_code, edit.value_raw, edit.unit_raw, db)
                if not norm["valid"]:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"code": norm["error_code"], "message": norm["message"]}
                    )

                ref_dict = edit.reference.dict() if edit.reference else norm["reference"]
                marker_data = {
                    "marker_code": m_code,
                    "loinc": None,
                    "raw_name": norm["raw_name"],
                    "mapping_status": "mapped",
                    "value_type": "numeric",
                    "value_raw": edit.value_raw,
                    "unit_raw": edit.unit_raw,
                    "value_canonical": norm["value_canonical"],
                    "unit_canonical": norm["unit_canonical"],
                    "conversion_factor": norm["conversion_factor"],
                    "censoring": norm.get("censoring"),
                    "value_text": None,
                    "reference": ref_dict,
                    "status": norm["status"],
                    "confidence": {"value": 1.0, "unit": 1.0, "reference": 1.0, "name": 1.0},
                    "validation": {"passed": True, "errors": []},
                    "provenance": {"source": "patient_confirmed"},
                    "edited": True,
                    "edited_by": "patient",
                    "edited_by_id": current_patient,
                    "edited_at": now,
                    "original_value_canonical": active_markers_map.get(m_code, {}).get("value_canonical"),
                }
                active_markers_map[m_code] = marker_data
                edit_count += 1
                applied_edits.append({"op": edit.op, "marker_code": m_code})

    # Actualizar paneles con la lista final de marcadores
    final_markers = list(active_markers_map.values())
    panels[0]["markers"] = final_markers

    # Persistir en clinical_test_extractions como CONFIRMED
    db.clinical_test_extractions.update_one(
        {"_id": ext_doc["_id"]},
        {
            "$set": {
                "status": ExtractionStatus.CONFIRMED.value,
                "document": ext_doc["document"],
                "panels": panels,
                # §7.3: la propuesta (`proposal`) no se toca nunca; aquí queda el resultado de la edición
                "confirmed": {
                    "document": ext_doc["document"],
                    "panels": panels,
                    "confirmed_by": current_patient,
                    "confirmed_at": now,
                },
                "confirmation": {
                    "status": "confirmed",
                    "confirmed_by": current_patient,
                    "confirmed_at": now,
                    "validated_by": None,
                    "validated_at": None,
                    "edit_count": edit_count,
                    "edits_applied": applied_edits,
                    "idempotency_key": idempotency_key,
                },
                "updated_at": now,
            }
        }
    )

    # Desnormalizar e insertar cada marcador en la colección `clinical_markers`
    measured_date = ext_doc["document"].get("collection_date") or doc.get("test_date") or now.strftime("%Y-%m-%d")
    
    # Invalidar marcadores previos si existieran
    db.clinical_markers.update_many(
        {"clinical_test_id": clinical_test_id},
        {"$set": {"invalidated_at": now}}
    )

    markers_to_insert = []
    for m in final_markers:
        if (m.get("validation") or {}).get("passed") is False:
            continue  # §5.5.2: no se convierte ni se puntúa; queda visible en la extracción con su bandera
        val_canon = m.get("value_canonical")
        subscore = None
        if val_canon is not None:
            subscore, _ = scoring_engine.calculate_subscore(
                marker_code=m["marker_code"],
                value=float(val_canon),
                reference=m.get("reference")
            )

        markers_to_insert.append({
            "patient_id": current_patient,
            "marker_code": m["marker_code"],
            "clinical_test_id": clinical_test_id,
            "extraction_id": request.extraction_id,
            "panel_code": panels[0]["panel_code"],
            "specimen": panels[0]["specimen"],
            "measured_on": measured_date,
            "value_canonical": m["value_canonical"],
            "unit_canonical": m["unit_canonical"],
            "value_raw": m["value_raw"],
            "unit_raw": m["unit_raw"],
            "censoring": m.get("censoring"),
            "reference": m.get("reference"),
            "status": m.get("status", "normal"),
            "subscore": subscore,
            "scoring_version": scoring_engine.scoring_version if subscore is not None else None,
            "catalog_version": "cat-2026.08",
            "confirmation_level": ConfirmationLevel.PATIENT.value,
            "edited": m.get("edited", False),
            "edited_by": m.get("edited_by"),
            "edited_at": m.get("edited_at"),
            "original_value_canonical": m.get("original_value_canonical"),
            "provenance": "llm_extraction" if not m.get("edited") else "patient_edited",
            "created_at": now,
            "updated_at": now,
            "invalidated_at": None,
        })

    if markers_to_insert:
        db.clinical_markers.insert_many(markers_to_insert)

    # Actualizar clinical_tests
    db.clinical_tests.update_one(
        {"clinical_test_id": clinical_test_id},
        {
            "$set": {
                "extraction.status": ExtractionStatus.CONFIRMED.value,
                "extraction.confirmed_at": now,
                "extraction.confirmed_by": current_patient,
                "extraction.marker_count": len(final_markers),
                "extraction.edit_count": edit_count,
                "updated_at": now,
            }
        }
    )

    logger.info(f"✅ Extracción {request.extraction_id} confirmada por paciente {current_patient}. {len(markers_to_insert)} marcadores persistidos en clinical_markers.")

    # Auditoría: una confirmación y un evento por cada adición, corrección y eliminación (§7.3)
    _audit_event(db, "extraction_confirmed", doc["patient_id"], clinical_test_id,
                 request.extraction_id, "patient", current_patient, edit_count=edit_count)
    for ae in applied_edits:
        _audit_event(db, f"marker_{ae['op']}", doc["patient_id"], clinical_test_id,
                     request.extraction_id, "patient", current_patient, marker_code=ae["marker_code"])

    # Disparar cálculo de score_snapshot (§8.8)
    score_snapshot_id = None
    try:
        excluded_info = [
            {"marker_code": me.marker_code, "reason": me.reason or "removed_by_patient"}
            for me in (request.marker_edits or []) if me.op == "remove"
        ]
        snapshot = scoring_engine.compute_patient_score(
            patient_id=current_patient,
            db=db,
            trigger="extraction_confirmed",
            excluded_markers_info=excluded_info,
        )
        if snapshot:
            score_snapshot_id = snapshot.get("snapshot_id")
            db.clinical_tests.update_one(
                {"clinical_test_id": clinical_test_id},
                {"$set": {"extraction.score_snapshot_id": score_snapshot_id}}
            )
            db.clinical_test_extractions.update_one(
                {"_id": ext_doc["_id"]},
                {"$set": {"confirmation.score_snapshot_id": score_snapshot_id}}
            )
    except Exception as e:
        logger.warning(f"Aviso al calcular snapshot tras confirmación: {e}")

    return ExtractionResponse(
        schema_version="1.0",
        clinical_test_id=clinical_test_id,
        extraction_id=request.extraction_id,
        status=ExtractionStatus.CONFIRMED,
        document=ext_doc["document"],
        panels=panels,
        flags=ext_doc.get("flags", []),
        extraction_meta=ext_doc.get("extraction_meta", {}),
        confirmation={
            "status": "confirmed",
            "confirmed_by": current_patient,
            "confirmed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "edit_count": edit_count,
            "edits_applied": applied_edits,
            "score_snapshot_id": score_snapshot_id,
        },
    )

# ============ ENDPOINT 14: REPROCESS EXTRACTION ============

MAX_REPROCESSES_PER_EXAM = 5  # §7.4.3 (propuesto: 5 reprocesamientos por examen)
_REPROCESSABLE_STATES = (
    ExtractionStatus.EXTRACTION_FAILED.value,
    ExtractionStatus.UNREADABLE.value,
    ExtractionStatus.DISCARDED.value,
)


class ReprocessRequest(BaseModel):
    # Confirmación explícita requerida para reprocesar un examen ya confirmado (§7.4.3)
    confirm_reprocess_confirmed: bool = False


@router.post(
    "/clinical-tests/{clinical_test_id}/extraction/reprocess",
    response_model=ExtractionResponse,
    summary="Reprocesar extracción del documento",
)
async def reprocess_extraction(
    clinical_test_id: str,
    body: Optional[ReprocessRequest] = None,
    idempotency_key: str = Header(...),
    current_patient: str = Depends(get_current_patient),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #14: POST /api/v1/clinical-tests/{clinical_test_id}/extraction/reprocess
    Vuelve a ejecutar la extracción del mismo documento con la versión vigente de prompt y catálogo.
    Permitido desde extraction_failed, unreadable y discarded y, con confirmación explícita
    (confirm_reprocess_confirmed=true), desde confirmed. Límite: 5 reprocesamientos por examen.
    """
    body = body or ReprocessRequest()
    doc = db.clinical_tests.find_one({"clinical_test_id": clinical_test_id, "deleted_at": None})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Examen médico no encontrado"}
        )

    if doc["patient_id"] != current_patient:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "No tienes acceso a este examen"}
        )

    ext_info = doc.get("extraction") or {}
    old_ext_id = ext_info.get("extraction_id")
    old_ext = db.clinical_test_extractions.find_one({"extraction_id": old_ext_id}) if old_ext_id else None

    # Idempotencia: el mismo Idempotency-Key devuelve la extracción ya generada
    if old_ext and ext_info.get("reprocess_idempotency_key") == idempotency_key:
        return _response_from_ext_doc(old_ext)

    current_status = old_ext["status"] if old_ext else None
    if current_status == ExtractionStatus.CONFIRMED.value:
        if not body.confirm_reprocess_confirmed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "CONFIRMATION_REQUIRED",
                        "message": "El examen ya está confirmado: reprocesarlo requiere confirmación explícita "
                                   "(confirm_reprocess_confirmed=true) y descarta la confirmación actual"}
            )
    elif current_status not in _REPROCESSABLE_STATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "REPROCESS_NOT_ALLOWED",
                    "message": f"No se puede reprocesar desde el estado '{current_status}'. Permitido desde: "
                               f"extraction_failed, unreadable, discarded y, con confirmación explícita, confirmed"}
        )

    reprocess_count = int(ext_info.get("reprocess_count", 0))
    if reprocess_count >= MAX_REPROCESSES_PER_EXAM:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "RATE_LIMITED",
                    "message": f"Límite de {MAX_REPROCESSES_PER_EXAM} reprocesamientos por examen alcanzado"}
        )

    now = datetime.utcnow()

    # Archivar extracción vigente
    if old_ext_id:
        db.clinical_test_extractions.update_one(
            {"extraction_id": old_ext_id},
            {"$set": {"superseded_at": now, "updated_at": now}}
        )

    # Invalidar marcadores previos (el puntaje derivado deja de contar con ellos)
    db.clinical_markers.update_many(
        {"clinical_test_id": clinical_test_id},
        {"$set": {"invalidated_at": now}}
    )

    # Ejecutar nueva extracción
    new_ext_doc = extraction_engine.run_extraction_pipeline(clinical_test_id, db)

    db.clinical_tests.update_one(
        {"clinical_test_id": clinical_test_id},
        {"$set": {
            "extraction.reprocess_count": reprocess_count + 1,
            "extraction.reprocess_idempotency_key": idempotency_key,
            "updated_at": now,
        }}
    )
    _audit_event(db, "extraction_reprocessed", doc["patient_id"], clinical_test_id,
                 new_ext_doc["extraction_id"], "patient", current_patient,
                 previous_status=current_status, previous_extraction_id=old_ext_id,
                 reprocess_number=reprocess_count + 1)

    return _response_from_ext_doc(new_ext_doc)

# ============ ENDPOINT 15: CLINICIAN VALIDATION ============

@router.post(
    "/clinical-tests/{clinical_test_id}/extraction/validate",
    response_model=ExtractionResponse,
    summary="Validación clínica de la extracción (Clínico)",
)
async def validate_extraction_clinician(
    clinical_test_id: str,
    request: ClinicianValidationRequest,
    current_clinician: str = Depends(get_current_clinician),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #15: POST /api/v1/clinical-tests/{clinical_test_id}/extraction/validate
    Validación clínica de los valores confirmados por el paciente.

    - validation_status: "validated" | "rejected" (otro valor => 422).
    - Las correcciones se validan TODAS antes de escribir nada: si alguna es inválida
      (marcador que no está en el examen, duplicado, valor o unidad no válidos) responde 422
      con el detalle por marcador y no se modifica nada.
    - La corrección actualiza el marcador vigente y la extracción, conserva el valor original,
      registra quién lo editó y deja un evento de auditoría.
    """
    doc = db.clinical_tests.find_one({"clinical_test_id": clinical_test_id, "deleted_at": None})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Examen médico no encontrado"}
        )

    await require_clinician_access(doc["patient_id"], current_clinician)

    if request.validation_status not in ("validated", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_VALIDATION_STATUS",
                    "message": "validation_status debe ser 'validated' o 'rejected'"}
        )

    ext_info = doc.get("extraction", {})
    if ext_info.get("status") != ExtractionStatus.CONFIRMED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "NOT_CONFIRMED", "message": f"Solo se pueden validar exámenes en estado 'confirmed'. Estado actual: {ext_info.get('status')}"}
        )

    extraction_id = ext_info.get("extraction_id")
    ext_doc = db.clinical_test_extractions.find_one({"extraction_id": extraction_id})
    if not ext_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Documento de extracción no encontrado"}
        )

    now = datetime.utcnow()
    applied_corrections: List[Dict[str, Any]] = []

    if request.validation_status == "rejected":
        # Rechazar extracción: invalida los marcadores en cascada (§11.5)
        db.clinical_markers.update_many(
            {"clinical_test_id": clinical_test_id},
            {"$set": {"invalidated_at": now}}
        )
        db.clinical_test_extractions.update_one(
            {"_id": ext_doc["_id"]},
            {
                "$set": {
                    "status": ExtractionStatus.REJECTED.value,
                    "confirmation.validated_by": current_clinician,
                    "confirmation.validated_at": now,
                    "confirmation.validation_note": request.clinical_note,
                    "updated_at": now,
                }
            }
        )
        db.clinical_tests.update_one(
            {"clinical_test_id": clinical_test_id},
            {"$set": {"extraction.status": ExtractionStatus.REJECTED.value, "updated_at": now}}
        )
        ext_doc["status"] = ExtractionStatus.REJECTED.value

        # Recalcular puntaje sin los marcadores rechazados
        try:
            scoring_engine.compute_patient_score(
                patient_id=doc["patient_id"],
                db=db,
                trigger="recompute"
            )
        except Exception as e:
            logger.warning(f"Aviso al recalcular tras rechazo clínico: {e}")
    else:
        panels = ext_doc.get("panels", [])

        # 1) Validar TODAS las correcciones antes de escribir nada (atómico)
        prepared = []
        if request.marker_corrections:
            current_markers = {
                m["marker_code"]: m
                for m in db.clinical_markers.find(
                    {"clinical_test_id": clinical_test_id, "invalidated_at": None}
                )
            }
            errors: List[Dict[str, Any]] = []
            seen = set()
            for corr in request.marker_corrections:
                code = corr.marker_code
                if code in seen:
                    errors.append({"marker_code": code, "code": "DUPLICATE_CORRECTION",
                                   "message": "El marcador aparece más de una vez en las correcciones"})
                    continue
                seen.add(code)

                existing = current_markers.get(code)
                if not existing:
                    errors.append({"marker_code": code, "code": "MARKER_NOT_IN_EXAM",
                                   "message": "El marcador no existe en este examen; solo se pueden corregir marcadores vigentes"})
                    continue

                norm = catalog_service.validate_and_convert(code, corr.value_raw, corr.unit_raw, db)
                if not norm["valid"]:
                    errors.append({"marker_code": code, "code": norm.get("error_code") or "INVALID_VALUE",
                                   "message": norm.get("message") or "Valor o unidad no válidos"})
                    continue
                prepared.append((corr, existing, norm))

            if errors:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "INVALID_MARKER_CORRECTIONS",
                        "message": "Una o más correcciones no son válidas; no se aplicó ningún cambio",
                        "errors": errors,
                    }
                )

        # 2) Aplicar las correcciones validadas
        for corr, existing, norm in prepared:
            new_value = float(norm["value_canonical"])
            subscore, _ = scoring_engine.calculate_subscore(
                marker_code=corr.marker_code,
                value=new_value,
                reference=existing.get("reference"),
            )
            original_value = existing.get("original_value_canonical")
            if original_value is None:
                original_value = existing.get("value_canonical")

            db.clinical_markers.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "value_raw": corr.value_raw,
                        "unit_raw": corr.unit_raw,
                        "value_canonical": norm["value_canonical"],
                        "unit_canonical": norm["unit_canonical"],
                        "censoring": norm.get("censoring"),
                        "status": norm["status"],
                        "subscore": subscore,
                        "scoring_version": scoring_engine.scoring_version,
                        "confirmation_level": ConfirmationLevel.CLINICIAN.value,
                        "edited": True,
                        "edited_by": "clinician",
                        "edited_by_id": current_clinician,
                        "edited_at": now,
                        "original_value_canonical": original_value,
                        "correction_reason": corr.reason,
                        "provenance": "clinician_corrected",
                        "updated_at": now,
                    }
                }
            )

            # Reflejar la corrección en la extracción (lo que ven GET /extraction y el reporte)
            for panel in panels:
                for mk in panel.get("markers", []):
                    if mk.get("marker_code") == corr.marker_code:
                        mk.update({
                            "value_raw": corr.value_raw,
                            "unit_raw": corr.unit_raw,
                            "value_canonical": norm["value_canonical"],
                            "unit_canonical": norm["unit_canonical"],
                            "conversion_factor": norm.get("conversion_factor", mk.get("conversion_factor", 1.0)),
                            "status": norm["status"],
                            "edited": True,
                            "edited_by": "clinician",
                            "edited_by_id": current_clinician,
                            "edited_at": now,
                            "original_value_canonical": original_value,
                            "provenance": {"source": "clinician_corrected"},
                        })

            applied_corrections.append({
                "marker_code": corr.marker_code,
                "previous_value_canonical": existing.get("value_canonical"),
                "new_value_canonical": norm["value_canonical"],
                "unit_canonical": norm["unit_canonical"],
                "reason": corr.reason,
            })

        ext_doc["panels"] = panels
        db.clinical_test_extractions.update_one(
            {"_id": ext_doc["_id"]},
            {
                "$set": {
                    "status": ExtractionStatus.CLINICALLY_VALIDATED.value,
                    "panels": panels,
                    "confirmation.validated_by": current_clinician,
                    "confirmation.validated_at": now,
                    "confirmation.validation_note": request.clinical_note,
                    "updated_at": now,
                }
            }
        )
        db.clinical_tests.update_one(
            {"clinical_test_id": clinical_test_id},
            {
                "$set": {
                    "extraction.status": ExtractionStatus.CLINICALLY_VALIDATED.value,
                    "extraction.validated_by": current_clinician,
                    "extraction.validated_at": now,
                    "updated_at": now,
                }
            }
        )
        ext_doc["status"] = ExtractionStatus.CLINICALLY_VALIDATED.value

        # Solo las correcciones del clínico disparan un recálculo del puntaje (§7.4.4)
        if applied_corrections:
            logger.info(f"🔄 Recalculando score para paciente {doc['patient_id']} con trigger=clinician_correction")
            try:
                snapshot = scoring_engine.compute_patient_score(
                    patient_id=doc["patient_id"],
                    db=db,
                    trigger="clinician_correction",
                    window_months=12,
                    excluded_markers_info=[]
                )
                if snapshot:
                    logger.info(f"✅ Nuevo snapshot creado: {snapshot.get('snapshot_id')} con trigger=clinician_correction")
            except Exception as e:
                # La validación ya quedó guardada: no devolver 500 por un fallo de recálculo
                logger.error(f"❌ Error recalculando score tras la validación: {e}", exc_info=True)

    # Auditoría de la validación / rechazo clínico y de cada corrección (§7.3, §12.8)
    _audit_event(
        db,
        "clinical_rejection" if request.validation_status == "rejected" else "clinical_validation",
        doc["patient_id"], clinical_test_id, extraction_id, "clinician", current_clinician,
        corrections=len(applied_corrections),
    )
    for ac in applied_corrections:
        _audit_event(db, "marker_correction", doc["patient_id"], clinical_test_id, extraction_id,
                     "clinician", current_clinician, **ac)

    return ExtractionResponse(
        schema_version="1.0",
        clinical_test_id=clinical_test_id,
        extraction_id=extraction_id,
        status=ExtractionStatus(ext_doc["status"]),
        document=ext_doc["document"],
        panels=ext_doc["panels"],
        flags=ext_doc.get("flags", []),
        extraction_meta=ext_doc.get("extraction_meta", {}),
        confirmation={
            "status": ext_doc["status"],
            "validated_by": current_clinician,
            "validated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "clinical_note": request.clinical_note,
        },
    )