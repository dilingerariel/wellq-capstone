from fastapi import HTTPException, status
from typing import Optional

async def require_patient_access(patient_id_param: str, current_patient_id: str) -> str:
    """Verificar que el paciente solo accede a sus propios recursos"""
    if patient_id_param != current_patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "No tienes acceso a este recurso"}
        )
    return patient_id_param

async def require_clinician_access(patient_id: str, current_clinician_id: str) -> str:
    """
    Verificar que el clínico tiene acceso al paciente.
    TODO: Implementar lógica real de relación asistencial
    (care_clinician_id, authorized_clinicians, etc.)
    """
    # Por ahora, acceso a todos. En producción:
    # - Verificar care_clinician_id
    # - Verificar authorized_clinicians list
    # - Verificar pertenencia a clínica
    
    return patient_id