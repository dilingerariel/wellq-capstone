"""Vertex AI Gemini adapter for explicitly approved, consented clinical PDFs.

Authentication uses Application Default Credentials (ADC); no API key or
service-account key is accepted by this adapter. Callers must still enforce
WellQ's production and institutional-approval gates before sending a document.
"""
import base64
import io
import json
from urllib.parse import quote

from app.config import settings
from app.services.catalog import catalog_service
from app.services.gemini_provider import _SCHEMA, _SYSTEM_INSTRUCTION


class VertexAIProviderError(RuntimeError):
    """Bounded safe error for logs and durable retry state."""

    def __init__(self, code: str, *, retryable: bool = False):
        self.safe_code = code
        self.retryable = retryable
        super().__init__(code)


class VertexAIProvider:
    model_id = "vertex_ai"
    is_test = False
    synthetic_only = False
    clinical_data_provider = True

    def __init__(self, project_id=None, location=None, model_id=None, timeout=None,
                 credentials_loader=None, session_factory=None):
        self.project_id = project_id or settings.VERTEX_AI_PROJECT_ID
        self.location = location or settings.VERTEX_AI_LOCATION
        self.model_version = model_id or settings.VERTEX_AI_MODEL_ID
        self._timeout = timeout or settings.GEMINI_TIMEOUT_SECONDS
        self._credentials_loader = credentials_loader
        self._session_factory = session_factory

    def _session(self):
        try:
            if self._credentials_loader:
                credentials = self._credentials_loader()
            else:
                import google.auth
                credentials, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"])
            if self._session_factory:
                return self._session_factory(credentials)
            from google.auth.transport.requests import AuthorizedSession
            return AuthorizedSession(credentials)
        except Exception:
            raise VertexAIProviderError("AI_AUTH_MISSING") from None

    def extract(self, data: bytes, mime_type: str) -> dict:
        if not all((self.project_id, self.location, self.model_version)):
            raise VertexAIProviderError("AI_CONFIGURATION_MISSING")
        if mime_type not in {"application/pdf", "image/jpeg", "image/png"}:
            raise VertexAIProviderError("AI_UNSUPPORTED_FORMAT")

        markers = [{"marker_code": item["marker_code"], "name": item["name"],
                    "panel_code": item["panel_code"]}
                   for item in catalog_service.list_catalog()]
        prompt = (
            "Extract the visible document fields and numeric/qualitative results. "
            "Candidate catalog markers (code, printed name, panel): "
            + json.dumps(markers, ensure_ascii=False, separators=(",", ":"))
        )
        body = {
            "systemInstruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": mime_type,
                                "data": base64.b64encode(data).decode("ascii")}},
            ]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": _SCHEMA,
                "maxOutputTokens": 8192,
            },
        }
        location_host = ("aiplatform.googleapis.com" if self.location == "global"
                         else f"{quote(self.location, safe='')}-aiplatform.googleapis.com")
        endpoint = (
            f"https://{location_host}/v1/projects/{quote(self.project_id, safe='')}/"
            f"locations/{quote(self.location, safe='')}/publishers/google/"
            f"models/{quote(self.model_version, safe='')}:generateContent"
        )
        session = self._session()
        try:
            response = session.post(endpoint, json=body, timeout=self._timeout)
            if response.status_code >= 400:
                code = response.status_code
                if code == 429:
                    raise VertexAIProviderError("AI_RATE_LIMITED", retryable=True)
                if code == 408 or code >= 500:
                    raise VertexAIProviderError("AI_PROVIDER_UNAVAILABLE", retryable=True)
                if code in (401, 403):
                    raise VertexAIProviderError("AI_AUTH_REJECTED")
                if code == 404:
                    raise VertexAIProviderError("AI_MODEL_NOT_FOUND")
                raise VertexAIProviderError("AI_REQUEST_REJECTED")
            response_data = response.json()
        except VertexAIProviderError:
            raise
        except Exception as exc:
            # ADC refresh/network errors and transport errors are not persisted verbatim.
            error_name = type(exc).__name__
            if error_name in {"RefreshError", "DefaultCredentialsError", "TransportError"}:
                raise VertexAIProviderError("AI_AUTH_MISSING") from None
            raise VertexAIProviderError("AI_PROVIDER_UNAVAILABLE", retryable=True) from None
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

        try:
            parts = response_data["candidates"][0]["content"]["parts"]
            output_text = "".join(part.get("text", "") for part in parts)
            if not output_text:
                raise ValueError()
            output = json.loads(output_text)
            if mime_type == "application/pdf":
                from pypdf import PdfReader
                output["page_count"] = len(PdfReader(io.BytesIO(data), strict=True).pages)
            else:
                output["page_count"] = 1
            return output
        except (KeyError, IndexError, TypeError, ValueError):
            raise VertexAIProviderError("AI_RESPONSE_INVALID") from None
