"""Request-scoped scheduling for the fixed synthetic Gemini extraction demo.

Vercel has no persistent worker process, so queue writes must be followed by a
bounded background invocation. Production clinical documents are never eligible.
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def schedule_synthetic_demo_extraction(background_tasks, doc) -> bool:
    """Schedule one durable queue claim if this document passes every demo gate."""
    if not doc or not doc.get("ai_consent"):
        return False
    if (doc.get("extraction_job") or {}).get("status") != "pending":
        return False

    from app.routes.demo import SYNTHETIC_PDF_SHA256, SYNTHETIC_PDF_SIZE

    file = doc.get("file") or {}
    upload = doc.get("upload") or {}
    if (settings.ENVIRONMENT == "production"
            or not settings.DEMO_AUTH_ENABLED
            or not settings.DEMO_MONGO_STORAGE_ENABLED
            or file.get("sha256") != SYNTHETIC_PDF_SHA256
            or file.get("size_bytes") != SYNTHETIC_PDF_SIZE
            or not file.get("verified_at")
            or upload.get("status") != "ready_for_review"):
        logger.info("WellQ extraction scheduling skipped; synthetic demo eligibility failed")
        return False

    checks = {
        "provider_approved": settings.AI_PROVIDER_APPROVED,
        "gemini_provider": settings.AI_PROVIDER == "gemini_api",
        "api_key_present": bool(settings.GEMINI_API_KEY),
    }
    missing = [name for name, passed in checks.items() if not passed]
    if missing:
        logger.warning("WellQ synthetic extraction not scheduled; missing checks=%s", ",".join(missing))
        return False

    background_tasks.add_task(process_one_synthetic_demo_extraction, doc["clinical_test_id"])
    logger.info("WellQ synthetic extraction task scheduled")
    return True


def process_one_synthetic_demo_extraction(clinical_test_id: str) -> None:
    """Claim and process no more than one eligible job in this serverless call."""
    from app.database import mongodb
    from app.workers.processing import run_once

    if mongodb.db is None:
        logger.warning("WellQ synthetic extraction worker invoked without a database connection")
        return
    try:
        claimed = run_once(mongodb.db, "extraction", clinical_test_id=clinical_test_id)
        logger.info("WellQ synthetic extraction worker invoked; claimed_job=%s", bool(claimed))
    except Exception as exc:
        # Do not log provider response bodies, document data, or request details.
        logger.warning("WellQ synthetic extraction invocation failed; error_type=%s", type(exc).__name__)
