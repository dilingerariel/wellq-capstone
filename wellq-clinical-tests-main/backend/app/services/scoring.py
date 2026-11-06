import logging
import uuid
import hashlib
import json
import math
import calendar
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pymongo.database import Database

from app.services.catalog import catalog_service, PILLAR_THEORETICAL_WEIGHTS
from app.services.references import effective_reference, reference_status
from app.models.scoring import (
    PillarScore, PillarContribution, ScoreFlag, FlagSeverity,
    ScoreConfidence, ExcludedMarker, ScoreSnapshotModel
)

logger = logging.getLogger(__name__)

SCORING_VERSION = "score-v1.0"
CATALOG_VERSION = "cat-2026.08"

class ScoringEngine:
    def __init__(self):
        self.scoring_version = SCORING_VERSION
        self.catalog_version = CATALOG_VERSION

    @staticmethod
    def publication_allowed():
        from app.config import settings
        return settings.CATALOG_CLINICALLY_APPROVED or settings.ENVIRONMENT == "test"

    def snapshot_publishable(self, snapshot):
        from app.config import settings
        return bool(self.publication_allowed() and snapshot
            and snapshot.get("catalog_hash") == catalog_service.content_hash()
            and snapshot.get("scoring_version") == self.scoring_version
            and (settings.ENVIRONMENT == "test" or snapshot.get("catalog_clinically_approved") is True))

    def publication_stamp(self):
        from app.config import settings
        return {"subscore_catalog_hash": catalog_service.content_hash(),
                "subscore_clinically_approved": settings.CATALOG_CLINICALLY_APPROVED}

    def published_subscore(self, marker):
        from app.config import settings
        if not self.publication_allowed():
            return None
        if settings.ENVIRONMENT != "test" and (
            marker.get("subscore_clinically_approved") is not True
            or marker.get("subscore_catalog_hash") != catalog_service.content_hash()
            or marker.get("scoring_version") != self.scoring_version):
            return None
        # Do not republish a legacy cache for a reference that cannot be scored.
        if self.exclusion_reason(marker.get("marker_code"), marker.get("reference")):
            return None
        return marker.get("subscore")

    def display_status(self, marker):
        cat = catalog_service.get_marker(marker.get("marker_code")) or {}
        ref, _ = effective_reference(cat, marker.get("reference"))
        if ref.get("source") != "document" and not self.publication_allowed():
            return "indeterminate"
        return reference_status(marker.get("value_canonical"), cat, ref)

    @staticmethod
    def scoring_parameters(catalog_item, reference=None):
        ref, error = effective_reference(catalog_item, reference)
        if error:
            return None, error
        L, H = ref.get("low"), ref.get("high")
        direction = catalog_item.get("directionality", "two_sided")
        if (direction == "two_sided" and (L is None or H is None)
            or direction == "lower_better" and H is None
            or direction == "higher_better" and L is None):
            return None, "INCOMPLETE_REFERENCE_RANGE"
        amplitude = H - L if L is not None and H is not None else None
        opt = catalog_item.get("optimal_range") or {}
        crit = catalog_item.get("critical_range") or {}
        raw = {"L": L, "H": H, "Ol": opt.get("low", L), "Oh": opt.get("high", H),
               "Cl": crit.get("low", L - .5 * amplitude if amplitude is not None else None) if L is not None else None,
               "Ch": crit.get("high", H + .5 * amplitude if amplitude is not None else None) if H is not None else None}
        try:
            params = {k: float(v) if v is not None else None for k, v in raw.items()}
        except (TypeError, ValueError, OverflowError):
            return None, "INVALID_SCORING_PARAMETERS"
        if any(v is not None and not math.isfinite(v) for v in params.values()):
            return None, "INVALID_SCORING_PARAMETERS"
        lower = [params[k] for k in ("Cl", "L", "Ol")]
        upper = [params[k] for k in ("Oh", "H", "Ch")]
        if direction in ("two_sided", "higher_better") and (
            any(v is None for v in lower) or not lower[0] < lower[1] <= lower[2]):
            return None, "INCONSISTENT_SCORING_PARAMETERS"
        if direction in ("two_sided", "lower_better") and (
            any(v is None for v in upper) or not upper[0] <= upper[1] < upper[2]):
            return None, "INCONSISTENT_SCORING_PARAMETERS"
        if direction == "two_sided" and not L <= params["Ol"] <= params["Oh"] <= H:
            return None, "INCONSISTENT_SCORING_PARAMETERS"
        if direction not in ("two_sided", "lower_better", "higher_better"):
            return None, "UNSUPPORTED_DIRECTIONALITY"
        return params, None

    def exclusion_reason(self, marker_code, reference=None):
        cat = catalog_service.get_marker(marker_code)
        return self.scoring_parameters(cat, reference)[1] if cat else "UNKNOWN_MARKER"

    def calculate_subscore(
        self,
        marker_code: str,
        value: float,
        reference: Optional[dict] = None,
        catalog_item: Optional[dict] = None
    ) -> Tuple[Optional[float], Optional[ScoreFlag]]:
        """
        Paso 1: Cálculo del subscore (0-100) y generación de banderas clínicas.
        Implementa la función lineal por tramos del Documento Maestro (§8.2).
        """
        if not catalog_item:
            catalog_item = catalog_service.get_marker(marker_code)

        if not catalog_item:
            return None, None

        directionality = catalog_item.get("directionality", "two_sided")
        params, error = self.scoring_parameters(catalog_item, reference)
        if error:
            return None, None
        L, H, Ol, Oh, Cl, Ch = (params[k] for k in ("L", "H", "Ol", "Oh", "Cl", "Ch"))
        amplitude = H - L if L is not None and H is not None else None

        v = float(value)
        if not math.isfinite(v):
            raise ValueError("Finite scoring value required")
        s = 0.0

        if directionality == "two_sided":
            if Ol <= v <= Oh:
                s = 100.0
            elif L <= v < Ol:
                s = 100.0 - 30.0 * (Ol - v) / max(Ol - L, 1e-6)
            elif Oh < v <= H:
                s = 100.0 - 30.0 * (v - Oh) / max(H - Oh, 1e-6)
            elif Cl <= v < L:
                s = 70.0 - 70.0 * (L - v) / max(L - Cl, 1e-6)
            elif H < v <= Ch:
                s = 70.0 - 70.0 * (v - H) / max(Ch - H, 1e-6)
            else:
                s = 0.0

        elif directionality == "lower_better":
            if v <= Oh:
                s = 100.0
            elif Oh < v <= H:
                s = 100.0 - 30.0 * (v - Oh) / max(H - Oh, 1e-6)
            elif H < v <= Ch:
                s = 70.0 - 70.0 * (v - H) / max(Ch - H, 1e-6)
            else:
                s = 0.0

        elif directionality == "higher_better":
            if v >= Ol:
                s = 100.0
            elif L <= v < Ol:
                s = 100.0 - 30.0 * (Ol - v) / max(Ol - L, 1e-6)
            elif Cl <= v < L:
                s = 70.0 - 70.0 * (L - v) / max(L - Cl, 1e-6)
            else:
                s = 0.0

        s = max(0.0, min(100.0, round(s, 1)))

        # Evaluar banderas clínicas (§8.6)
        flag: Optional[ScoreFlag] = None
        if (Cl is not None and v < Cl) or (Ch is not None and v > Ch):
            flag = ScoreFlag(
                code=f"{marker_code}_critical",
                severity=FlagSeverity.CRITICAL,
                marker_code=marker_code,
                value=v,
                unit=catalog_item.get("canonical_unit"),
                message=f"Valor crítico fuera de rango seguro ({v} {catalog_item.get('canonical_unit', '')})"
            )
        elif (L is not None and v < L) or (H is not None and v > H):
            dev = ((L - v if L is not None and v < L else v - H) / amplitude
                   if amplitude is not None else None)
            if dev is not None and dev > 0.25:
                flag = ScoreFlag(
                    code=f"{marker_code}_high_deviation",
                    severity=FlagSeverity.HIGH,
                    marker_code=marker_code,
                    value=v,
                    unit=catalog_item.get("canonical_unit"),
                    message=f"Desviación significativa superior al 25% ({v} {catalog_item.get('canonical_unit', '')})"
                )
            else:
                flag = ScoreFlag(
                    code=f"{marker_code}_out_of_range",
                    severity=FlagSeverity.INFO,
                    marker_code=marker_code,
                    value=v,
                    unit=catalog_item.get("canonical_unit"),
                    message=f"Valor fuera del rango de referencia ({v} {catalog_item.get('canonical_unit', '')})"
                )

        return s, flag

    def compute_patient_score(
        self,
        patient_id: str,
        db: Database,
        trigger: str = "manual_recompute",
        window_months: int = 12,
        excluded_markers_info: Optional[List[dict]] = None,
        scoring_version_override: Optional[str] = None,
        persist: bool = True,
        as_of: Optional[datetime] = None,
    ) -> Optional[dict]:
        """
        Paso 3 y 4: Agregación por pilar, cálculo de índice global y generación de snapshot.
        Persiste el snapshot en la colección `score_snapshots` si persist=True.
        """
        from app.config import settings
        if not self.publication_allowed():
            return None  # Confirmation/deletion remain possible; clinical publication is blocked.
        active_version = scoring_version_override or self.scoring_version
        if active_version != self.scoring_version:
            raise ValueError("Unknown scoring implementation; labels do not select historical algorithms")
        now = as_of or datetime.utcnow()
        if not 1 <= window_months <= 60:
            raise ValueError("Invalid scoring window")
        month = now.year * 12 + now.month - 1 - window_months
        year, month = divmod(month, 12)
        window_start = now.replace(year=year, month=month + 1,
            day=min(now.day, calendar.monthrange(year, month + 1)[1]))
        raw_markers, excluded = self.eligible_markers(patient_id, db, window_start, now)
        latest_markers_by_code = {}
        for marker in raw_markers:
            latest_markers_by_code.setdefault(marker["marker_code"], marker)

        catalog_map = {item["marker_code"]: item for item in catalog_service.list_catalog(db)}

        # Calcular subscore actualizado y banderas para cada marcador
        active_subscores: Dict[str, dict] = {}
        active_flags: List[ScoreFlag] = []

        for code, m in sorted(latest_markers_by_code.items()):
            cat = catalog_map.get(code)
            if not cat:
                continue

            val = m.get("value_canonical")
            if val is None:
                continue

            subscore, flag = self.calculate_subscore(
                marker_code=code,
                value=float(val),
                reference=m.get("reference"),
                catalog_item=cat
            )
            if subscore is None:
                excluded.append({"marker_code": code, "reason": self.exclusion_reason(code, m.get("reference"))})
                continue

            # Actualizar en clinical_markers si persist=True
            if persist:
                db.clinical_markers.update_one(
                    {"_id": m["_id"]},
                    {
                        "$set": {
                            "subscore": subscore,
                            "scoring_version": active_version,
                            **self.publication_stamp(),
                        }
                    }
                )

            active_subscores[code] = {
                "marker_code": code,
                "name": cat.get("name", code),
                "value": float(val),
                "unit": m.get("unit_canonical") or cat.get("canonical_unit", ""),
                "subscore": subscore,
                "clinical_test_id": m.get("clinical_test_id"),
                "measured_on": str(m.get("measured_on", "")),
                "cat": cat,
            }

            if flag:
                active_flags.append(flag)

        # 2. Agregación por pilar (§8.4)
        pillars: Dict[str, PillarScore] = {}
        publishable_pillars: List[PillarScore] = []

        for pilar_key in ["cardio", "joint", "muscle", "bone"]:
            t_weight = PILLAR_THEORETICAL_WEIGHTS.get(pilar_key, 1.0)
            contributions: List[PillarContribution] = []
            a_weight_sum = 0.0
            weighted_score_sum = 0.0

            for code, data in active_subscores.items():
                p_weights = data["cat"].get("pillar_weights", {})
                w_i = p_weights.get(pilar_key)
                if w_i and w_i > 0:
                    a_weight_sum += w_i
                    weighted_score_sum += w_i * data["subscore"]
                    contributions.append(
                        PillarContribution(
                            marker_code=code,
                            name=data["name"],
                            value=data["value"],
                            unit=data["unit"],
                            subscore=data["subscore"],
                            weight=w_i,
                            clinical_test_id=data["clinical_test_id"],
                            measured_on=data["measured_on"],
                        )
                    )

            coverage = round(a_weight_sum / max(t_weight, 1e-6), 2)

            if coverage >= 0.60:
                confidence = ScoreConfidence.HIGH
                pillar_status = "published"
                p_score = round(weighted_score_sum / max(a_weight_sum, 1e-6), 1)
            elif coverage >= 0.35:
                confidence = ScoreConfidence.MEDIUM
                pillar_status = "published"
                p_score = round(weighted_score_sum / max(a_weight_sum, 1e-6), 1)
            else:
                confidence = ScoreConfidence.INSUFFICIENT
                pillar_status = "insufficient_data"
                p_score = None

            p_obj = PillarScore(
                score=p_score,
                coverage=coverage,
                confidence=confidence,
                status=pillar_status,
                contributions=contributions
            )
            pillars[pilar_key] = p_obj
            if pillar_status == "published" and p_score is not None:
                publishable_pillars.append(p_obj)

        # 3. Índice de Laboratorio Global (§8.5)
        lab_index: Optional[float] = None
        base_score: Optional[float] = None
        penalty_applied: float = 0.0

        if publishable_pillars:
            sum_weighted_pillars = sum(p.coverage * (p.score or 0.0) for p in publishable_pillars)
            sum_coverages = sum(p.coverage for p in publishable_pillars)
            base_score = round(sum_weighted_pillars / max(sum_coverages, 1e-6), 1)

            # Penalización por banderas activas
            flag_penalties = 0.0
            for f in active_flags:
                if f.severity == FlagSeverity.CRITICAL:
                    flag_penalties += 10.0
                elif f.severity == FlagSeverity.HIGH:
                    flag_penalties += 5.0

            penalty_applied = min(20.0, flag_penalties)
            lab_index = max(0.0, round(base_score - penalty_applied, 1))

        # 4. Snapshot inmutable (§8.8)
        snapshot_id = f"sc_{uuid.uuid4().hex[:16]}"
        snapshot_doc = {
            "snapshot_id": snapshot_id,
            "patient_id": patient_id,
            "computed_at": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "trigger": trigger,
            "scoring_version": active_version,
            "catalog_version": self.catalog_version,
            "window": {
                "months": window_months,
                "from": window_start.strftime("%Y-%m-%d"),
                "to": now.strftime("%Y-%m-%d"),
            },
            "lab_index": lab_index,
            "base_score": base_score,
            "penalty_applied": penalty_applied,
            "pillars": {k: v.dict() for k, v in pillars.items()},
            "flags": [f.dict() for f in active_flags],
            "excluded_markers": (excluded_markers_info or []) + excluded,
            "catalog_hash": catalog_service.content_hash(),
            "catalog_snapshot": catalog_service.list_catalog(),
            "source_digest": self.source_digest(raw_markers),
            "input_markers": [self.marker_input(m) for m in raw_markers],
            "catalog_clinically_approved": settings.CATALOG_CLINICALLY_APPROVED,
            "parameters": {"coverage_high": 0.60, "coverage_medium": 0.35,
                           "critical_penalty": 10, "high_penalty": 5, "penalty_cap": 20},
        }

        # Guardar snapshot inmutable en MongoDB si persist=True (§8.8)
        if persist:
            db.score_snapshots.insert_one(snapshot_doc)
            logger.info("Clinical operation event; details withheld")

        # Retornar documento sin _id de MongoDB para serialización directa
        snapshot_doc.pop("_id", None)
        return snapshot_doc

    @staticmethod
    def marker_input(marker):
        keys = ("marker_code", "clinical_test_id", "extraction_id", "measured_on", "value_canonical",
                "unit_canonical", "reference", "confirmation_level", "edited", "updated_at")
        return {k: marker.get(k) for k in keys}

    def source_digest(self, markers):
        data = [self.marker_input(m) for m in markers]
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

    def eligible_markers(self, patient_id, db, window_start, now):
        candidates = list(db.clinical_markers.find({"patient_id": patient_id, "invalidated_at": None,
            "status": {"$ne": "rejected"}, "confirmation_level": {"$in": ["patient", "clinician"]},
            "measured_on": {"$gte": window_start.strftime("%Y-%m-%d"), "$lte": now.strftime("%Y-%m-%d")}}
            ).sort([("measured_on", -1), ("updated_at", -1), ("_id", -1)]))
        valid, excluded = [], []
        for marker in candidates:
            parent = db.clinical_tests.find_one({"clinical_test_id": marker["clinical_test_id"],
                                                "patient_id": patient_id, "deleted_at": None})
            value = marker.get("value_canonical")
            if not parent or value is None or not math.isfinite(float(value)):
                excluded.append({"marker_code": marker["marker_code"], "reason": "deleted_or_invalid_source"})
                continue
            valid.append(marker)
        return valid, excluded

    def snapshot_current(self, snapshot, patient_id, db):
        from app.config import settings
        if not self.snapshot_publishable(snapshot):
            return False
        if not snapshot or snapshot.get("catalog_hash") != catalog_service.content_hash() or snapshot.get("window", {}).get("to") != datetime.utcnow().strftime("%Y-%m-%d"):
            return False
        try:
            start = datetime.fromisoformat(snapshot["window"]["from"])
            markers, _ = self.eligible_markers(patient_id, db, start, datetime.utcnow())
            return snapshot.get("source_digest") == self.source_digest(markers)
        except (KeyError, TypeError, ValueError):
            return False

scoring_engine = ScoringEngine()
