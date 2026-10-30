"""
WELLQ — Script de Recálculo Masivo Controlado de Puntuaciones (§8.8 y §13.5).

Este script permite recalcular en masa los snapshots de puntuación de todos los
pacientes con exámenes clínicos confirmados, comparando las distribuciones antes
y después para garantizar la reproducibilidad y el control clínico de versiones.

Principios rectores (§8.8):
1. Inmutabilidad: NUNCA se sobrescriben los snapshots históricos existentes.
2. Cada recálculo genera un nuevo snapshot con trigger="recompute".
3. Modo --dry-run (por defecto): simula el recálculo y calcula la comparación estadística.
4. Modo --apply: persiste los nuevos snapshots y registra el evento de auditoría.
"""

import os
import sys
import argparse
import math
from datetime import datetime
from typing import List, Dict, Any, Optional

# Asegurar que el path incluya backend para importar app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pymongo import MongoClient
from pymongo.database import Database
from app.config import settings
from app.services.scoring import scoring_engine, SCORING_VERSION

def calculate_stats(values: List[float]) -> Dict[str, Any]:
    """Calcula estadísticas descriptivas para una lista de valores numéricos."""
    if not values:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "min": None,
            "p25": None,
            "median": None,
            "p75": None,
            "max": None,
        }

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mean = sum(sorted_vals) / n
    variance = sum((x - mean) ** 2 for x in sorted_vals) / n if n > 1 else 0.0
    std = math.sqrt(variance)

    def percentile(p: float) -> float:
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return d0 + d1

    return {
        "count": n,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "min": round(sorted_vals[0], 2),
        "p25": round(percentile(0.25), 2),
        "median": round(percentile(0.50), 2),
        "p75": round(percentile(0.75), 2),
        "max": round(sorted_vals[-1], 2),
    }

def run_bulk_recompute(
    db: Database,
    scoring_version: str = SCORING_VERSION,
    apply: bool = False,
    target_patient_id: Optional[str] = None,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ejecuta el recálculo masivo y compara distribuciones estadísticas.
    """
    # 1. Obtener pacientes candidatos
    if target_patient_id:
        patients = [target_patient_id]
    else:
        patients = db.clinical_markers.distinct(
            "patient_id",
            {"invalidated_at": None, "confirmation_level": {"$in": ["patient", "clinician"]}}
        )

    print(f"\n🚀 [RECÁLCULO CONTROLADO] Procesando {len(patients)} pacientes (versión: {scoring_version}, apply={apply})")

    before_lab_indices: List[float] = []
    after_lab_indices: List[float] = []

    before_pillars: Dict[str, List[float]] = {"cardio": [], "joint": [], "muscle": [], "bone": []}
    after_pillars: Dict[str, List[float]] = {"cardio": [], "joint": [], "muscle": [], "bone": []}

    paired_deltas: List[float] = []
    total_evaluated = 0
    recalculated_count = 0

    for pid in patients:
        total_evaluated += 1

        # Obtener snapshot vigente previo (baseline)
        baseline = db.score_snapshots.find_one(
            {"patient_id": pid},
            sort=[("computed_at", -1), ("_id", -1)]
        )

        old_lab_index = baseline.get("lab_index") if baseline else None
        if old_lab_index is not None:
            before_lab_indices.append(float(old_lab_index))

        if baseline and "pillars" in baseline:
            for pkey in ["cardio", "joint", "muscle", "bone"]:
                p_obj = baseline["pillars"].get(pkey, {})
                if p_obj.get("score") is not None:
                    before_pillars[pkey].append(float(p_obj["score"]))

        # Calcular nuevo snapshot
        new_snap = scoring_engine.compute_patient_score(
            patient_id=pid,
            db=db,
            trigger="recompute",
            scoring_version_override=scoring_version,
            persist=apply,
        )

        if new_snap:
            recalculated_count += 1
            new_lab_index = new_snap.get("lab_index")
            if new_lab_index is not None:
                after_lab_indices.append(float(new_lab_index))

            for pkey in ["cardio", "joint", "muscle", "bone"]:
                p_obj = new_snap.get("pillars", {}).get(pkey, {})
                if p_obj.get("score") is not None:
                    after_pillars[pkey].append(float(p_obj["score"]))

            if old_lab_index is not None and new_lab_index is not None:
                paired_deltas.append(round(new_lab_index - old_lab_index, 2))

    # 2. Análisis estadístico comparativo
    stats_before = calculate_stats(before_lab_indices)
    stats_after = calculate_stats(after_lab_indices)

    increased = sum(1 for d in paired_deltas if d > 0.5)
    neutral = sum(1 for d in paired_deltas if -0.5 <= d <= 0.5)
    decreased = sum(1 for d in paired_deltas if d < -0.5)
    mean_delta = round(sum(paired_deltas) / len(paired_deltas), 2) if paired_deltas else 0.0

    pillar_stats_before = {k: calculate_stats(v) for k, v in before_pillars.items()}
    pillar_stats_after = {k: calculate_stats(v) for k, v in after_pillars.items()}

    summary = {
        "execution_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scoring_version": scoring_version,
        "mode": "APPLY (Persistido)" if apply else "DRY-RUN (Simulación)",
        "patients_evaluated": total_evaluated,
        "patients_recalculated": recalculated_count,
        "lab_index_stats": {
            "before": stats_before,
            "after": stats_after,
            "deltas": {
                "mean_delta": mean_delta,
                "increased": increased,
                "neutral": neutral,
                "decreased": decreased,
                "max_increase": max(paired_deltas) if paired_deltas else 0.0,
                "max_decrease": min(paired_deltas) if paired_deltas else 0.0,
            }
        },
        "pillar_stats": {
            "before": pillar_stats_before,
            "after": pillar_stats_after,
        }
    }

    # 3. Auditoría en MongoDB si apply=True
    if apply:
        db.audit_logs.insert_one({
            "event_type": "bulk_scoring_recompute",
            "executed_at": datetime.utcnow(),
            "scoring_version": scoring_version,
            "patients_evaluated": total_evaluated,
            "patients_recalculated": recalculated_count,
            "mean_delta": mean_delta,
            "increased": increased,
            "decreased": decreased,
        })
        print("✅ Evento de auditoría registrado en audit_logs.")

    # 4. Formatear reporte en Markdown
    report_md = generate_markdown_report(summary)
    print(report_md)

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"📄 Reporte guardado exitosamente en: {output_path}")

    return summary

def generate_markdown_report(summary: Dict[str, Any]) -> str:
    """Genera un reporte legible en Markdown de la comparación de distribuciones."""
    li_b = summary["lab_index_stats"]["before"]
    li_a = summary["lab_index_stats"]["after"]
    deltas = summary["lab_index_stats"]["deltas"]

    lines = [
        "# WellQ — Reporte de Comparación de Distribución de Puntajes (§13.5)",
        f"- **Fecha:** {summary['execution_date']}",
        f"- **Modo:** {summary['mode']}",
        f"- **Versión de Scoring Evaluada:** `{summary['scoring_version']}`",
        f"- **Pacientes evaluados:** {summary['patients_evaluated']}",
        f"- **Snapshots generados:** {summary['patients_recalculated']}",
        "",
        "## 1. Distribución del Índice Global de Laboratorio (lab_index)",
        "",
        "| Métrica | Antes (Baseline) | Después (Nueva Versión) | Variación |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Pacientes con score** | {li_b['count']} | {li_a['count']} | {li_a['count'] - li_b['count']:+d} |",
        f"| **Media (μ)** | {li_b['mean']} | {li_a['mean']} | {(li_a['mean'] or 0) - (li_b['mean'] or 0):+.2f} |",
        f"| **Desv. Estándar (σ)** | {li_b['std']} | {li_a['std']} | {(li_a['std'] or 0) - (li_b['std'] or 0):+.2f} |",
        f"| **Mínimo** | {li_b['min']} | {li_a['min']} | {(li_a['min'] or 0) - (li_b['min'] or 0):+.2f} |",
        f"| **P25 (Cuartil 1)** | {li_b['p25']} | {li_a['p25']} | {(li_a['p25'] or 0) - (li_b['p25'] or 0):+.2f} |",
        f"| **Mediana (P50)** | {li_b['median']} | {li_a['median']} | {(li_a['median'] or 0) - (li_b['median'] or 0):+.2f} |",
        f"| **P75 (Cuartil 3)** | {li_b['p75']} | {li_a['p75']} | {(li_a['p75'] or 0) - (li_b['p75'] or 0):+.2f} |",
        f"| **Máximo** | {li_b['max']} | {li_a['max']} | {(li_a['max'] or 0) - (li_b['max'] or 0):+.2f} |",
        "",
        "## 2. Análisis de Desplazamiento y Deltas (Δ)",
        f"- **Variación media global (Δ):** `{deltas['mean_delta']:+.2f} pts`",
        f"- **Pacientes que subieron (> +0.5 pts):** `{deltas['increased']}`",
        f"- **Pacientes estables (±0.5 pts):** `{deltas['neutral']}`",
        f"- **Pacientes que bajaron (< -0.5 pts):** `{deltas['decreased']}`",
        f"- **Mayor aumento registrado:** `+{deltas['max_increase']:.2f} pts`",
        f"- **Mayor descenso registrado:** `{deltas['max_decrease']:.2f} pts`",
        "",
        "## 3. Desglose por Pilar de Salud",
        "",
        "| Pilar | Media Antes | Media Después | Δ Media | Pacientes Antes | Pacientes Después |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    p_b = summary["pillar_stats"]["before"]
    p_a = summary["pillar_stats"]["after"]

    for pkey, name in [("cardio", "Cardio"), ("muscle", "Músculo"), ("joint", "Articulación"), ("bone", "Hueso")]:
        mb = p_b[pkey]["mean"] or 0.0
        ma = p_a[pkey]["mean"] or 0.0
        cb = p_b[pkey]["count"]
        ca = p_a[pkey]["count"]
        diff = ma - mb
        lines.append(f"| **{name}** | {mb:.2f} | {ma:.2f} | {diff:+.2f} | {cb} | {ca} |")

    lines.extend([
        "",
        "---",
        "> **Garantía de Auditoría (§8.8):** Cada cálculo preserva todos los snapshots anteriores sin sobrescritura.",
        ""
    ])
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Recálculo Masivo Controlado de Puntuaciones WellQ")
    parser.add_argument("--version", default=SCORING_VERSION, help=f"Versión de algoritmo (def: {SCORING_VERSION})")
    parser.add_argument("--apply", action="store_true", help="Persistir los nuevos snapshots (por defecto es dry-run)")
    parser.add_argument("--patient-id", default=None, help="Recalcular un paciente individual (opcional)")
    parser.add_argument("--output", default=None, help="Ruta del archivo Markdown para exportar el informe")
    args = parser.parse_args()

    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB]

    output_file = args.output
    if not output_file:
        os.makedirs("exports", exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_file = f"exports/recompute_report_{ts}.md"

    run_bulk_recompute(
        db=db,
        scoring_version=args.version,
        apply=args.apply,
        target_patient_id=args.patient_id,
        output_path=output_file
    )

if __name__ == "__main__":
    main()
