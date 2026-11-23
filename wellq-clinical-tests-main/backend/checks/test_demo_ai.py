from datetime import datetime

from app.config import settings
from app.routes.demo import SYNTHETIC_PDF_SHA256, SYNTHETIC_PDF_SIZE
from app.services import demo_ai


class CapturedBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, function, *args):
        self.tasks.append((function, args))


def eligible_synthetic_document():
    return {
        "clinical_test_id": "ct_synthetic_test",
        "ai_consent": True,
        "file": {
            "sha256": SYNTHETIC_PDF_SHA256,
            "size_bytes": SYNTHETIC_PDF_SIZE,
            "verified_at": datetime.utcnow(),
        },
        "upload": {"status": "ready_for_review"},
        "extraction_job": {"status": "pending"},
    }


def enable_synthetic_gemini(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "DEMO_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "DEMO_MONGO_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_PROVIDER_APPROVED", True)
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini_api")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-only-key")


def test_synthetic_extraction_schedules_only_requested_document(monkeypatch):
    enable_synthetic_gemini(monkeypatch)
    tasks = CapturedBackgroundTasks()
    monkeypatch.setattr(demo_ai, "process_one_synthetic_demo_extraction", lambda *_: None)

    assert demo_ai.schedule_synthetic_demo_extraction(tasks, eligible_synthetic_document()) is True
    assert tasks.tasks == [(demo_ai.process_one_synthetic_demo_extraction, ("ct_synthetic_test",))]


def test_synthetic_extraction_fails_closed_for_non_synthetic_document(monkeypatch):
    enable_synthetic_gemini(monkeypatch)
    tasks = CapturedBackgroundTasks()
    document = eligible_synthetic_document()
    document["file"]["sha256"] = "0" * 64

    assert demo_ai.schedule_synthetic_demo_extraction(tasks, document) is False
    assert tasks.tasks == []


def test_synthetic_extraction_fails_closed_in_production(monkeypatch):
    enable_synthetic_gemini(monkeypatch)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    tasks = CapturedBackgroundTasks()

    assert demo_ai.schedule_synthetic_demo_extraction(tasks, eligible_synthetic_document()) is False
    assert tasks.tasks == []
