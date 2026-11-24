import json

import pytest

from app.config import settings
from app.services import vertex_ai_provider as vertex


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.request = None

    def post(self, url, *, json, timeout):
        self.request = (url, json, timeout)
        return self.response


def provider(monkeypatch, session):
    monkeypatch.setattr(vertex.catalog_service, "list_catalog", lambda: [])
    return vertex.VertexAIProvider(
        project_id="wellq-project",
        location="us-central1",
        model_id="gemini-3.8-flash",
        credentials_loader=lambda: object(),
        session_factory=lambda _credentials: session,
    )


def valid_output():
    return {
        "schema_version": "1.0",
        "document_type": "blood_panel",
        "language": "es",
        "page_count": 1,
        "collection_date": None,
        "report_date": None,
        "panels": [],
    }


def test_vertex_provider_uses_adc_session_and_structured_request(monkeypatch):
    session = FakeSession(FakeResponse({"candidates": [{"content": {"parts": [
        {"text": json.dumps(valid_output())}
    ]}}]}))
    adapter = provider(monkeypatch, session)

    output = adapter.extract(b"not parsed as pdf when a mocked image is passed", "image/png")

    assert output["document_type"] == "blood_panel"
    assert adapter.clinical_data_provider is True
    url, body, timeout = session.request
    assert "projects/wellq-project/locations/us-central1" in url
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "image/png"
    assert timeout == settings.GEMINI_TIMEOUT_SECONDS


@pytest.mark.parametrize("status,code,retryable", [
    (401, "AI_AUTH_REJECTED", False),
    (403, "AI_AUTH_REJECTED", False),
    (404, "AI_MODEL_NOT_FOUND", False),
    (429, "AI_RATE_LIMITED", True),
    (503, "AI_PROVIDER_UNAVAILABLE", True),
])
def test_vertex_provider_maps_http_errors_without_retaining_response(monkeypatch, status, code, retryable):
    class ErrorResponse:
        status_code = status
        text = "sensitive provider response must not leak"

    adapter = provider(monkeypatch, FakeSession(ErrorResponse()))
    with pytest.raises(vertex.VertexAIProviderError) as raised:
        adapter.extract(b"image", "image/png")

    assert raised.value.safe_code == code
    assert raised.value.retryable is retryable
    assert str(raised.value) == code


def test_vertex_provider_fails_closed_without_adc(monkeypatch):
    adapter = vertex.VertexAIProvider(
        project_id="wellq-project", location="us-central1",
        credentials_loader=lambda: (_ for _ in ()).throw(RuntimeError("no ADC")),
    )
    with pytest.raises(vertex.VertexAIProviderError) as raised:
        adapter.extract(b"image", "image/png")
    assert raised.value.safe_code == "AI_AUTH_MISSING"


def test_production_configuration_requires_clamav_and_vertex_approvals(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "JWT_ISSUER", "https://identity.test.invalid")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "wellq-test")
    monkeypatch.setattr(settings, "JWT_JWKS_URL", "https://identity.test.invalid/.well-known/jwks.json")
    monkeypatch.setattr(settings, "CLAMAV_HOST", None)
    monkeypatch.setattr(settings, "AI_PROVIDER", "vertex_ai")
    monkeypatch.setattr(settings, "VERTEX_AI_PROJECT_ID", "wellq-project")
    monkeypatch.setattr(settings, "VERTEX_AI_LOCATION", "us-central1")
    monkeypatch.setattr(settings, "VERTEX_AI_MODEL_ID", "gemini-3.8-flash")
    monkeypatch.setattr(settings, "AI_PROVIDER_APPROVED", True)
    monkeypatch.setattr(settings, "AI_CLINICAL_DATA_APPROVED", True)
    with pytest.raises(RuntimeError, match="ClamAV"):
        settings.validate_clinical_services()

    monkeypatch.setattr(settings, "CLAMAV_HOST", "clamav")
    monkeypatch.setattr(settings, "AI_CLINICAL_DATA_APPROVED", False)
    with pytest.raises(RuntimeError, match="explicit approvals"):
        settings.validate_clinical_services()
