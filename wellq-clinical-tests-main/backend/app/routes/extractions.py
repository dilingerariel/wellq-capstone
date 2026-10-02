import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pymongo.database import Database

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

    extraction_info = doc.get("extraction")
    if not extraction_info or not extraction_info.get("extraction_id"):
        # Si aún no se ha ejecutado la extracción, intentamos correr el extractor
        try:
            extraction_engine.run_extraction_pipeline(clinical_test_id, db)
            doc = db.clinical_tests.find_one({"clinical_test_id": clinical_test_id})
            extraction_info = doc.get("extraction")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "EXTRACTION_NOT_READY", "message": f"La extracción aún no está lista: {e}"}
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
                    "updated_at": now,
                }
            }
        )
        db.clinical_tests.update_one(
            {"clinical_test_id": clinical_test_id},
            {"$set": {"extraction.status": ExtractionStatus.DISCARDED.value, "updated_at": now}}
        )
        ext_doc["status"] = ExtractionStatus.DISCARDED.value
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

    if request.marker_edits:
        for edit in request.marker_edits:
            m_code = edit.marker_code
            if edit.op == "remove":
                if m_code in active_markers_map:
                    del active_markers_map[m_code]
                    edit_count += 1
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
                    "censoring": None,
                    "value_text": None,
                    "reference": ref_dict,
                    "status": norm["status"],
                    "confidence": {"value": 1.0, "unit": 1.0, "reference": 1.0, "name": 1.0},
                    "validation": {"passed": True, "errors": []},
                    "provenance": {"source": "patient_confirmed"},
                    "edited": True,
                    "edited_by": current_patient,
                    "original_value_canonical": active_markers_map.get(m_code, {}).get("value_canonical"),
                }
                active_markers_map[m_code] = marker_data
                edit_count += 1

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
                "confirmation": {
                    "status": "confirmed",
                    "confirmed_by": current_patient,
                    "confirmed_at": now,
                    "validated_by": None,
                    "validated_at": None,
                    "edit_count": edit_count,
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

    # Disparar cálculo de score_snapshot (§8.8)
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
            db.clinical_tests.update_one(
                {"clinical_test_id": clinical_test_id},
                {"$set": {"extraction.score_snapshot_id": snapshot.get("snapshot_id")}}
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
        },
    )

# ============ ENDPOINT 14: REPROCESS EXTRACTION ============

@router.post(
    "/clinical-tests/{clinical_test_id}/extraction/reprocess",
    response_model=ExtractionResponse,
    summary="Reprocesar extracción del documento",
)
async def reprocess_extraction(
    clinical_test_id: str,
    idempotency_key: str = Header(...),
    current_patient: str = Depends(get_current_patient),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #14: POST /api/v1/clinical-tests/{clinical_test_id}/extraction/reprocess
    Vuelve a encolar la extracción del mismo documento, invalidando la anterior.
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

    now = datetime.utcnow()

    # Archivar extracción vigente
    old_ext_id = doc.get("extraction", {}).get("extraction_id")
    if old_ext_id:
        db.clinical_test_extractions.update_one(
            {"extraction_id": old_ext_id},
            {"$set": {"superseded_at": now, "updated_at": now}}
        )

    # Invalidar marcadores previos
    db.clinical_markers.update_many(
        {"clinical_test_id": clinical_test_id},
        {"$set": {"invalidated_at": now}}
    )

    # Ejecutar nueva extracción
    new_ext_doc = extraction_engine.run_extraction_pipeline(clinical_test_id, db)

    return ExtractionResponse(
        schema_version="1.0",
        clinical_test_id=clinical_test_id,
        extraction_id=new_ext_doc["extraction_id"],
        status=ExtractionStatus(new_ext_doc["status"]),
        document=new_ext_doc["document"],
        panels=new_ext_doc["panels"],
        flags=new_ext_doc.get("flags", []),
        extraction_meta=new_ext_doc.get("extraction_meta", {}),
        confirmation=new_ext_doc.get("confirmation", {}),
    )

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
    """
    doc = db.clinical_tests.find_one({"clinical_test_id": clinical_test_id, "deleted_at": None})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Examen médico no encontrado"}
        )

    await require_clinician_access(doc["patient_id"], current_clinician)

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

    if request.validation_status == "rejected":
        # Rechazar extracción: invalida marcadores
        db.clinical_markers.update_many(
            {"clinical_test_id": clinical_test_id},
            {"$set": {"invalidated_at": now}}
        )
        db.clinical_test_extractions.update_one(
            {"_id": ext_doc["_id"]},
            {
                "$set": {
                    "status": "rejected",
                    "confirmation.validated_by": current_clinician,
                    "confirmation.validated_at": now,
                    "confirmation.validation_note": request.clinical_note,
                    "updated_at": now,
                }
            }
        )
        db.clinical_tests.update_one(
            {"clinical_test_id": clinical_test_id},
            {"$set": {"extraction.status": "rejected", "updated_at": now}}
        )
        # Invalidar marcadores en cascada (§11.5)
        db.clinical_markers.update_many(
            {"clinical_test_id": clinical_test_id},
            {"$set": {"invalidated_at": now}}
        )
        ext_doc["status"] = "rejected"

        # Recalcular puntaje sin los marcadores rechazados
        try:
            scoring_engine.compute_patient_score(
                patient_id=doc["patient_id"],
                db=db,
                trigger="clinician_rejection"
            )
        except Exception as e:
            logger.warning(f"Aviso al recalcular tras rechazo clínico: {e}")
    else:
        # Validar y aplicar correcciones del clínico si vienen
        panels = ext_doc.get("panels", [])
        if request.marker_corrections:
            for corr in request.marker_corrections:
                norm = catalog_service.validate_and_convert(corr.marker_code, corr.value_raw, corr.unit_raw, db)
                if norm["valid"]:
                    subscore, _ = scoring_engine.calculate_subscore(
                        marker_code=corr.marker_code,
                        value=float(norm["value_canonical"]),
                    )
                    db.clinical_markers.update_one(
                        {"clinical_test_id": clinical_test_id, "marker_code": corr.marker_code},
                        {
                            "$set": {
                                "value_raw": corr.value_raw,
                                "unit_raw": corr.unit_raw,
                                "value_canonical": norm["value_canonical"],
                                "unit_canonical": norm["unit_canonical"],
                                "status": norm["status"],
                                "subscore": subscore,
                                "scoring_version": scoring_engine.scoring_version,
                                "confirmation_level": ConfirmationLevel.CLINICIAN.value,
                                "edited": True,
                                "provenance": "clinician_corrected",
                                "updated_at": now,
                            }
                        }
                    )

        db.clinical_test_extractions.update_one(
            {"_id": ext_doc["_id"]},
            {
                "$set": {
                    "status": ExtractionStatus.CLINICALLY_VALIDATED.value,
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

        # Recalcular puntaje con las correcciones médicas (8 espacios = dentro del else)
        trigger_type = "clinician_correction" if request.marker_corrections else "clinician_validation"
        logger.info(f"🔄 Recalculando score para paciente {doc['patient_id']} con trigger={trigger_type}")

        try:
            snapshot = scoring_engine.compute_patient_score(
                patient_id=doc["patient_id"],
                db=db,
                trigger=trigger_type,
                window_months=12,
                excluded_markers_info=[]
            )
            logger.info(f"✅ Nuevo snapshot creado: {snapshot.get('snapshot_id')} con trigger={trigger_type}")
        except Exception as e:
            logger.error(f"❌ Error recalculando score: {e}", exc_info=True)
            raise

    # Return fuera del if-else (4 espacios = dentro de la función)
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