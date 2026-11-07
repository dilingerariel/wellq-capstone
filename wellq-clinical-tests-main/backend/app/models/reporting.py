"""Stable response envelopes for clinician-only reporting operations."""
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field, model_validator


class MarkerPoint(BaseModel):
    measured_on: str
    value: Optional[float]
    unit: Optional[str]
    reference: Optional[dict[str, Any]]
    status: Optional[str]
    subscore: Optional[float]
    subscore_blank_reason: Optional[str] = None
    clinical_test_id: str
    confirmation_level: Optional[str]
    edited: bool


class MarkerSeries(BaseModel):
    marker_code: str
    unit: Optional[str]
    points: list[MarkerPoint]


class MarkerSeriesResponse(BaseModel):
    patient_id: str
    date_from: Optional[str] = Field(alias="from")
    date_to: Optional[str] = Field(alias="to")
    only_confirmed: bool
    series: list[MarkerSeries]


class LabReportResponse(BaseModel):
    source_version: str
    generated_at: str
    header: dict[str, Any]
    score: Optional[dict[str, Any]]
    flags: list[dict[str, Any]]
    results: dict[str, Any]
    longitudinal: Optional[dict[str, Any]]
    imaging_findings: list[dict[str, Any]]
    traceability: dict[str, Any]
    actions: dict[str, str]


class LabReportExportResponse(BaseModel):
    source_version: str
    verified_at: str
    export_id: str
    patient_id: str
    status: Literal["ready", "download_pending"]
    file_name: str
    download_url: Optional[str]
    expires_at: Optional[str]
    size_bytes: int
    sha256: str
    storage: Literal["gcs"]
    replayed: bool
    generated_at: str
    error_code: Optional[Literal["DOWNLOAD_URL_UNAVAILABLE"]] = None

    @model_validator(mode="after")
    def coherent_download(self):
        if self.status == "ready" and (not self.download_url or not self.expires_at):
            raise ValueError("Ready exports require a signed URL and expiry")
        if self.status == "download_pending" and (self.download_url is not None or self.expires_at is not None):
            raise ValueError("Pending downloads cannot expose a partial link")
        return self
