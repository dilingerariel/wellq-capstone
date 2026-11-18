"""Provider-independent extraction boundary. No synthetic production output."""
import copy
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Protocol, Literal
from pymongo.database import Database
from pydantic import BaseModel, ConfigDict, Field
from app.config import settings
from app.models.extraction import MarkerStatus, ConfidenceScores, ReferenceRange
from app.services.catalog import catalog_service
from app.services.storage import storage_service
from app.services.references import canonical_document_reference, reference_status
from app.services.clinical_dates import validate_extraction_dates

class ExtractionUnavailable(RuntimeError):
    pass

class ProviderConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    value: float = Field(ge=0, le=1)
    unit: float = Field(ge=0, le=1)
    reference: float = Field(ge=0, le=1)
    name: float = Field(ge=0, le=1)

class ProviderMarker(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    marker_code: str
    raw_name: str = Field(min_length=1)
    value_raw: str = Field(min_length=1)
    unit_raw: str = Field(min_length=1)
    confidence: ProviderConfidence
    reference: Optional[ReferenceRange] = None
    page: int = Field(ge=1)
    evidence: str = Field(min_length=1, max_length=4000)

class ProviderPanel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    panel_code: str
    panel_name_raw: str
    specimen: str
    collection_date: Optional[str] = None
    markers: list[ProviderMarker] = Field(max_length=1000)

class ProviderOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"]
    document_type: Literal["blood_panel", "urine_panel", "imaging_report", "other", "unreadable"]
    language: str
    page_count: int = Field(ge=1)
    collection_date: Optional[str] = None
    report_date: Optional[str] = None
    panels: list[ProviderPanel] = Field(max_length=30)

class MultimodalProvider(Protocol):
    model_id: str
    model_version: str
    is_test: bool
    def extract(self, data: bytes, mime_type: str) -> dict: ...

class ExtractionEngine:
    def __init__(self, provider: Optional[MultimodalProvider] = None):
        self.provider = provider
        self.prompt_version = "extract-v2.0"
        self.catalog_version = catalog_service.version

    def build_marker(self, m_code: str, raw_name: str, v_raw: str, u_raw: str, conf: float,
                     db: Optional[Database], line_no: int) -> Dict[str, Any]:
        """Normaliza un marcador. Si la validación determinista falla NO se descarta (§5.2.5, §5.5.2):
        se conserva con su valor literal, sin conversión, confianza 0 y una bandera; no se puntúa."""
        norm = catalog_service.validate_and_convert(m_code, v_raw, u_raw, db)
        if norm["valid"]:
            return {
                "marker_code": m_code,
                "loinc": None,
                "raw_name": raw_name,
                "mapping_status": "mapped",
                "value_type": "numeric",
                "value_raw": v_raw,
                "unit_raw": u_raw,
                "value_canonical": norm["value_canonical"],
                "unit_canonical": norm["unit_canonical"],
                "conversion_factor": norm["conversion_factor"],
                "censoring": norm.get("censoring"),
                "value_text": None,
                "reference": norm["reference"],
                "status": norm["status"],
                "confidence": {
                    "value": conf,
                    "unit": conf,
                    "reference": 0.95,
                    "name": 0.99,
                },
                "validation": {"passed": True, "errors": []},
                "provenance": {"page": 1, "line_hint": f"línea {line_no}"},
                "edited": False,
                "edited_by": None,
                "original_value_canonical": None,
            }

        error_code = norm["error_code"]
        return {
            "marker_code": m_code,
            "loinc": None,
            "raw_name": raw_name,
            "mapping_status": "unmapped" if error_code == "UNKNOWN_MARKER" else "mapped",
            "value_type": "numeric",
            "value_raw": v_raw,
            "unit_raw": u_raw,
            "value_canonical": None,
            "unit_canonical": None,
            "conversion_factor": 1.0,
            "censoring": None,
            "value_text": None,
            "reference": None,
            "status": MarkerStatus.INDETERMINATE.value,
            "confidence": {"value": 0.0, "unit": 0.0, "reference": 0.0, "name": 0.0},
            "validation": {"passed": False, "errors": [error_code]},
            "provenance": {"page": 1, "line_hint": f"línea {line_no}"},
            "edited": False,
            "edited_by": None,
            "original_value_canonical": None,
        }

    def classify_document(self, doc):
        # Classification requires document content and a configured provider.
        raise ExtractionUnavailable("Content classification provider required")

    def run_extraction_pipeline(self, clinical_test_id, db, as_of=None):
        provider = self.provider
        if provider is None or not settings.AI_PROVIDER_APPROVED:
            raise ExtractionUnavailable("Approved multimodal provider required")
        if provider.is_test and settings.ENVIRONMENT != "test":
            raise ExtractionUnavailable("Test provider forbidden outside isolated tests")
        doc = db.clinical_tests.find_one({"clinical_test_id": clinical_test_id, "deleted_at": None})
        if not doc or not doc.get("file", {}).get("verified_at") or doc["upload"]["status"] != "ready_for_review":
            raise ExtractionUnavailable("Verified document required")
        if not doc.get("ai_consent"):
            raise ExtractionUnavailable("Patient AI consent required")
        if getattr(provider, "synthetic_only", False):
            # Gemini Developer API is wired only for the fixed, non-identifying
            # presentation asset. Real clinical PDFs require an approved Vertex AI
            # deployment, never this developer endpoint.
            from app.routes.demo import SYNTHETIC_PDF_SHA256, SYNTHETIC_PDF_SIZE
            if (settings.ENVIRONMENT == "production" or not settings.DEMO_AUTH_ENABLED
                    or not settings.DEMO_MONGO_STORAGE_ENABLED
                    or doc.get("file", {}).get("sha256") != SYNTHETIC_PDF_SHA256
                    or doc.get("file", {}).get("size_bytes") != SYNTHETIC_PDF_SIZE):
                raise ExtractionUnavailable("Gemini Developer API is restricted to the fixed synthetic demo PDF")
        data, mime, generation = storage_service.read_object(doc["file"]["gcs_object_key"], doc["file"]["generation"])
        if generation != doc["file"]["generation"]:
            raise ExtractionUnavailable("Document generation changed")
        # Native PDF input is deliberate; any provider requiring rasterization must
        # supply a bounded implementation before deployment. HEIC is converted here.
        if mime == "image/heic":
            import io
            from PIL import Image
            from pillow_heif import register_heif_opener
            register_heif_opener()
            image = Image.open(io.BytesIO(data)); output = io.BytesIO()
            image.convert("RGB").save(output, format="JPEG"); data = output.getvalue(); mime = "image/jpeg"
        provider_output = provider.extract(data, mime)
        result = ProviderOutput.model_validate(provider_output)
        if result.page_count > settings.MAX_DOCUMENT_PAGES:
            raise ValueError("Page limit")
        validate_extraction_dates(result.model_dump(), [p.model_dump() for p in result.panels], as_of)
        panels, flags, seen = [], [], set()
        for panel in result.panels:
            markers = []
            for m in panel.markers:
                if m.marker_code in seen or m.page > result.page_count:
                    raise ValueError("Duplicate marker or invalid provenance")
                seen.add(m.marker_code)
                marker = self.build_marker(m.marker_code, m.raw_name, m.value_raw, m.unit_raw,
                                           m.confidence.value, db, len(markers) + 1)
                if m.reference is not None:
                    try:
                        marker["reference"] = canonical_document_reference(
                            m.reference.model_dump(exclude_none=True), m.unit_raw,
                            marker.get("unit_canonical"), marker.get("conversion_factor", 1.0))
                    except ValueError:
                        marker["reference"] = {"source": "none"}
                        flags.append({"code": "reference_unit_unknown", "marker_code": m.marker_code})
                marker["status"] = reference_status(marker.get("value_canonical"),
                    catalog_service.get_marker(m.marker_code) or {}, marker.get("reference"))
                declared = m.confidence.model_dump()
                marker["provider_confidence"] = declared
                marker["confidence"] = (declared.copy() if marker["validation"]["passed"]
                                        else dict.fromkeys(declared, 0.0))
                if (marker.get("reference") or {}).get("source") == "none":
                    marker["confidence"]["reference"] = 0.0
                marker["provenance"] = {"page": m.page, "evidence": m.evidence}
                if min(marker["confidence"].values()) < 0.9:
                    flags.append({"code": "low_confidence", "marker_code": m.marker_code})
                if not marker["validation"]["passed"]:
                    flags.append({"code": marker["validation"]["errors"][0], "marker_code": m.marker_code})
                markers.append(marker)
            panels.append({**panel.model_dump(exclude={"markers"}), "collection_date": panel.collection_date or result.collection_date,
                           "markers": markers})
        # No trusted patient name registry is available: never fabricate a match.
        flags.append({"code": "identity_unverified"})
        now = datetime.utcnow()
        state = ("unreadable" if result.document_type == "unreadable" else
                 "not_applicable" if result.document_type == "other" else "awaiting_confirmation")
        if state == "awaiting_confirmation" and not seen:
            raise ValueError("Incomplete extraction")
        extraction = {"schema_version": "1.0", "clinical_test_id": clinical_test_id,
            "extraction_id": "cte_" + uuid.uuid4().hex, "patient_id": doc["patient_id"], "status": state,
            "document": {"document_type": result.document_type, "language": result.language,
                         "page_count": result.page_count, "collection_date": result.collection_date,
                         "report_date": result.report_date},
            "panels": panels, "flags": flags,
            "extraction_meta": {"model_id": provider.model_id, "model_version": provider.model_version,
                "prompt_version": self.prompt_version, "catalog_version": self.catalog_version,
                "extracted_at": now, "source_generation": generation, "test_only": provider.is_test},
            "confirmation": {"status": state}, "created_at": now, "updated_at": now, "superseded_at": None}
        extraction["proposal"] = copy.deepcopy({k: extraction[k] for k in ("document", "panels", "flags")})
        extraction["proposal"]["provider_output"] = copy.deepcopy(provider_output)
        db.clinical_test_extractions.insert_one(extraction)
        db.clinical_tests.update_one({"clinical_test_id": clinical_test_id, "deleted_at": None},
            {"$set": {"extraction.extraction_id": extraction["extraction_id"], "extraction.status": state, "updated_at": now}})
        return extraction

def _configured_provider():
    from app.services.gemini_provider import configured_extraction_provider
    return configured_extraction_provider()


extraction_engine = ExtractionEngine(provider=_configured_provider())
