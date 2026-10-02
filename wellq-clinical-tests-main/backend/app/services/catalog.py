import logging
from typing import Optional, Dict, Any, List
from pymongo.database import Database

logger = logging.getLogger(__name__)

# Catálogo canónico inicial de marcadores para WellQ v1.0
INITIAL_MARKER_CATALOG = [
    {
        "marker_code": "cholesterol_total",
        "name": "Colesterol Total",
        "panel_code": "lipid_profile",
        "specimen": "blood",
        "canonical_unit": "mg/dL",
        "supported_units": ["mg/dL", "mmol/L"],
        "unit_conversions": {"mg/dL": 1.0, "mmol/L": 38.67},
        "plausible_range": {"min": 50.0, "max": 700.0},
        "default_reference": {"low": 0.0, "high": 200.0},
        "pillars": ["cardio"],
        "directionality": "lower_better",
        "optimal_range": {"low": 0.0, "high": 180.0},
        "critical_range": {"low": 0.0, "high": 300.0},
        "pillar_weights": {"cardio": 0.08},
    },
    {
        "marker_code": "ldl_cholesterol",
        "name": "Colesterol LDL",
        "panel_code": "lipid_profile",
        "specimen": "blood",
        "canonical_unit": "mg/dL",
        "supported_units": ["mg/dL", "mmol/L"],
        "unit_conversions": {"mg/dL": 1.0, "mmol/L": 38.67},
        "plausible_range": {"min": 20.0, "max": 500.0},
        "default_reference": {"low": 0.0, "high": 130.0},
        "pillars": ["cardio"],
        "directionality": "lower_better",
        "optimal_range": {"low": 0.0, "high": 100.0},
        "critical_range": {"low": 0.0, "high": 220.0},
        "pillar_weights": {"cardio": 0.20},
    },
    {
        "marker_code": "hdl_cholesterol",
        "name": "Colesterol HDL",
        "panel_code": "lipid_profile",
        "specimen": "blood",
        "canonical_unit": "mg/dL",
        "supported_units": ["mg/dL", "mmol/L"],
        "unit_conversions": {"mg/dL": 1.0, "mmol/L": 38.67},
        "plausible_range": {"min": 10.0, "max": 150.0},
        "default_reference": {"low": 40.0, "high": 100.0},
        "pillars": ["cardio"],
        "directionality": "higher_better",
        "optimal_range": {"low": 55.0, "high": 200.0},
        "critical_range": {"low": 25.0, "high": 300.0},
        "pillar_weights": {"cardio": 0.12},
    },
    {
        "marker_code": "triglycerides",
        "name": "Triglicéridos",
        "panel_code": "lipid_profile",
        "specimen": "blood",
        "canonical_unit": "mg/dL",
        "supported_units": ["mg/dL", "mmol/L"],
        "unit_conversions": {"mg/dL": 1.0, "mmol/L": 88.57},
        "plausible_range": {"min": 20.0, "max": 2000.0},
        "default_reference": {"low": 0.0, "high": 150.0},
        "pillars": ["cardio"],
        "directionality": "lower_better",
        "optimal_range": {"low": 0.0, "high": 100.0},
        "critical_range": {"low": 0.0, "high": 400.0},
        "pillar_weights": {"cardio": 0.12},
    },
    {
        "marker_code": "glucose",
        "name": "Glucosa en Ayunas",
        "panel_code": "metabolic_panel",
        "specimen": "blood",
        "canonical_unit": "mg/dL",
        "supported_units": ["mg/dL", "mmol/L"],
        "unit_conversions": {"mg/dL": 1.0, "mmol/L": 18.0182},
        "plausible_range": {"min": 20.0, "max": 1000.0},
        "default_reference": {"low": 70.0, "high": 100.0},
        "pillars": ["cardio", "muscle"],
        "directionality": "two_sided",
        "optimal_range": {"low": 70.0, "high": 90.0},
        "critical_range": {"low": 50.0, "high": 180.0},
        "pillar_weights": {"cardio": 0.08, "muscle": 0.10},
    },
    {
        "marker_code": "creatinine",
        "name": "Creatinina Sérica",
        "panel_code": "renal_panel",
        "specimen": "blood",
        "canonical_unit": "mg/dL",
        "supported_units": ["mg/dL", "umol/L", "µmol/L"],
        "unit_conversions": {"mg/dL": 1.0, "umol/L": 0.0113, "µmol/L": 0.0113},
        "plausible_range": {"min": 0.2, "max": 25.0},
        "default_reference": {"low": 0.6, "high": 1.3},
        "pillars": ["muscle", "cardio"],
        "directionality": "two_sided",
        "optimal_range": {"low": 0.7, "high": 1.1},
        "critical_range": {"low": 0.4, "high": 2.5},
        "pillar_weights": {"muscle": 0.20, "cardio": 0.10},
    },
    {
        "marker_code": "hemoglobin",
        "name": "Hemoglobina",
        "panel_code": "complete_blood_count",
        "specimen": "blood",
        "canonical_unit": "g/dL",
        "supported_units": ["g/dL", "g/L"],
        "unit_conversions": {"g/dL": 1.0, "g/L": 0.1},
        "plausible_range": {"min": 3.0, "max": 25.0},
        "default_reference": {"low": 12.0, "high": 17.5},
        "pillars": ["cardio", "muscle"],
        "directionality": "two_sided",
        "optimal_range": {"low": 13.0, "high": 16.5},
        "critical_range": {"low": 8.0, "high": 20.0},
        "pillar_weights": {"muscle": 0.15, "cardio": 0.10},
    },
    {
        "marker_code": "vitamin_d",
        "name": "Vitamina D (25-OH)",
        "panel_code": "bone_panel",
        "specimen": "blood",
        "canonical_unit": "ng/mL",
        "supported_units": ["ng/mL", "nmol/L"],
        "unit_conversions": {"ng/mL": 1.0, "nmol/L": 0.4006},
        "plausible_range": {"min": 3.0, "max": 200.0},
        "default_reference": {"low": 30.0, "high": 100.0},
        "pillars": ["bone", "joint"],
        "directionality": "higher_better",
        "optimal_range": {"low": 40.0, "high": 60.0},
        "critical_range": {"low": 10.0, "high": 150.0},
        "pillar_weights": {"bone": 0.30, "joint": 0.15, "muscle": 0.10},
    },
    {
        "marker_code": "calcium",
        "name": "Calcio Sérico",
        "panel_code": "bone_panel",
        "specimen": "blood",
        "canonical_unit": "mg/dL",
        "supported_units": ["mg/dL", "mmol/L"],
        "unit_conversions": {"mg/dL": 1.0, "mmol/L": 4.0},
        "plausible_range": {"min": 4.0, "max": 20.0},
        "default_reference": {"low": 8.5, "high": 10.5},
        "pillars": ["bone", "joint"],
        "directionality": "two_sided",
        "optimal_range": {"low": 8.8, "high": 10.2},
        "critical_range": {"low": 7.0, "high": 12.5},
        "pillar_weights": {"bone": 0.15, "joint": 0.10},
    },
    {
        "marker_code": "crp_high_sensitivity",
        "name": "Proteína C Reactiva Ultrasensible (hs-CRP)",
        "panel_code": "inflammation_panel",
        "specimen": "blood",
        "canonical_unit": "mg/L",
        "supported_units": ["mg/L", "mg/dL"],
        "unit_conversions": {"mg/L": 1.0, "mg/dL": 10.0},
        "plausible_range": {"min": 0.05, "max": 300.0},
        "default_reference": {"low": 0.0, "high": 3.0},
        "pillars": ["cardio", "joint"],
        "directionality": "lower_better",
        "optimal_range": {"low": 0.0, "high": 1.0},
        "critical_range": {"low": 0.0, "high": 10.0},
        "pillar_weights": {"joint": 0.30, "cardio": 0.10},
    },
]

PILLAR_THEORETICAL_WEIGHTS = {
    "bone": 1.0,
    "muscle": 1.0,
    "joint": 1.0,
    "cardio": 1.0,
}

class CatalogService:
    def __init__(self):
        self.catalog_by_code: Dict[str, dict] = {item["marker_code"]: item for item in INITIAL_MARKER_CATALOG}

    def seed_catalog(self, db: Database):
        """Poblar/actualizar el catálogo en MongoDB con configuración completa"""
        try:
            for item in INITIAL_MARKER_CATALOG:
                db.marker_catalog.update_one(
                    {"marker_code": item["marker_code"]},
                    {"$set": item},
                    upsert=True
                )
            logger.info(f"✅ Catálogo de marcadores inicializado/sincronizado con {len(INITIAL_MARKER_CATALOG)} registros.")
        except Exception as e:
            logger.warning(f"Aviso al sembrar catálogo de marcadores: {e}")

    def list_catalog(self, db: Optional[Database] = None) -> List[dict]:
        if db is not None:
            try:
                items = list(db.marker_catalog.find({}, {"_id": 0}))
                if items:
                    return items
            except Exception:
                pass
        return list(self.catalog_by_code.values())

    def get_marker(self, marker_code: str, db: Optional[Database] = None) -> Optional[dict]:
        if db is not None:
            try:
                found = db.marker_catalog.find_one({"marker_code": marker_code}, {"_id": 0})
                if found:
                    return found
            except Exception:
                pass
        return self.catalog_by_code.get(marker_code)

    def validate_and_convert(
        self,
        marker_code: str,
        value_raw: str,
        unit_raw: str,
        db: Optional[Database] = None
    ) -> Dict[str, Any]:
        """
        Validación determinista contra el catálogo canónico:
        - Verifica existencia de marcador (422 UNKNOWN_MARKER)
        - Verifica unidad admitida (422 UNIT_NOT_SUPPORTED)
        - Valida plausibilidad fisiológica (422 VALUE_IMPLAUSIBLE)
        - Convierte a unidad canónica y calcula estatus
        """
        marker_def = self.get_marker(marker_code, db)
        if not marker_def:
            return {
                "valid": False,
                "error_code": "UNKNOWN_MARKER",
                "message": f"El marcador '{marker_code}' no existe en el catálogo canónico",
            }

        # Validar unidad
        supported = marker_def.get("supported_units", [])
        if unit_raw not in supported:
            return {
                "valid": False,
                "error_code": "UNIT_NOT_SUPPORTED",
                "message": f"La unidad '{unit_raw}' no es admitida para el marcador '{marker_code}'. Admitidas: {supported}",
            }

        # Parsear número
        try:
            # Limpiar comas por puntos si vienen de documentos en español
            val_clean = str(value_raw).replace(",", ".").strip()
            num_val = float(val_clean)
        except ValueError:
            return {
                "valid": False,
                "error_code": "VALUE_INVALID_FORMAT",
                "message": f"El valor '{value_raw}' no puede ser interpretado como número",
            }

        # Validar intervalo de plausibilidad fisiológica
        plausible = marker_def.get("plausible_range", {})
        p_min = plausible.get("min", 0.0)
        p_max = plausible.get("max", 999999.0)
        if num_val < p_min or num_val > p_max:
            return {
                "valid": False,
                "error_code": "VALUE_IMPLAUSIBLE",
                "message": f"El valor {num_val} para '{marker_code}' está fuera del rango fisiológicamente plausible ({p_min} - {p_max} {unit_raw})",
            }

        # Conversión a unidad canónica
        conv_factor = marker_def.get("unit_conversions", {}).get(unit_raw, 1.0)
        val_canonical = round(num_val * conv_factor, 2)
        unit_canonical = marker_def.get("canonical_unit", unit_raw)

        # Determinar status respecto a rango de referencia
        default_ref = marker_def.get("default_reference", {})
        low = default_ref.get("low", 0.0)
        high = default_ref.get("high", 999999.0)

        if val_canonical < low:
            status = "low"
        elif val_canonical > high:
            status = "high"
        else:
            status = "normal"

        return {
            "valid": True,
            "marker_code": marker_code,
            "raw_name": marker_def.get("name", marker_code),
            "value_raw": str(num_val),
            "unit_raw": unit_raw,
            "value_canonical": val_canonical,
            "unit_canonical": unit_canonical,
            "conversion_factor": conv_factor,
            "status": status,
            "reference": {
                "low": low,
                "high": high,
                "unit": unit_canonical,
                "source": "catalog",
            }
        }

catalog_service = CatalogService()
