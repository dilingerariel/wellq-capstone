from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime
from .enums import UploadStatus, TestType, ReviewStatus, ScanStatus
from app.services.clinical_dates import validate_clinical_date
from app.services.upload_metadata import normalize_filename

# Unknown fields are rejected to prevent misspelled clinical edits or identity fields.
class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

# ============ REQUEST SCHEMAS ============

class InitiateUploadRequest(RequestModel):
    @field_validator("file_name")
    @classmethod
    def filename(cls, value):
        return normalize_filename(value)

    @field_validator("mime_type")
    @classmethod
    def mime(cls, value):
        return value.lower()

    client_upload_id: str = Field(min_length=1, max_length=200)  # Stable client identifier
    file_name: str = Field(..., min_length=1, max_length=255)
    mime_type: str
    size_bytes: int = Field(..., gt=0)
    sha256: str = Field(..., min_length=64, max_length=64)
    test_type: TestType
    title: str = Field(..., min_length=1, max_length=200)
    test_date: str  # YYYY-MM-DD
    ai_consent: bool = False
    notes: Optional[str] = Field(None, max_length=2000)
    case_id: Optional[str] = None
    appointment_id: Optional[str] = None

    @field_validator("test_date")
    @classmethod
    def date_format(cls, value):
        return validate_clinical_date(value)

    @field_validator('sha256')
    @classmethod
    def validate_sha256(cls, v):
        if not all(c in '0123456789abcdef' for c in v.lower()):
            raise ValueError('SHA-256 debe ser hex válido (minúsculas)')
        return v.lower()

class RefreshUrlRequest(RequestModel):
    client_upload_id: str
    sha256: str = Field(..., min_length=64, max_length=64)

    @field_validator("sha256")
    @classmethod
    def checksum(cls, value):
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
            raise ValueError("Expected SHA256 hexadecimal")
        return value.lower()

class CompleteUploadRequest(RequestModel):
    client_upload_id: str
    sha256: str = Field(..., min_length=64, max_length=64)
    size_bytes: int = Field(..., gt=0)

    @field_validator("sha256")
    @classmethod
    def checksum(cls, value):
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
            raise ValueError("Expected SHA256 hexadecimal")
        return value.lower()

class EditClinicalTestRequest(RequestModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, json_schema_extra={"minProperties": 1})

    @model_validator(mode="after")
    def require_edit(self):
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        return self

    @field_validator("test_date")
    @classmethod
    def date_format(cls, value):
        return validate_clinical_date(value)

    title: str = Field(None, min_length=1, max_length=200)
    test_type: TestType = None
    test_date: str = None  # Omitted means unchanged; explicit null is invalid.
    notes: Optional[str] = Field(None, max_length=2000)
    case_id: Optional[str] = None
    appointment_id: Optional[str] = None

class ReviewRequest(RequestModel):
    expected_version: str | None = Field(None, pattern="^[a-f0-9]{64}$")
    review_status: Literal["reviewed"] = "reviewed"  # Solo "reviewed" en v1
    review_note: Optional[str] = Field(None, max_length=2000)
    patient_message: Optional[str] = Field(None, max_length=2000)

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
    patient_message: Optional[str] = None

class ClinicalTestResponse(BaseModel):
    clinical_version: str | None = None
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
