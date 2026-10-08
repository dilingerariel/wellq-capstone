from fastapi import HTTPException, status
from typing import Optional

from app.database import get_database

# Colección con la relación asistencial paciente-clínico.
# DECISIÓN PENDIENTE DEL EQUIPO: la spec (§4.2 / endpoints) dice "usar el modelo de acceso clínico
# existente de la plataforma". Si esos datos viven en otra colección o servicio (p. ej. `patients`),
# basta con cambiar este nombre o reescribir _has_clinical_relationship().
# Campos soportados (según la spec): care_clinician_id, authorised_clinicians (también se acepta
# la grafía "authorized_clinicians") y clinic_id (pertenencia a la clínica).
PATIENT_ACCESS_COLLECTION = "patient_access"


async def require_patient_access(patient_id_param: str, current_patient_id: str) -> str:
    """Verificar que el paciente solo accede a sus propios recursos"""
    if patient_id_param != current_patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "No tienes acceso a este recurso"}
        )
    return patient_id_param


def _has_clinical_relationship(patient_id: str, clinician_id: str, clinic_id: Optional[str]) -> bool:
    conditions = [
        {"care_clinician_id": clinician_id},
        {"authorised_clinicians": clinician_id},
        {"authorized_clinicians": clinician_id},
    ]
    if clinic_id:
        conditions.append({"clinic_id": clinic_id})
    relation = get_database()[PATIENT_ACCESS_COLLECTION].find_one(
        {"patient_id": patient_id, "$or": conditions}, {"_id": 1}
    )
    return relation is not None


async def require_clinician_access(
    patient_id: str,
    current_clinician_id: str,
    clinic_id: Optional[str] = None,
) -> str:
    """
    Verificar que el clínico tiene relación asistencial con el paciente:
      - es su clínico de cabecera (care_clinician_id), o
      - está en su lista de clínicos autorizados (authorised_clinicians), o
      - pertenece a la clínica del paciente (clinic_id, si el token la trae).
    Si no la tiene: 403 NO_PATIENT_ACCESS.
    """
    if not current_clinician_id or not _has_clinical_relationship(patient_id, current_clinician_id, clinic_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NO_PATIENT_ACCESS", "message": "El clínico no tiene acceso a este paciente"}
        )
    return patient_id