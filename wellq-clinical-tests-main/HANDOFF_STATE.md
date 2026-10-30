# WELLQ — MÓDULO EXÁMENES MÉDICOS
## Documento de Traspaso de Estado y Contexto (Handoff Prompt)

> **Fecha de corte:** Octubre de 2026  
> **Versión alcanzada:** **Componentes A, B, C, D, E y F COMPLETADOS AL 100%** (20 endpoints funcionales, testeados con Pytest y persistidos en MongoDB).  
> **Base Path:** `/api/v1`  
> **Documento Rector:** `Documento_Maestro_Proyecto_Examenes_Medicos_WellQ.docx`  
> **Procedimiento de Recálculo Controlado (§13.5 y §8.8):** `backend/docs/PROCEDIMIENTO_RECALCULO_CONTROLADO.md`

---

### 1. Resumen de Estado del Proyecto (Tabla de Componentes)

| Letra | Componente | Estado actual | Qué incluye |
| :---: | :--- | :---: | :--- |
| **A** | **API de carga** | ✅ **100% COMPLETADA** | Endpoints #1 al #11: subida asíncrona, idempotencia, URLs firmadas V4, estado, listado, detalle, edición (bloqueada tras revisión), soft-delete, descarga y revisión médica. |
| **B** | **Motor de extracción** | ✅ **100% COMPLETADA** | Pipeline de extracción LLM multimodal directo (`app/services/extractor.py`) con confianzas por campo, integrado a tareas en background. |
| **C** | **Esquema JSON canónico** | ✅ **100% COMPLETADA** | Catálogo canónico de marcadores (`app/services/catalog.py`), colecciones `clinical_test_extractions`, `clinical_markers` (desnormalizada) y `marker_catalog`. Índices optimizados. |
| **D** | **Confirmación y validación** | ✅ **100% COMPLETADA** | Endpoints #12 al #16: lectura de propuesta con confianzas, confirmación/edición por el paciente, reprocesamiento, validación clínica médica y catálogo público. |
| **E** | **Motor de puntuación (Scoring)** | ✅ **100% COMPLETADA** | Subscore 0–100 por marcador (función cuadrática acotada), agregación ponderada por los 4 pilares de WellQ (Cardio, Músculo, Articulación, Hueso), penalizaciones por flags críticas/altas, colección `score_snapshots` inmutable (Endpoint #18) y herramienta CLI de recálculo masivo controlado con reporte de distribución (§8.8 y §13.5). |
| **F** | **Reportería (Portal clínico)** | ✅ **100% COMPLETADA** | Endpoints #17 (series longitudinales), #19 (payload estructurado del reporte de laboratorio) y #20 (exportación a PDF con ReportLab firmado y subido a almacenamiento privado). Control estricto de relación asistencial médico-paciente. |
| **G** | **App del paciente** | ⏳ **PENDIENTE (SIGUIENTE PASO)** | Desarrollo en Flutter + SQLite (Drift) para consumo de API y sincronización offline-first. |

---

### 2. Catálogo de los 20 Endpoints Operativos

| # | Método | Ruta | Audiencia | Comp. | Descripción y Reglas Críticas |
|---|---|---|---|:---:|---|
| **1** | `POST` | `/clinical-tests/uploads/initiate` | Paciente | A | Infiere `patient_id` de JWT, valida lista blanca MIME y máx 20MB. Idempotencia `client_upload_id` + `sha256`. Genera URL firmada V4 de subida (PUT). |
| **2** | `POST` | `/clinical-tests/uploads/{id}/refresh-url` | Paciente | A | Renueva URL expirada sin duplicar registro. Límite 10 refrescos. |
| **3** | `POST` | `/clinical-tests/uploads/{id}/complete` | Paciente | A / B | Valida checksum y tamaño. Pasa a `processing`. Dispara en background escaneo de seguridad y motor de extracción (Comp B). `local_file_can_be_deleted = false`. |
| **4** | `GET` | `/clinical-tests/uploads/{id}/status` | Paciente | A | Polling de estado. `local_file_can_be_deleted = true` **únicamente** en `ready_for_review`. |
| **5** | `GET` | `/clinical-tests` | Paciente | A | Listado de exámenes con filtros (`status`, `test_type`) y paginación por cursor opaco (`limit` máx 100). |
| **6** | `GET` | `/clinical-tests/{id}` | Paciente / Clínico | A | Detalle del examen con validación estricta de propiedad/acceso asistencial. |
| **7** | `PATCH` | `/clinical-tests/{id}` | Paciente | A | Edición de metadatos. **Falla con 409 ALREADY_REVIEWED** si ya fue revisado por el clínico. |
| **8** | `DELETE` | `/clinical-tests/{id}` | Paciente | A | Soft delete (`deleted_at = now`). |
| **9** | `POST` | `/clinical-tests/{id}/download-url` | Paciente / Clínico | A | Genera URL firmada V4 de descarga privada (5 min). |
| **10** | `GET` | `/patients/{id}/clinical-tests` | Clínico | A | Listado de exámenes de un paciente asignado con verificación asistencial. |
| **11** | `PATCH` | `/clinical-tests/{id}/review` | Clínico | A | Registro de revisión clínica (`reviewed_by`, `reviewed_at` y nota privada). |
| **12** | `GET` | `/clinical-tests/{id}/extraction` | Paciente / Clínico | D | Devuelve la extracción vigente con confianzas por campo. |
| **13** | `PATCH` | `/clinical-tests/{id}/extraction` | Paciente | D | Confirmar/corregir propuesta. Valida catálogo canónico. Inserta marcadores confirmados en `clinical_markers` y dispara cálculo de `score_snapshot`. |
| **14** | `POST` | `/clinical-tests/{id}/extraction/reprocess` | Paciente | D | Reintenta extracción, archiva la anterior (`superseded_at`) e invalida marcadores previos. |
| **15** | `POST` | `/clinical-tests/{id}/extraction/validate` | Clínico | D | Validación clínica médica. Permite correcciones médicas con precedencia sobre el paciente e invalida versiones previas del marcador. |
| **16** | `GET` | `/marker-catalog` | Todos | C | Catálogo canónico de marcadores con unidades admitidas y rangos típicos. |
| **17** | `GET` | `/patients/{id}/markers` | Clínico | F | Serie longitudinal de hasta 20 marcadores con puntos, valores canónicos, deltas y referencias. |
| **18** | `GET` | `/patients/{id}/lab-score` | Clínico | E | Consulta de puntaje vigente e histórico inmutable (`?history=true`). Motivo explicativo si no hay score disponible. |
| **19** | `GET` | `/patients/{id}/lab-report` | Clínico | F | Payload completo del reporte (cabecera, score, flags, paneles, longitudinal, trazabilidad y acciones). Soporta modo examen y modo acumulado por ventana temporal. |
| **20** | `POST` | `/patients/{id}/lab-report/export` | Clínico | F | Exportación idempotente del reporte a PDF con ReportLab. Almacenamiento en prefijo privado, URL firmada y evento en `audit_events`. |

---

### 3. Recálculo Controlado de Puntuaciones (§8.8 y §13.5)

Para dar cumplimiento estricto a las secciones 8.8 e incisos de control de versiones del Documento Maestro:
* **Script de Recálculo:** `backend/scripts/recompute_scoring.py`
  - Permite ejecutar en modo `--dry-run` (por defecto) o `--apply`.
  - Compara distribuciones estadísticas poblacionales antes vs después: media, desviación estándar, percentiles (min, P25, P50, P75, max), desplazamiento promedio (delta) y desglose por pilar de salud.
  - Guarda reportes comparativos en formato Markdown (`--output`).
  - En modo `--apply`, registra un evento de auditoría en la colección `audit_logs` y genera nuevos snapshots inmutables (`trigger: "recompute"`).
* **Procedimiento Operativo Estándar:** `backend/docs/PROCEDIMIENTO_RECALCULO_CONTROLADO.md`
  - Guía oficial para DevOps y Dirección Médica que describe el flujo de simulación, aprobación clínica y aplicación.
* **Pruebas Automatizadas:** `backend/tests/test_recompute_batch.py`
  - Valida la exactitud matemática de las funciones de distribución.
  - Valida que `--dry-run` no persista cambios y que `--apply` preserve todos los snapshots históricos.

---

### 4. Base de Datos MongoDB (`wellq_clinical`)

Colecciones configuradas e indexadas:
1. `clinical_tests`: Documento principal de exámenes (con subdocumentos `file`, `upload`, `review` y `extraction`).
2. `clinical_test_extractions`: Un documento por intento de extracción del LLM (propuesta inmutable, confianzas, versiones de modelo y prompt).
3. `clinical_markers`: Colección desnormalizada. Una fila por marcador confirmado, con `value_canonical`, `unit_canonical`, `status`, `subscore` y `confirmation_level`.
4. `marker_catalog`: Catálogo sembrado automáticamente con los marcadores clave de WellQ y rangos óptimos.
5. `score_snapshots`: Histórico inmutable de puntajes por paciente con pilares, lab_index, flags y trazabilidad.
6. `patient_access`: Relaciones asistenciales y asignaciones paciente-médico.
7. `audit_events` / `audit_logs`: Eventos de auditoría clínica (accesos denegados, exportaciones PDF, recálculos masivos de scoring).
8. `lab_report_exports`: Registro idempotente de archivos PDF generados para descarga.

---

### 5. Batería de Pruebas Automatizadas (Pytest)

Las 16 suites corren contra el backend en Docker (`wellq-api`) y pasan al 100%:
* `tests/test_clinician_access.py`
* `tests/test_clinician_correction.py`
* `tests/test_clinician_validation.py`
* `tests/test_extraction_flow.py`
* `tests/test_extraction_proposal.py`
* `tests/test_extraction_rules.py`
* `tests/test_full_lifecycle.py`
* `tests/test_lab_report_export.py`
* `tests/test_lab_report_payload.py`
* `tests/test_lab_score_endpoint.py`
* `tests/test_marker_catalog.py`
* `tests/test_marker_series.py`
* `tests/test_pdf_structure.py`
* `tests/test_recompute_batch.py`
* `tests/test_scoring_reproducibility.py`
* `tests/test_upload_flow.py`

**Comando de verificación:**
```powershell
docker exec -e WELLQ_ALLOW_ANY_DB=1 -e WELLQ_TEST_DB=wellq_clinical -e WELLQ_TEST_MONGO_URI=mongodb://root:password@mongodb:27017/?authSource=admin wellq-api pytest -v tests/
# Resultado: 209 passed in 61.69s [100%]
```

---

### 6. PROMPT LISTO PARA OTRA IA / SIGUIENTE FASE:

```text
Actúa como desarrollador senior backend y móvil. Estamos desarrollando el módulo de Exámenes Médicos para la plataforma WellQ, siguiendo las especificaciones del archivo "Documento_Maestro_Proyecto_Examenes_Medicos_WellQ.docx".

ESTADO ACTUAL DEL PROYECTO:
1. Componentes A, B, C, D, E y F COMPLETADOS AL 100%:
   - 20 endpoints operativos en /api/v1 (Carga, Extracción, Confirmación, Validación Médica, Catálogo, Series Longitudinales, Scoring, Reporte de Laboratorio y Exportación PDF).
   - Base de datos MongoDB en Docker (puerto 27017, db wellq_clinical) completamente indexada y con inmutabilidad de snapshots (§8.8).
   - Herramienta de recálculo masivo controlado de puntuaciones (§13.5) con script CLI (backend/scripts/recompute_scoring.py), SOP clínico (backend/docs/PROCEDIMIENTO_RECALCULO_CONTROLADO.md) y test suite.
   - Batería de pruebas en backend/tests/ pasa 100% (16 suites, 209 tests passed).

SIGUIENTE PASO A DESARROLLAR:
Componente G: Aplicación Móvil del Paciente (Flutter + SQLite / Drift)
- Flujo de subida y cámara para captura de exámenes médicos.
- Pantalla de revisión y confirmación interactiva de marcadores propuestos.
- Consulta de historial de exámenes y visualización de valores confirmados.
- Sincronización offline-first con SQLite/Drift.

Continúa guiando el desarrollo a partir del Componente G manteniendo la consistencia con las APIs existentes de FastAPI.
```
