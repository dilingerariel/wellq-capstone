// Generated from backend/docs/openapi.json. Do not edit.
// Source SHA-256: e0464fe981b8e6c8aae866d2254c3d626e7d94b405c75f6f489841d50ad6bc7a
export type CatalogItemResponse = { "catalog_version"?: string; "clinically_validated"?: boolean; "marker_code": string; "name": string; "panel_code": string; "specimen": string; "canonical_unit": string; "supported_units": Array<string>; "pillars": Array<string>; "typical_range": { [key: string]: unknown } }

export type ClinicalTestResponse = { "clinical_version"?: string | null; "clinical_test_id": string; "patient_id": string; "title": string; "test_type": TestType; "test_date": string; "notes"?: string | null; "case_id"?: string | null; "appointment_id"?: string | null; "file": FileInfo; "status": UploadStatus; "review": ReviewInfo; "created_at": string; "updated_at": string }

export type ClinicianValidationRequest = { "expected_version"?: string | null; "validation_status"?: "validated" | "rejected"; "marker_corrections"?: Array<MarkerCorrection> | null; "clinical_note"?: string | null }

export type CompleteUploadRequest = { "client_upload_id": string; "sha256": string; "size_bytes": number }

export type CompleteUploadResponse = { "clinical_test_id": string; "upload_id": string; "status": UploadStatus; "local_file_can_be_deleted": boolean; "status_url": string }

export type ConfidenceScores = { "value"?: number; "unit"?: number; "reference"?: number; "name"?: number }

export type DocumentEdits = { "collection_date"?: string | null; "report_date"?: string | null; "document_type"?: DocumentType | null; "identity_confirmed"?: boolean | null }

export type DocumentMetadata = { "document_type"?: DocumentType; "description"?: string; "language"?: string; "page_count"?: number; "collection_date"?: string | null; "report_date"?: string | null }

export type DocumentType = "blood_panel" | "urine_panel" | "imaging_report" | "other" | "unreadable"

export type DownloadUrlResponse = { "url": string; "expires_at": string; "file_name": string }

export type EditClinicalTestRequest = { "title"?: string; "test_type"?: TestType; "test_date"?: string; "notes"?: string | null; "case_id"?: string | null; "appointment_id"?: string | null }

export type ErrorDetail = { "code": string; "message"?: string | null; "errors"?: Array<{ [key: string]: unknown }> | null; "reason"?: string | null; [key: string]: unknown }

export type ErrorResponse = { "detail": ErrorDetail }

export type ExcludedMarker = { "marker_code"?: string | null; "raw_name"?: string | null; "reason": string }

export type ExtractionResponse = { "clinical_version"?: string | null; "schema_version"?: string; "clinical_test_id": string; "extraction_id": string; "status": ExtractionStatus; "document": DocumentMetadata; "panels"?: Array<PanelItem>; "flags"?: Array<{ [key: string]: unknown }>; "extraction_meta"?: { [key: string]: unknown }; "confirmation"?: { [key: string]: unknown } }

export type ExtractionStatus = "queued" | "extracting" | "awaiting_confirmation" | "confirmed" | "clinically_validated" | "extraction_failed" | "unreadable" | "discarded" | "not_applicable" | "rejected"

export type FileInfo = { "name": string; "mime_type": string; "size_bytes": number }

export type FlagSeverity = "critical" | "high" | "info"

export type InitiateUploadRequest = { "client_upload_id": string; "file_name": string; "mime_type": string; "size_bytes": number; "sha256": string; "test_type": TestType; "title": string; "test_date": string; "ai_consent"?: boolean; "notes"?: string | null; "case_id"?: string | null; "appointment_id"?: string | null }

export type InitiateUploadResponse = { "upload_id": string; "clinical_test_id": string; "status"?: UploadStatus; "upload": SignedUrlResponse }

export type LabReportExportRequest = { "clinical_test_id"?: string | null; "window_months"?: number; "include_series"?: boolean; "expected_source_version"?: string | null }

export type LabReportExportResponse = { "source_version": string; "verified_at": string; "export_id": string; "patient_id": string; "status": "ready" | "download_pending"; "file_name": string; "download_url": string | null; "expires_at": string | null; "size_bytes": number; "sha256": string; "storage": string; "replayed": boolean; "generated_at": string; "error_code"?: string | null }

export type LabReportResponse = { "source_version": string; "generated_at": string; "header": { [key: string]: unknown }; "score": { [key: string]: unknown } | null; "flags": Array<{ [key: string]: unknown }>; "results": { [key: string]: unknown }; "longitudinal": { [key: string]: unknown } | null; "imaging_findings": Array<{ [key: string]: unknown }>; "traceability": { [key: string]: unknown }; "actions": { [key: string]: string } }

export type LabScoreResponse = { "current_snapshot": ScoreSnapshotModel; "history"?: Array<ScoreSnapshotModel> | null }

export type ListClinicalTestsResponse = { "items": Array<{ [key: string]: unknown }>; "next_cursor"?: string | null }

export type MarkerCorrection = { "marker_code": string; "value_raw": string; "unit_raw": string; "reason"?: string | null }

export type MarkerEdit = { "op": "add" | "update" | "remove"; "marker_code": string; "value_raw"?: string | null; "unit_raw"?: string | null; "reference"?: ReferenceRange | null; "reason"?: string | null }

export type MarkerItem = { "marker_code": string; "loinc"?: string | null; "raw_name": string; "mapping_status"?: string; "value_type"?: string; "value_raw": string; "unit_raw": string; "value_canonical"?: number | null; "unit_canonical"?: string | null; "conversion_factor"?: number; "censoring"?: string | null; "value_text"?: string | null; "reference"?: ReferenceRange | null; "status"?: MarkerStatus; "confidence"?: ConfidenceScores; "provider_confidence"?: ConfidenceScores | null; "provenance"?: { [key: string]: unknown }; "validation"?: { [key: string]: unknown }; "edited"?: boolean; "edited_by"?: string | null; "edited_by_id"?: string | null; "edited_at"?: string | null; "original_value_canonical"?: number | null }

export type MarkerPoint = { "measured_on": string; "value": number | null; "unit": string | null; "reference": { [key: string]: unknown } | null; "status": string | null; "subscore": number | null; "subscore_blank_reason"?: string | null; "clinical_test_id": string; "confirmation_level": string | null; "edited": boolean }

export type MarkerSeries = { "marker_code": string; "unit": string | null; "points": Array<MarkerPoint> }

export type MarkerSeriesResponse = { "patient_id": string; "from": string | null; "to": string | null; "only_confirmed": boolean; "series": Array<MarkerSeries> }

export type MarkerStatus = "low" | "normal" | "high" | "critical_low" | "critical_high" | "indeterminate"

export type PanelItem = { "panel_code": string; "panel_name_raw": string; "specimen"?: string; "collection_date"?: string | null; "fasting"?: boolean | null; "markers"?: Array<MarkerItem> }

export type PatientConfirmationRequest = { "action"?: "confirm" | "discard"; "extraction_id": string; "acknowledged_marker_codes"?: Array<string>; "document_edits"?: DocumentEdits | null; "marker_edits"?: Array<MarkerEdit> | null }

export type PillarContribution = { "marker_code": string; "name": string; "value": number; "unit": string; "subscore": number; "weight": number; "clinical_test_id"?: string | null; "measured_on"?: string | null }

export type PillarScore = { "score"?: number | null; "coverage": number; "confidence": ScoreConfidence; "status"?: string; "contributions"?: Array<PillarContribution> }

export type ProcessingStatus = { "malware_scan": ScanStatus; "mime_validation": ScanStatus }

export type ReferenceRange = { "low"?: number | null; "high"?: number | null; "unit"?: string | null; "source"?: string; "text_raw"?: string | null }

export type RefreshUrlRequest = { "client_upload_id": string; "sha256": string }

export type RefreshUrlResponse = { "upload_id": string; "status": UploadStatus; "upload": SignedUrlResponse }

export type ReprocessRequest = { "confirm_reprocess_confirmed"?: boolean }

export type ReviewInfo = { "status": ReviewStatus; "reviewed_at"?: string | null; "reviewed_by"?: string | null }

export type ReviewRequest = { "expected_version"?: string | null; "review_status"?: string; "review_note"?: string | null }

export type ReviewStatus = "not_reviewed" | "reviewed"

export type ScanStatus = "pending" | "passed" | "failed" | "not_applicable"

export type ScoreConfidence = "high" | "medium" | "insufficient"

export type ScoreFlag = { "code": string; "severity": FlagSeverity; "marker_code": string; "value": number; "unit"?: string | null; "message": string }

export type ScoreSnapshotModel = { "catalog_hash"?: string | null; "source_digest"?: string | null; "parameters"?: { [key: string]: unknown }; "catalog_clinically_approved"?: boolean; "snapshot_id": string; "patient_id": string; "computed_at": string; "trigger": string; "scoring_version"?: string; "catalog_version"?: string; "window": { [key: string]: unknown }; "lab_index"?: number | null; "base_score"?: number | null; "penalty_applied"?: number; "pillars": { [key: string]: PillarScore }; "flags"?: Array<ScoreFlag>; "excluded_markers"?: Array<ExcludedMarker> }

export type SignedUrlResponse = { "method"?: string; "signed_url": string; "required_headers": { [key: string]: unknown }; "expires_at": string }

export type TestType = "blood_test" | "urine_test" | "imaging" | "pathology" | "other"

export type UploadStatus = "initiated" | "object_uploaded" | "processing" | "ready_for_review" | "rejected" | "failed" | "deleted"

export type UploadStatusResponse = { "clinical_test_id": string; "upload_id": string; "status": UploadStatus; "processing": ProcessingStatus; "local_file_can_be_deleted": boolean; "error"?: { [key: string]: unknown } | null; "completed_at"?: string | null }
