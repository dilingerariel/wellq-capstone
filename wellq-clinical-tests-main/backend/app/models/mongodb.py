from datetime import datetime
from typing import Optional
from .enums import UploadStatus, TestType, ReviewStatus

class ClinicalTestDocument:
    """Esquema MongoDB para clinical_tests"""
    
    def __init__(
        self,
        clinical_test_id: str,
        patient_id: str,
        title: str,
        test_type: TestType,
        test_date: str,
        file_name: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        notes: Optional[str] = None,
        case_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
    ):
        self.clinical_test_id = clinical_test_id
        self.patient_id = patient_id
        self.title = title
        self.test_type = test_type
        self.test_date = test_date
        self.patient_notes = notes
        self.case_id = case_id
        self.appointment_id = appointment_id
        
        # File metadata
        self.file = {
            "original_name": file_name,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "gcs_object_key": None,  # Se asigna después
            "media_id": None,
        }
        
        # Upload state machine
        self.upload = {
            "upload_id": None,
            "client_upload_id": None,
            "status": UploadStatus.INITIATED,
            "validated_at": None,
            "rejection": None,  # {code, message}
        }
        
        # Review state
        self.review = {
            "status": ReviewStatus.NOT_REVIEWED,
            "reviewed_at": None,
            "reviewed_by": None,
            "private_note": None,
        }
        
        # Timestamps
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.deleted_at = None
    
    def to_dict(self):
        return {
            "clinical_test_id": self.clinical_test_id,
            "patient_id": self.patient_id,
            "title": self.title,
            "test_type": self.test_type,
            "test_date": self.test_date,
            "patient_notes": self.patient_notes,
            "case_id": self.case_id,
            "appointment_id": self.appointment_id,
            "file": self.file,
            "upload": self.upload,
            "review": self.review,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at,
        }

# Schema para MongoDB (para crear índices)
CLINICAL_TESTS_SCHEMA = {
    "bsonType": "object",
    "required": ["clinical_test_id", "patient_id", "file", "upload"],
    "properties": {
        "_id": {"bsonType": "objectId"},
        "clinical_test_id": {"bsonType": "string"},
        "patient_id": {"bsonType": "string"},
        "title": {"bsonType": "string"},
        "test_type": {"bsonType": "string"},
        "test_date": {"bsonType": "string"},
        "patient_notes": {"bsonType": ["string", "null"]},
        "case_id": {"bsonType": ["string", "null"]},
        "appointment_id": {"bsonType": ["string", "null"]},
        "file": {
            "bsonType": "object",
            "properties": {
                "original_name": {"bsonType": "string"},
                "mime_type": {"bsonType": "string"},
                "size_bytes": {"bsonType": "int"},
                "sha256": {"bsonType": "string"},
                "gcs_object_key": {"bsonType": ["string", "null"]},
                "media_id": {"bsonType": ["objectId", "null"]},
            }
        },
        "upload": {
            "bsonType": "object",
            "properties": {
                "upload_id": {"bsonType": ["string", "null"]},
                "client_upload_id": {"bsonType": ["string", "null"]},
                "status": {"bsonType": "string"},
                "validated_at": {"bsonType": ["date", "null"]},
                "rejection": {"bsonType": ["object", "null"]},
            }
        },
        "review": {
            "bsonType": "object",
            "properties": {
                "status": {"bsonType": "string"},
                "reviewed_at": {"bsonType": ["date", "null"]},
                "reviewed_by": {"bsonType": ["string", "null"]},
                "private_note": {"bsonType": ["string", "null"]},
            }
        },
        "created_at": {"bsonType": "date"},
        "updated_at": {"bsonType": "date"},
        "deleted_at": {"bsonType": ["date", "null"]},
    }
}