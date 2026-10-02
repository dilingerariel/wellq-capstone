from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class PillarName(str, Enum):
    BONE = "bone"
    MUSCLE = "muscle"
    JOINT = "joint"
    CARDIO = "cardio"

class ScoreConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    INSUFFICIENT = "insufficient"

class FlagSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    INFO = "info"

class PillarContribution(BaseModel):
    marker_code: str
    name: str
    value: float
    unit: str
    subscore: float
    weight: float
    clinical_test_id: Optional[str] = None
    measured_on: Optional[str] = None

class PillarScore(BaseModel):
    score: Optional[float] = None
    coverage: float
    confidence: ScoreConfidence
    status: str = "published"  # published | insufficient_data
    contributions: List[PillarContribution] = []

class ScoreFlag(BaseModel):
    code: str
    severity: FlagSeverity
    marker_code: str
    value: float
    unit: Optional[str] = None
    message: str

class ExcludedMarker(BaseModel):
    marker_code: Optional[str] = None
    raw_name: Optional[str] = None
    reason: str

class ScoreSnapshotModel(BaseModel):
    snapshot_id: str
    patient_id: str
    computed_at: str
    trigger: str  # extraction_confirmed | clinician_correction | manual_recompute
    scoring_version: str = "score-v1.0"
    catalog_version: str = "cat-2026.08"
    window: Dict[str, Any]
    lab_index: Optional[float] = None
    base_score: Optional[float] = None
    penalty_applied: float = 0.0
    pillars: Dict[str, PillarScore]
    flags: List[ScoreFlag] = []
    excluded_markers: List[ExcludedMarker] = []

class LabScoreResponse(BaseModel):
    current_snapshot: ScoreSnapshotModel
    history: Optional[List[ScoreSnapshotModel]] = None
