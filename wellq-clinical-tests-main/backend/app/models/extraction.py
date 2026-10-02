from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

class ExtractionStatus(str, Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    CLINICALLY_VALIDATED = "clinically_validated"
    EXTRACTION_FAILED = "extraction_failed"
    UNREADABLE = "unreadable"
    DISCARDED = "discarded"

class DocumentType(str, Enum):
    BLOOD_PANEL = "blood_panel"
    URINE_PANEL = "urine_panel"
    IMAGING_REPORT = "imaging_report"
    OTHER = "other"
    UNREADABLE = "unreadable"

class MarkerStatus(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL_LOW = "critical_low"
    CRITICAL_HIGH = "critical_high"
    INDETERMINATE = "indeterminate"

class ConfirmationLevel(str, Enum):
    PATIENT = "patient"
    CLINICIAN = "clinician"

# ============ SCHEMAS DE MARCADORES ============

class ReferenceRange(BaseModel):
    low: Optional[float] = None
    high: Optional[float] = None
    unit: Optional[str] = None
    source: str = "document"  # document | catalog | none
    text_raw: Optional[str] = None

class ConfidenceScores(BaseModel):
    value: float = Field(1.0, ge=0.0, le=1.0)
    unit: float = Field(1.0, ge=0.0, le=1.0)
    reference: float = Field(1.0, ge=0.0, le=1.0)
    name: float = Field(1.0, ge=0.0, le=1.0)

class MarkerItem(BaseModel):
    marker_code: str
    loinc: Optional[str] = None
    raw_name: str
    mapping_status: str = "mapped"  # mapped | unmapped
    value_type: str = "numeric"  # numeric | qualitative | ordinal
    value_raw: str
    unit_raw: str
    value_canonical: Optional[float] = None
    unit_canonical: Optional[str] = None
    conversion_factor: float = 1.0
    censoring: Optional[str] = None  # null | left | right
    value_text: Optional[str] = None
    reference: Optional[ReferenceRange] = None
    status: MarkerStatus = MarkerStatus.NORMAL
    confidence: ConfidenceScores = Field(default_factory=ConfidenceScores)
    edited: bool = False
    edited_by: Optional[str] = None
    original_value_canonical: Optional[float] = None

class PanelItem(BaseModel):
    panel_code: str
    panel_name_raw: str
    specimen: str = "blood"  # blood | urine
    collection_date: Optional[str] = None
    fasting: Optional[bool] = None
    markers: List[MarkerItem] = []

class DocumentMetadata(BaseModel):
    document_type: DocumentType = DocumentType.BLOOD_PANEL
    description: str = ""
    language: str = "es"
    page_count: int = 1
    collection_date: Optional[str] = None
    report_date: Optional[str] = None

class ExtractionResponse(BaseModel):
    schema_version: str = "1.0"
    clinical_test_id: str
    extraction_id: str
    status: ExtractionStatus
    document: DocumentMetadata
    panels: List[PanelItem] = []
    flags: List[Dict[str, Any]] = []
    extraction_meta: Dict[str, Any] = {}
    confirmation: Dict[str, Any] = {}

# ============ REQUESTS PARA ENDPOINTS 13, 14, 15 ============

class MarkerEdit(BaseModel):
    op: str  # update | add | remove
    marker_code: str
    value_raw: Optional[str] = None
    unit_raw: Optional[str] = None
    reference: Optional[ReferenceRange] = None
    reason: Optional[str] = None

class DocumentEdits(BaseModel):
    collection_date: Optional[str] = None
    document_type: Optional[DocumentType] = None
    identity_confirmed: Optional[bool] = True

class PatientConfirmationRequest(BaseModel):
    action: str = "confirm"  # confirm | discard
    extraction_id: str
    document_edits: Optional[DocumentEdits] = None
    marker_edits: Optional[List[MarkerEdit]] = []

class MarkerCorrection(BaseModel):
    marker_code: str
    value_raw: str
    unit_raw: str
    reason: Optional[str] = "clinical_correction"

class ClinicianValidationRequest(BaseModel):
    validation_status: str = "validated"  # validated | rejected
    marker_corrections: Optional[List[MarkerCorrection]] = []
    clinical_note: Optional[str] = None

class CatalogItemResponse(BaseModel):
    marker_code: str
    name: str
    panel_code: str
    specimen: str
    canonical_unit: str
    supported_units: List[str]
    pillars: List[str]
    typical_range: Dict[str, Any]
