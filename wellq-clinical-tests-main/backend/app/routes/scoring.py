import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pymongo.database import Database

from app.database import get_database
from app.dependencies.auth import get_current_user, TokenPayload
from app.dependencies.access import require_clinician_access
from app.services.scoring import scoring_engine
from app.models.scoring import LabScoreResponse, ScoreSnapshotModel

logger = logging.getLogger(__name__)

router = APIRouter()

# ============ ENDPOINT 18: GET LAB SCORE ============

@router.get(
    "/patients/{patient_id}/lab-score",
    response_model=LabScoreResponse,
    summary="Consultar puntaje vigente e histórico de laboratorio",
)
async def get_patient_lab_score(
    patient_id: str,
    history: bool = Query(False, description="Incluir histórico de snapshots anteriores"),
    user: TokenPayload = Depends(get_current_user),
    db: Database = Depends(get_database),
):
    """
    ENDPOINT #18: GET /api/v1/patients/{patient_id}/lab-score
    Devuelve el snapshot vigente y, con history=true, el histórico de snapshots.
    """
    # 1. Control de acceso estricto
    if user.role == "patient":
        if user.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "No tienes acceso a los puntajes de este paciente"}
            )
    elif user.role == "clinician":
        await require_clinician_access(patient_id, user.clinician_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Rol no autorizado"}
        )

    # 2. Buscar snapshot vigente en score_snapshots
    snapshots = list(db.score_snapshots.find(
        {"patient_id": patient_id},
        {"_id": 0}
    ).sort("computed_at", -1))

    if not snapshots:
        # Intentar calcular si hay marcadores confirmados
        computed = scoring_engine.compute_patient_score(
            patient_id=patient_id,
            db=db,
            trigger="on_demand"
        )
        if computed and (computed.get("lab_index") is not None or any(p.get("score") is not None for p in computed.get("pillars", {}).values())):
            snapshots = [computed]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "NO_SCORE_AVAILABLE",
                    "message": "No hay puntaje de laboratorio disponible para este paciente (sin exámenes confirmados o cobertura insuficiente en los cuatro pilares)"
                }
            )

    current_snapshot = snapshots[0]
    history_list: Optional[List[ScoreSnapshotModel]] = None
    if history and len(snapshots) > 1:
        history_list = snapshots[1:]

    return LabScoreResponse(
        current_snapshot=current_snapshot,
        history=history_list,
    )
