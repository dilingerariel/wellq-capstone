from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Literal, Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from app.services.clinical_dates import validate_clinical_date

class ExtractionStatus(str, Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    CLINICALLY_VALIDATED = "clinically_validated"
    EXTRACTION_FAILED = "extraction_failed"
    UNREADABLE = "unreadable"
    DISCARDED = "discarded"
    NOT_APPLICABLE = "not_applicable"
    REJECTED = "rejected"

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
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    @field_validator("low", "high", mode="before")
    @classmethod
    def numeric_bound(cls, value):
        if isinstance(value, bool):
            raise ValueError("Reference bounds must be numeric, not boolean")
        return value

    @model_validator(mode="after")
    def ordered(self):
        if self.low is not None and self.high is not None and self.low >= self.high:
            raise ValueError("Reference low must be below high")
        return self

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
    @model_validator(mode="after")
    def effective_display_status(self):
        # Every extraction response uses this model, including legacy proposals.
        from app.services.scoring import scoring_engine
        self.status = MarkerStatus(scoring_engine.display_status(self.model_dump()))
        if self.validation.get("passed") is False:
            self.provider_confidence = self.provider_confidence or self.confidence.model_copy(deep=True)
            self.confidence = ConfidenceScores(value=0, unit=0, reference=0, name=0)
        return self

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
    provider_confidence: Optional[ConfidenceScores] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    validation: Dict[str, Any] = Field(default_factory=dict)
    edited: bool = False
    edited_by: Optional[str] = None  # patient | clinician (§7.3)
    edited_by_id: Optional[str] = None  # identificador de quien editó
    edited_at: Optional[datetime] = None
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
    clinical_version: str | None = None
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
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    op: Literal["add", "update", "remove"]  # update | add | remove
    marker_code: str
    value_raw: Optional[str] = None
    unit_raw: Optional[str] = None
    reference: Optional[ReferenceRange] = None
    reason: Optional[str] = None

class DocumentEdits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("collection_date", "report_date")
    @classmethod
    def date_format(cls, value):
        return validate_clinical_date(value)

    collection_date: Optional[str] = None
    report_date: Optional[str] = None
    document_type: Optional[DocumentType] = None
    identity_confirmed: Optional[bool] = None

class PatientConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["confirm", "discard"] = "confirm"  # confirm | discard
    extraction_id: str
    acknowledged_marker_codes: List[str] = Field(default_factory=list, max_length=1000)
    document_edits: Optional[DocumentEdits] = None
    marker_edits: Optional[List[MarkerEdit]] = Field(default_factory=list, max_length=1000)

class MarkerCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    marker_code: str
    value_raw: str
    unit_raw: str
    reason: Optional[str] = "clinical_correction"

class ClinicianValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: str | None = Field(None, pattern="^[a-f0-9]{64}$")
    validation_status: Literal["validated", "rejected"] = "validated"  # validated | rejected
    marker_corrections: Optional[List[MarkerCorrection]] = Field(default_factory=list, max_length=1000)
    clinical_note: Optional[str] = None

class CatalogItemResponse(BaseModel):
    catalog_version: str = "cat-2026.08"
    clinically_validated: bool = False
    marker_code: str
    name: str
    panel_code: str
    specimen: str
    canonical_unit: str
    supported_units: List[str]
    pillars: List[str]
    typical_range: Dict[str, Any]
