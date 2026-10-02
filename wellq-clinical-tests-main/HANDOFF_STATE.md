# WELLQ — MÓDULO EXÁMENES MÉDICOS
## Documento de Traspaso de Estado y Contexto (Handoff Prompt)

> **Fecha de corte:** 2 de octubre de 2026  
> **Versión alcanzada:** **Componentes A, B, C y D COMPLETADOS AL 100%** (16 endpoints funcionales, testeados con Pytest y persistidos en MongoDB).  
> **Base Path:** `/api/v1`  
> **Documento Rector:** `Documento_Maestro_Proyecto_Examenes_Medicos_WellQ.docx` (ubicado en Descargas / proyecto).

---

### 1. Resumen de Estado del Proyecto (Tabla de Componentes)

| Letra | Componente | Estado actual | Qué incluye |
| :---: | :--- | :---: | :--- |
| **A** | **API de carga** | ✅ **100% COMPLETADA** | Endpoints #1 al #11: subida asíncrona, idempotencia, URLs firmadas V4, estado, listado, detalle, edición (bloqueada tras revisión), soft-delete, descarga y revisión médica. |
| **B** | **Motor de extracción** | ✅ **100% COMPLETADA** | Pipeline de extracción LLM multimodal directo (`app/services/extractor.py`) con confianzas por campo, integrado a tareas en background. |
| **C** | **Esquema JSON canónico** | ✅ **100% COMPLETADA** | Catálogo canónico de marcadores (`app/services/catalog.py`), colecciones `clinical_test_extractions`, `clinical_markers` (desnormalizada) y `marker_catalog`. Índices optimizados. |
| **D** | **Confirmación y validación** | ✅ **100% COMPLETADA** | Endpoints #12 al #16: lectura de propuesta con confianzas, confirmación/edición por el paciente, reprocesamiento, validación clínica y catálogo público. |
| **E** | **Motor de puntuación** | ⏳ **PENDIENTE (SIGUIENTE PASO)** | Cálculo del score 0–100 por marcador y por los 4 pilares de WellQ (Hueso, Músculo, Articulación, Cardio) + colección `score_snapshots` (Endpoint #18). |
| **F** | **Reportería (portal clínico)** | ⏳ **PENDIENTE** | Vista tabular, series longitudinales de marcadores y exportación a PDF (Endpoints #17, #19, #20). |
| **G** | **App del paciente** | ⏳ **PENDIENTE** | Desarrollo en Flutter + SQLite (Drift). |

---

### 2. Catálogo de los 16 Endpoints Operativos

| # | Método | Ruta | Audiencia | Componente | Descripción y Reglas Críticas |
|---|---|---|---|---|---|
| **1** | `POST` | `/clinical-tests/uploads/initiate` | Paciente | A | Infiere `patient_id` de JWT, valida lista blanca MIME y máx 20MB. Idempotencia `client_upload_id` + `sha256`. Genera URL firmada V4 de subida (PUT). |
| **2** | `POST` | `/clinical-tests/uploads/{id}/refresh-url` | Paciente | A | Renueva URL expirada sin duplicar registro. Límite 10 refrescos. |
| **3** | `POST` | `/clinical-tests/uploads/{id}/complete` | Paciente | A / B | Valida checksum y tamaño. Pasa a `processing`. Dispara en background escaneo de seguridad y motor de extracción (Comp B). `local_file_can_be_deleted = false`. |
| **4** | `GET` | `/clinical-tests/uploads/{id}/status` | Paciente | A | Polling de estado. `local_file_can_be_deleted = true` **únicamente** en `ready_for_review`. |
| **5** | `GET` | `/clinical-tests` | Paciente | A | Listado de exámenes con filtros (`status`, `test_type`) y paginación por cursor opaco (`limit` máx 100). |
| **6** | `GET` | `/clinical-tests/{id}` | Paciente / Clínico | A | Detalle del examen con validación estricta de propiedad/acceso. |
| **7** | `PATCH` | `/clinical-tests/{id}` | Paciente | A | Edición de metadatos. **Falla con 409 ALREADY_REVIEWED** si ya fue revisado por el clínico. |
| **8** | `DELETE` | `/clinical-tests/{id}` | Paciente | A | Soft delete (`deleted_at = now`). |
| **9** | `POST` | `/clinical-tests/{id}/download-url` | Paciente / Clínico | A | Genera URL firmada V4 de descarga privada (5 min). |
| **10** | `GET` | `/patients/{id}/clinical-tests` | Clínico | A | Listado de exámenes de un paciente asignado. |
| **11** | `PATCH` | `/clinical-tests/{id}/review` | Clínico | A | Registro de revisión clínica (`reviewed_by`, `reviewed_at` y nota privada). |
| **12** | `GET` | `/clinical-tests/{id}/extraction` | Paciente / Clínico | D | Devuelve la extracción vigente con confianzas por campo. |
| **13** | `PATCH` | `/clinical-tests/{id}/extraction` | Paciente | D | Confirmar/corregir propuesta. Valida catálogo canónico (`UNKNOWN_MARKER`, `UNIT_NOT_SUPPORTED`, `VALUE_IMPLAUSIBLE`). Inserta marcadores confirmados en `clinical_markers`. |
| **14** | `POST` | `/clinical-tests/{id}/extraction/reprocess` | Paciente | D | Reintenta la extracción, archiva la anterior (`superseded_at`) e invalida marcadores previos. |
| **15** | `POST` | `/clinical-tests/{id}/extraction/validate` | Clínico | D | Validación clínica médica. Permite correcciones médicas que tienen prioridad sobre las del paciente. |
| **16** | `GET` | `/marker-catalog` | Todos | C | Catálogo canónico de marcadores con unidades admitidas y rangos típicos. |

---

### 3. Base de Datos MongoDB (`wellq_clinical`)

Colecciones configuradas e indexadas:
1. `clinical_tests`: Documento principal de exámenes (con subdocumentos `file`, `upload`, `review` y `extraction`).
2. `clinical_test_extractions`: Un documento por intento de extracción del LLM (propuesta inmutable, confianzas, versiones de modelo y prompt).
3. `clinical_markers`: Colección desnormalizada. Una fila por marcador confirmado, con `value_canonical`, `unit_canonical`, `status` y `confirmation_level`.
4. `marker_catalog`: Catálogo sembrado automáticamente con los marcadores clave de WellQ (colesterol, glucosa, creatinina, hemoglobina, vitamina D, etc.).

---

### 4. Batería de Pruebas Automatizadas (Pytest)

Las 3 suites corren contra el backend en Docker y pasan al 100%:
* `tests/test_upload_flow.py`: Flujo de subida y estado.
* `tests/test_full_lifecycle.py`: Endpoints 5 al 11, control de acceso y soft-delete.
* `tests/test_extraction_flow.py`: Endpoints 12 al 16, validaciones del catálogo, confirmación del paciente y validación clínica.

**Comando de verificación:**
```powershell
cd backend
pytest -v tests/
# Resultado: 3 passed in 11.05s [100%]
```

---

### 5. PROMPT LISTO PARA OTRA IA (COPIAR Y PEGAR):

```text
Actúa como desarrollador senior backend en Python/FastAPI. Estamos desarrollando el módulo de Exámenes Médicos para la plataforma WellQ, siguiendo las especificaciones del archivo "Documento_Maestro_Proyecto_Examenes_Medicos_WellQ.docx".

ESTADO ACTUAL DEL PROYECTO:
1. Componentes A, B, C y D COMPLETADOS AL 100%:
   - 16 endpoints operativos en /api/v1 (desde upload e initiate hasta extracción, confirmación de paciente, reprocesamiento, validación clínica y catálogo canónico).
   - Base de datos MongoDB en Docker (puerto 27017, db wellq_clinical) con colecciones e índices listos: clinical_tests, clinical_test_extractions, clinical_markers y marker_catalog.
   - Motor de extracción LLM multimodal con visión y normalización determinista (app/services/extractor.py y app/services/catalog.py).
   - Regla de oro de confirmación humana implementada: ningún dato clínico entra al activo longitudinal (clinical_markers) sin confirmación del paciente o validación del médico.
   - Batería de pruebas en backend/tests/ pasa 100% (3 suites, 3 passed).

SIGUIENTE PASO A DESARROLLAR:
Fase 4 del Documento Maestro — Componente E: Motor de Puntuación (Scoring Engine)
- Subscore 0–100 por marcador respecto a su rango de referencia.
- Agregación ponderada por los 4 pilares de WellQ: Hueso, Músculo, Articulación y Cardio.
- Índice de laboratorio global.
- Creación de la colección score_snapshots (histórico inmutable de cálculos).
- Endpoint #18: GET /api/v1/patients/{patient_id}/lab-score (consultar puntaje vigente e histórico).

Continúa guiando el desarrollo a partir de la Fase 4 (Componente E) manteniendo los mismos estándares de arquitectura, trazabilidad y pruebas automatizadas.
```
