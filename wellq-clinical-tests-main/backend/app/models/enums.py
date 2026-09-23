from enum import Enum

class UploadStatus(str, Enum):
    INITIATED = "initiated"
    OBJECT_UPLOADED = "object_uploaded"
    PROCESSING = "processing"
    READY_FOR_REVIEW = "ready_for_review"
    REJECTED = "rejected"
    FAILED = "failed"
    DELETED = "deleted"

class TestType(str, Enum):
    BLOOD_TEST = "blood_test"
    URINE_TEST = "urine_test"
    IMAGING = "imaging"
    PATHOLOGY = "pathology"
    OTHER = "other"

class ReviewStatus(str, Enum):
    NOT_REVIEWED = "not_reviewed"
    REVIEWED = "reviewed"

class ScanStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"

class ErrorCode(str, Enum):
    INVALID_METADATA = "INVALID_METADATA"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    UPLOAD_CONFLICT = "UPLOAD_CONFLICT"
    UNPROCESSABLE = "UNPROCESSABLE"
    RATE_LIMITED = "RATE_LIMITED"
    STORAGE_UNAVAILABLE = "STORAGE_UNAVAILABLE"
    OBJECT_MISMATCH = "OBJECT_MISMATCH"
    CONTENT_INVALID = "CONTENT_INVALID"
    UPLOAD_NOT_FOUND = "UPLOAD_NOT_FOUND"
    UPLOAD_NOT_REFRESHABLE = "UPLOAD_NOT_REFRESHABLE"
    ALREADY_REVIEWED = "ALREADY_REVIEWED"
    DOCUMENT_NOT_READY = "DOCUMENT_NOT_READY"
    NO_PATIENT_ACCESS = "NO_PATIENT_ACCESS"
    ASSOCIATION_NOT_OWNED = "ASSOCIATION_NOT_OWNED"
    RETENTION_BLOCKED = "RETENTION_BLOCKED"