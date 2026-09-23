from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from .enums import UploadStatus, TestType, ReviewStatus, ScanStatus

# ============ REQUEST SCHEMAS ============

class InitiateUploadRequest(BaseModel):
    client_upload_id: str  # UUID
    file_name: str = Field(..., min_length=1, max_length=255)
    mime_type: str
    size_bytes: int = Field(..., gt=0)
    sha256: str = Field(..., min_length=64, max_length=64)
    test_type: TestType
    title: str = Field(..., min_length=1, max_length=200)
    test_date: str  # YYYY-MM-DD
    notes: Optional[str] = Field(None, max_length=2000)
    case_id: Optional[str] = None
    appointment_id: Optional[str] = None

    @validator('sha256')
    def validate_sha256(cls, v):
        if not all(c in '0123456789abcdef' for c in v.lower()):
            raise ValueError('SHA-256 debe ser hex válido (minúsculas)')
        return v.lower()

class RefreshUrlRequest(BaseModel):
    client_upload_id: str
    sha256: str = Field(..., min_length=64, max_length=64)

class CompleteUploadRequest(BaseModel):
    client_upload_id: str
    sha256: str = Field(..., min_length=64, max_length=64)
    size_bytes: int = Field(..., gt=0)

class EditClinicalTestRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    test_type: Optional[TestType] = None
    test_date: Optional[str] = None  # YYYY-MM-DD
    notes: Optional[str] = Field(None, max_length=2000)
    case_id: Optional[str] = None
    appointment_id: Optional[str] = None

class ReviewRequest(BaseModel):
    review_status: str = "reviewed"  # Solo "reviewed" en v1
    review_note: Optional[str] = Field(None, max_length=2000)

# ============ RESPONSE SCHEMAS ============

class SignedUrlResponse(BaseModel):
    method: str = "PUT"
    signed_url: str
    required_headers: dict
    expires_at: str  # ISO8601

class InitiateUploadResponse(BaseModel):
    upload_id: str
    clinical_test_id: str
    status: UploadStatus = UploadStatus.INITIATED
    upload: SignedUrlResponse

class RefreshUrlResponse(BaseModel):
    upload_id: str
    status: UploadStatus
    upload: SignedUrlResponse

class CompleteUploadResponse(BaseModel):
    clinical_test_id: str
    upload_id: str
    status: UploadStatus
    local_file_can_be_deleted: bool
    status_url: str

class ProcessingStatus(BaseModel):
    malware_scan: ScanStatus
    mime_validation: ScanStatus

class UploadStatusResponse(BaseModel):
    clinical_test_id: str
    upload_id: str
    status: UploadStatus
    processing: ProcessingStatus
    local_file_can_be_deleted: bool
    error: Optional[dict] = None  # {code, message}
    completed_at: Optional[str] = None

class FileInfo(BaseModel):
    name: str
    mime_type: str
    size_bytes: int

class ReviewInfo(BaseModel):
    status: ReviewStatus
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None

class ClinicalTestResponse(BaseModel):
    clinical_test_id: str
    patient_id: str
    title: str
    test_type: TestType
    test_date: str
    notes: Optional[str] = None
    case_id: Optional[str] = None
    appointment_id: Optional[str] = None
    file: FileInfo
    status: UploadStatus
    review: ReviewInfo
    created_at: str
    updated_at: str

class ListClinicalTestsResponse(BaseModel):
    items: List[dict]
    next_cursor: Optional[str] = None

class DownloadUrlResponse(BaseModel):
    url: str
    expires_at: str
    file_name: str

class ErrorResponse(BaseModel):
    detail: dict  # {code, message}