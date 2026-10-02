import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pymongo.database import Database

from app.services.catalog import catalog_service, PILLAR_THEORETICAL_WEIGHTS
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

    def calculate_subscore(
        self,
        marker_code: str,
        value: float,
        reference: Optional[dict] = None,
        catalog_item: Optional[dict] = None
    ) -> Tuple[float, Optional[ScoreFlag]]:
        """
        Paso 1: Cálculo del subscore (0-100) y generación de banderas clínicas.
        Implementa la función lineal por tramos del Documento Maestro (§8.2).
        """
        if not catalog_item:
            catalog_item = catalog_service.get_marker(marker_code)

        if not catalog_item:
            # Marcador no catalogado -> subscore 0
            return 0.0, None

        directionality = catalog_item.get("directionality", "two_sided")
        ref = reference or catalog_item.get("default_reference", {})
        L = float(ref.get("low", 0.0))
        H = float(ref.get("high", 100.0))
        amplitude = max(H - L, 1e-6)

        opt_range = catalog_item.get("optimal_range") or {}
        Ol = float(opt_range.get("low", L))
        Oh = float(opt_range.get("high", H))

        crit_range = catalog_item.get("critical_range") or {}
        Cl = float(crit_range.get("low", L - 0.5 * amplitude))
        Ch = float(crit_range.get("high", H + 0.5 * amplitude))

        v = float(value)
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
        if v < Cl or v > Ch:
            flag = ScoreFlag(
                code=f"{marker_code}_critical",
                severity=FlagSeverity.CRITICAL,
                marker_code=marker_code,
                value=v,
                unit=catalog_item.get("canonical_unit"),
                message=f"Valor crítico fuera de rango seguro ({v} {catalog_item.get('canonical_unit', '')})"
            )
        elif v < L or v > H:
            dev = (L - v if v < L else v - H) / amplitude
            if dev > 0.25:
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
        excluded_markers_info: Optional[List[dict]] = None
    ) -> Optional[dict]:
        """
        Paso 3 y 4: Agregación por pilar, cálculo de índice global y generación de snapshot.
        Persiste el snapshot en la colección `score_snapshots`.
        """
        # 🔍 DEBUG: Verificar trigger recibido
        logger.info(f"🔴 [SCORING] compute_patient_score INICIADO - patient_id={patient_id}, trigger={trigger}")
        
        now = datetime.utcnow()
        window_start = now - timedelta(days=int(window_months * 30.5))

        # 1. Recuperar marcadores confirmados válidos del paciente
        query = {
            "patient_id": patient_id,
            "invalidated_at": None,
            "status": {"$ne": "rejected"},
            "confirmation_level": {"$in": ["patient", "clinician"]},
        }
        raw_markers = list(db.clinical_markers.find(query).sort("measured_on", -1))
        
        # ... resto del código CON 8 ESPACIOS ...

        # Tomar la medición más reciente de cada marker_code dentro de la ventana
        latest_markers_by_code: Dict[str, dict] = {}
        for m in raw_markers:
            code = m["marker_code"]
            if code not in latest_markers_by_code:
                latest_markers_by_code[code] = m

        catalog_map = {item["marker_code"]: item for item in catalog_service.list_catalog(db)}

        # Calcular subscore actualizado y banderas para cada marcador
        active_subscores: Dict[str, dict] = {}
        active_flags: List[ScoreFlag] = []

        for code, m in latest_markers_by_code.items():
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

            # Actualizar en clinical_markers si cambió el subscore o scoring_version
            db.clinical_markers.update_one(
                {"_id": m["_id"]},
                {
                    "$set": {
                        "subscore": subscore,
                        "scoring_version": self.scoring_version,
                        "updated_at": now,
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
            "computed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "trigger": trigger,
            "scoring_version": self.scoring_version,
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
            "excluded_markers": excluded_markers_info or [],
        }

        # Guardar snapshot inmutable en MongoDB
        db.score_snapshots.insert_one(snapshot_doc)
        logger.info(f"✅ Snapshot de puntaje generado para paciente {patient_id}: id={snapshot_id}, lab_index={lab_index}")

        # Retornar documento sin _id de MongoDB para serialización directa
        snapshot_doc.pop("_id", None)
        return snapshot_doc

scoring_engine = ScoringEngine()
