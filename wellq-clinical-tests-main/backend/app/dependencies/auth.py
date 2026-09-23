from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from typing import Optional

from app.config import settings

security = HTTPBearer()

class TokenPayload:
    def __init__(self, sub: str, role: str, patient_id: Optional[str] = None, clinician_id: Optional[str] = None):
        self.sub = sub
        self.role = role
        self.patient_id = patient_id
        self.clinician_id = clinician_id

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenPayload:
    """Verificar JWT y retornar payload"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        sub: str = payload.get("sub")
        role: str = payload.get("role")
        
        if sub is None or role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "UNAUTHORIZED", "message": "Token inválido"}
            )
        
        return TokenPayload(
            sub=sub,
            role=role,
            patient_id=payload.get("patient_id"),
            clinician_id=payload.get("clinician_id"),
        )
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Token expirado"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Token inválido"}
        )

async def get_current_patient(user: TokenPayload = Depends(get_current_user)) -> str:
    """Solo pacientes"""
    if user.role != "patient" or not user.patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Solo pacientes pueden acceder"}
        )
    return user.patient_id

async def get_current_clinician(user: TokenPayload = Depends(get_current_user)) -> str:
    """Solo clínicos"""
    if user.role != "clinician" or not user.clinician_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Solo clínicos pueden acceder"}
        )
    return user.clinician_id