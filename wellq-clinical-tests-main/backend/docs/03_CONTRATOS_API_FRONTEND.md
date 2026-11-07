# Contratos API para React y Flutter

> **Vigencia tras cierre focalizado F01-F07 (2026-11-05):** Contrato vigente: export.status=ready o download_pending (replay misma clave); ready exige URL/expiracion. provider_confidence separada; subscore_blank_reason; report_date editable; fechas futuras rechazadas. 422 documenta detail objeto sin cambiar HTTP. GET extraction puede dar 409 INVALID_CLINICAL_DATE con reproceso. Ver OpenAPI regenerado y seccion de contratos de12. [Detalle y evidencia](12_CIERRE_DEFECTOS_F01_F07.md).
> El contenido anterior al cierre se conserva a continuacion como referencia historica; esta nota y el documento12 prevalecen donde difieran.

**Fecha:** 2026-11-05 (America/Santiago). **Rama:** fix/wellq-backend-hardening. **Base:** fb8746cd42fe107bbda82dd92d3a4d11d545fd3e + worktree sin commit.

## Fuente y alcance
Generado desde app.openapi() sin arrancar servicios, con anotaciones de identidad y reglas comprobadas en codigo. Las veinte operaciones clinicas mantienen /api/v1. Los esquemas de referencia estan en openapi.json; tipos nested dict del reporte son extensibles y no equivalen a un DTO totalmente cerrado.

## Autenticacion
Authorization: Bearer <token de la autoridad externa>. No hay login, registro ni refresh en este modulo. Solo RS256; clave publica, issuer y audiencia de configuracion confiable. Claims: sub, iss, aud, iat, nbf, exp, client_id, role, resource_id, permissions y capabilities, mas patient_id o clinician_id segun rol. resource_id coincide con el identificador clinico del rol; no se admiten identidades mezcladas.
El proveedor define obtencion, almacenamiento/renovacion y revocacion de sesiones. No generar JWT en cliente ni usar secretos compartidos. Los IDs de path no sustituyen autorizacion; client_id no se toma del body.

## Cabeceras y errores
Idempotency-Key obligatorio de 8 a 200 caracteres en initiate/refresh/complete/confirm/reprocess/export. Persistir claves por intencion; reintentar un conflicto con la misma clave. Content-Type application/json en cuerpos; PUT a GCS debe enviar required_headers completos.
HTTP 401: credencial no valida; 403: rol/grant/relacion/capacidad; 404: recurso no visible o score ausente; 409: estado/conflicto/replay incompatible; 422: validacion; 429: limites con Retry-After; 503: dependencia/configuracion o conflicto recuperable. Algunas rutas conservan 400/413 y 502 por contenido/storage. No inventar equivalencia entre estos estados.
Formato usual detail={code,message,...}. Validacion HTTP devuelve detail.code=INVALID_INPUT y lista errors de loc/type sin body. Errores de dominio historicos mantienen detalles especificos; el contrato no es una lista de strings uniforme.

## Estados
Subida: initiated -> processing -> ready_for_review o rejected/failed. La tarea vive en upload.job, pero no se expone un panel de operaciones. Solo status con verificacion y generacion permite borrar copia local; complete siempre devuelve false.
Extraccion separada: queued/extracting/awaiting_confirmation/confirmed/clinically_validated/discarded/rejected/unreadable/not_applicable/extraction_failed. Que exista el enum no garantiza proveedor real. Reproceso es asincrono. GET extraction devuelve 409 mientras se espera trabajo.
Consentimiento IA inicial: ai_consent=false por defecto. No confundir persistencia segura con exito del modelo ni validacion humana.
Confirmacion: confidence es objeto; enviar marker_edits y acknowledged_marker_codes reales. identity_unverified requiere document_edits.identity_confirmed=true. Notas privadas no forman parte de la confirmacion publica.

## Paginacion, limites y descargas
Listados usan limit ajustado a 1..100 y next_cursor opaco. El cursor incluye test_date/created_at/clinical_test_id para orden estable y no debe interpretarse en cliente; cursor antiguo invalido => reiniciar listado. No es una prueba de permiso.
Archivo maximo 20 MiB configurable; PDF/JPEG/PNG/HEIC. URL PUT <=15 minutos y GET <=5. Nuevo refresh tras vencimiento necesita clave nueva; repetir la misma conserva respuesta previa. Un enlace firmado es temporal y no debe persistirse ni compartirse como URL publica permanente.
Score/report/export son clinicos, nunca pantallas del paciente. Sin catalogo aprobado o snapshot vigente no hay score actual; reporte puede llevar score=null. No fabricar valores para completar UI.

## Catalogo de operaciones

| Metodo | Ruta | Acceso | Permiso | Request/response | Evidencia |
|---|---|---|---|---|---|
| POST | /api/v1/clinical-tests/uploads/initiate | Paciente | clinical:write | InitiateUploadRequest -> InitiateUploadResponse | app/routes/clinical_tests.py:44 |
| POST | /api/v1/clinical-tests/uploads/{upload_id}/refresh-url | Paciente | clinical:write | RefreshUrlRequest -> RefreshUrlResponse | app/routes/clinical_tests.py:60 |
| POST | /api/v1/clinical-tests/uploads/{upload_id}/complete | Paciente | clinical:write | CompleteUploadRequest -> CompleteUploadResponse | app/routes/clinical_tests.py:76 |
| GET | /api/v1/clinical-tests/uploads/{upload_id}/status | Paciente | clinical:read | dict/envelope -> UploadStatusResponse | app/routes/clinical_tests.py:93 |
| GET | /api/v1/clinical-tests | Paciente | clinical:read | dict/envelope -> ListClinicalTestsResponse | app/routes/clinical_tests.py:141 |
| GET | /api/v1/clinical-tests/{clinical_test_id} | JWT; propietario o clinico autorizado | clinical:read | dict/envelope -> ClinicalTestResponse | app/routes/clinical_tests.py:197 |
| PATCH | /api/v1/clinical-tests/{clinical_test_id} | Paciente | clinical:write | EditClinicalTestRequest -> ClinicalTestResponse | app/routes/clinical_tests.py:238 |
| DELETE | /api/v1/clinical-tests/{clinical_test_id} | Paciente | clinical:write | dict/envelope -> dict/envelope | app/routes/clinical_tests.py:299 |
| POST | /api/v1/clinical-tests/{clinical_test_id}/download-url | JWT; propietario o clinico autorizado | documents:download | dict/envelope -> DownloadUrlResponse | app/routes/clinical_tests.py:346 |
| GET | /api/v1/patients/{patient_id}/clinical-tests | Clinico con relacion | clinical:read | dict/envelope -> ListClinicalTestsResponse | app/routes/clinical_tests.py:415 |
| PATCH | /api/v1/clinical-tests/{clinical_test_id}/review | Clinico con relacion | clinical:review | ReviewRequest -> ClinicalTestResponse | app/routes/clinical_tests.py:473 |
| GET | /api/v1/patients/{patient_id}/lab-score | Clinico con relacion | clinical:read | dict/envelope -> LabScoreResponse | app/routes/clinical_tests.py:533 |
| GET | /api/v1/patients/{patient_id}/markers | Clinico con relacion | clinical:read | dict/envelope -> MarkerSeriesResponse | app/routes/clinical_tests.py:618 |
| GET | /api/v1/patients/{patient_id}/lab-report | Clinico con relacion | clinical:read | dict/envelope -> LabReportResponse | app/routes/clinical_tests.py:783 |
| POST | /api/v1/patients/{patient_id}/lab-report/export | Clinico con relacion | reports:export + capability report_export | LabReportExportRequest/null -> LabReportExportResponse | app/routes/clinical_tests.py:1245 |
| GET | /api/v1/marker-catalog | JWT | clinical:read | dict/envelope -> array | app/routes/extractions.py:57 |
| GET | /api/v1/clinical-tests/{clinical_test_id}/extraction | JWT; propietario o clinico autorizado | clinical:read | dict/envelope -> ExtractionResponse | app/routes/extractions.py:89 |
| PATCH | /api/v1/clinical-tests/{clinical_test_id}/extraction | Paciente | extractions:confirm | PatientConfirmationRequest -> ExtractionResponse | app/routes/extractions.py:178 |
| POST | /api/v1/clinical-tests/{clinical_test_id}/extraction/reprocess | Paciente | clinical:write | ReprocessRequest/null -> ExtractionResponse | app/routes/extractions.py:539 |
| POST | /api/v1/clinical-tests/{clinical_test_id}/extraction/validate | Clinico con relacion | extractions:validate | ClinicianValidationRequest -> ExtractionResponse | app/routes/extractions.py:636 |

## Parametros y contratos por operacion

### POST /api/v1/clinical-tests/uploads/initiate

Initiate Upload

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| idempotency-key | header | True | {"type": "string", "minLength": 8, "maxLength": 200, "title": "Idempotency-Key"} |

Body: {"required": true, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/InitiateUploadRequest"}}}}

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"201": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/InitiateUploadResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### POST /api/v1/clinical-tests/uploads/{upload_id}/refresh-url

Refresh Url

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| upload_id | path | True | {"type": "string", "title": "Upload Id"} |
| idempotency-key | header | True | {"type": "string", "minLength": 8, "maxLength": 200, "title": "Idempotency-Key"} |

Body: {"required": true, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/RefreshUrlRequest"}}}}

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/RefreshUrlResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### POST /api/v1/clinical-tests/uploads/{upload_id}/complete

Complete Upload

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| upload_id | path | True | {"type": "string", "title": "Upload Id"} |
| idempotency-key | header | True | {"type": "string", "minLength": 8, "maxLength": 200, "title": "Idempotency-Key"} |

Body: {"required": true, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CompleteUploadRequest"}}}}

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CompleteUploadResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### GET /api/v1/clinical-tests/uploads/{upload_id}/status

Get Upload Status

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| upload_id | path | True | {"type": "string", "title": "Upload Id"} |

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UploadStatusResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### GET /api/v1/clinical-tests

ENDPOINT #5: GET /api/v1/clinical-tests - Listar resultados de paciente
Paginación por cursor opaco, límite máx 100, ordenado por test_date desc, created_at desc.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| status | query | False | {"anyOf": [{"$ref": "#/components/schemas/UploadStatus"}, {"type": "null"}], "title": "Status"} |
| test_type | query | False | {"anyOf": [{"$ref": "#/components/schemas/TestType"}, {"type": "null"}], "title": "Test Type"} |
| limit | query | False | {"type": "integer", "default": 20, "title": "Limit"} |
| cursor | query | False | {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Cursor"} |

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ListClinicalTestsResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### GET /api/v1/clinical-tests/{clinical_test_id}

ENDPOINT #6: GET /api/v1/clinical-tests/{clinical_test_id} - Detalle de examen
Accesible por el paciente dueño o un clínico autorizado.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| clinical_test_id | path | True | {"type": "string", "title": "Clinical Test Id"} |

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ClinicalTestResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### PATCH /api/v1/clinical-tests/{clinical_test_id}

ENDPOINT #7: PATCH /api/v1/clinical-tests/{clinical_test_id} - Editar metadatos
REGLA CRÍTICA: Solo editable si review.status == not_reviewed.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| clinical_test_id | path | True | {"type": "string", "title": "Clinical Test Id"} |

Body: {"required": true, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/EditClinicalTestRequest"}}}}

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ClinicalTestResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### DELETE /api/v1/clinical-tests/{clinical_test_id}

ENDPOINT #8: DELETE /api/v1/clinical-tests/{clinical_test_id} - Soft delete

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| clinical_test_id | path | True | {"type": "string", "title": "Clinical Test Id"} |

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### POST /api/v1/clinical-tests/{clinical_test_id}/download-url

ENDPOINT #9: POST /api/v1/clinical-tests/{clinical_test_id}/download-url
URL firmada privada de corta duración (5 min) para descarga del archivo original.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| clinical_test_id | path | True | {"type": "string", "title": "Clinical Test Id"} |

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/DownloadUrlResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### GET /api/v1/patients/{patient_id}/clinical-tests

ENDPOINT #10: GET /api/v1/patients/{patient_id}/clinical-tests - Listar para clínico

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| patient_id | path | True | {"type": "string", "title": "Patient Id"} |
| status | query | False | {"anyOf": [{"$ref": "#/components/schemas/UploadStatus"}, {"type": "null"}], "title": "Status"} |
| test_type | query | False | {"anyOf": [{"$ref": "#/components/schemas/TestType"}, {"type": "null"}], "title": "Test Type"} |
| limit | query | False | {"type": "integer", "default": 20, "title": "Limit"} |
| cursor | query | False | {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Cursor"} |

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ListClinicalTestsResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### PATCH /api/v1/clinical-tests/{clinical_test_id}/review

ENDPOINT #11: PATCH /api/v1/clinical-tests/{clinical_test_id}/review - Revisión clínica

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| clinical_test_id | path | True | {"type": "string", "title": "Clinical Test Id"} |

Body: {"required": true, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ReviewRequest"}}}}

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ClinicalTestResponse"}}}}, "401": {"description": "Authentication required (WWW-Authenticate: Bearer)", "headers": {"WWW-Authenticate": {"schema": {"type": "string"}}}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "403": {"description": "Role, relationship, permission or capability denied", "headers": {}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "404": {"description": "Resource or publishable score unavailable", "headers": {}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "409": {"description": "State, idempotency, source or retryable write conflict", "headers": {}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "422": {"description": "Invalid request; detail is an object with code and optional errors", "headers": {}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "429": {"description": "Rate limit (Retry-After where applicable)", "headers": {"Retry-After": {"schema": {"type": "string"}}}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "503": {"description": "Dependency unavailable (Retry-After for database failures)", "headers": {"Retry-After": {"schema": {"type": "string"}}}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "428": {"description": "CLINICAL_VERSION_REQUIRED: GET current version before writing"}}

### GET /api/v1/patients/{patient_id}/lab-score

ENDPOINT #18: GET /api/v1/patients/{patient_id}/lab-score
Consultar puntaje vigente e histórico del paciente.
Solo clínico con relación verificada (§4.2, §9.5.3). El paciente NO ve el puntaje (§1.2).
Nunca calcula al vuelo: si no hay snapshot, responde 404 NO_SCORE_AVAILABLE con el motivo.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| patient_id | path | True | {"type": "string", "title": "Patient Id"} |
| history | query | False | {"type": "boolean", "default": false, "title": "History"} |

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LabScoreResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### GET /api/v1/patients/{patient_id}/markers

ENDPOINT #17: GET /api/v1/patients/{patient_id}/markers
Serie longitudinal por marcador (§9.5.2). Solo clínico con relación verificada.
Devuelve, por marcador, los puntos con valor canónico, unidad, rango aplicado,
estado, subscore y clinical_test_id de origen.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| patient_id | path | True | {"type": "string", "title": "Patient Id"} |
| marker_codes | query | True | {"type": "string", "description": "Lista separada por comas, máximo 20", "title": "Marker Codes"} |
| from | query | False | {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "From"} |
| to | query | False | {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "To"} |
| only_confirmed | query | False | {"type": "boolean", "default": true, "title": "Only Confirmed"} |

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/MarkerSeriesResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### GET /api/v1/patients/{patient_id}/lab-report

ENDPOINT #19: GET /api/v1/patients/{patient_id}/lab-report  (§9.5.1)
Payload completo del reporte, resuelto en servidor (el portal no recalcula nada).
  - con clinical_test_id  -> modo "exam": solo los marcadores de ese documento
  - sin clinical_test_id  -> modo "aggregate": último valor de cada marcador dentro de window_months
include_snapshot=true incluye el desglose de contribuciones por pilar.
include_series=true incluye series de marcadores y de pilares.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| patient_id | path | True | {"type": "string", "title": "Patient Id"} |
| clinical_test_id | query | False | {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Clinical Test Id"} |
| window_months | query | False | {"type": "integer", "maximum": 60, "minimum": 1, "default": 12, "title": "Window Months"} |
| include_series | query | False | {"type": "boolean", "default": false, "title": "Include Series"} |
| include_snapshot | query | False | {"type": "boolean", "default": false, "title": "Include Snapshot"} |

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LabReportResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### POST /api/v1/patients/{patient_id}/lab-report/export

ENDPOINT #20: POST /api/v1/patients/{patient_id}/lab-report/export  (§9.5.4)
Genera el PDF en servidor con el mismo payload del endpoint 19, lo guarda en un prefijo privado
y devuelve una URL firmada de corta duración. Idempotente por (clínico, paciente, Idempotency-Key).
Cada exportación nueva queda registrada en audit_events.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| patient_id | path | True | {"type": "string", "title": "Patient Id"} |
| idempotency-key | header | True | {"type": "string", "minLength": 8, "maxLength": 200, "title": "Idempotency-Key"} |

Body: {"content": {"application/json": {"schema": {"anyOf": [{"$ref": "#/components/schemas/LabReportExportRequest"}, {"type": "null"}], "title": "Body"}}}}

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LabReportExportResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### GET /api/v1/marker-catalog

ENDPOINT #16: GET /api/v1/marker-catalog
Catálogo de marcadores soportados, unidades canónicas y rangos.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"items": {"$ref": "#/components/schemas/CatalogItemResponse"}, "type": "array", "title": "Response Get Marker Catalog Api V1 Marker Catalog Get"}}}}}

### GET /api/v1/clinical-tests/{clinical_test_id}/extraction

ENDPOINT #12: GET /api/v1/clinical-tests/{clinical_test_id}/extraction
Devuelve la extracción vigente del examen.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| clinical_test_id | path | True | {"type": "string", "title": "Clinical Test Id"} |

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ExtractionResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### PATCH /api/v1/clinical-tests/{clinical_test_id}/extraction

ENDPOINT #13: PATCH /api/v1/clinical-tests/{clinical_test_id}/extraction
El paciente confirma, edita o descarta los valores propuestos.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| clinical_test_id | path | True | {"type": "string", "title": "Clinical Test Id"} |
| idempotency-key | header | True | {"type": "string", "minLength": 8, "maxLength": 200, "title": "Idempotency-Key"} |

Body: {"required": true, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/PatientConfirmationRequest"}}}}

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ExtractionResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### POST /api/v1/clinical-tests/{clinical_test_id}/extraction/reprocess

ENDPOINT #14: POST /api/v1/clinical-tests/{clinical_test_id}/extraction/reprocess
Vuelve a ejecutar la extracción del mismo documento con la versión vigente de prompt y catálogo.
Permitido desde extraction_failed, unreadable y discarded y, con confirmación explícita
(confirm_reprocess_confirmed=true), desde confirmed. Límite: 5 reprocesamientos por examen.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| clinical_test_id | path | True | {"type": "string", "title": "Clinical Test Id"} |
| idempotency-key | header | True | {"type": "string", "minLength": 8, "maxLength": 200, "title": "Idempotency-Key"} |

Body: {"content": {"application/json": {"schema": {"anyOf": [{"$ref": "#/components/schemas/ReprocessRequest"}, {"type": "null"}], "title": "Body"}}}}

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ExtractionResponse"}}}}, "422": {"description": "Validation Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}}

### POST /api/v1/clinical-tests/{clinical_test_id}/extraction/validate

ENDPOINT #15: POST /api/v1/clinical-tests/{clinical_test_id}/extraction/validate
Validación clínica de los valores confirmados por el paciente.

- validation_status: "validated" | "rejected" (otro valor => 422).
- Las correcciones se validan TODAS antes de escribir nada: si alguna es inválida
  (marcador que no está en el examen, duplicado, valor o unidad no válidos) responde 422
  con el detalle por marcador y no se modifica nada.
- La corrección actualiza el marcador vigente y la extracción, conserva el valor original,
  registra quién lo editó y deja un evento de auditoría.

| Parametro | Origen | Obligatorio | Esquema / restricciones |
|---|---|---|---|
| clinical_test_id | path | True | {"type": "string", "title": "Clinical Test Id"} |

Body: {"required": true, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ClinicianValidationRequest"}}}}

Respuestas declaradas (ademas de errores de dominio/autorizacion): {"200": {"description": "Successful Response", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ExtractionResponse"}}}}, "401": {"description": "Authentication required (WWW-Authenticate: Bearer)", "headers": {"WWW-Authenticate": {"schema": {"type": "string"}}}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "403": {"description": "Role, relationship, permission or capability denied", "headers": {}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "404": {"description": "Resource or publishable score unavailable", "headers": {}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "409": {"description": "State, idempotency, source or retryable write conflict", "headers": {}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "422": {"description": "Invalid request; detail is an object with code and optional errors", "headers": {}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "429": {"description": "Rate limit (Retry-After where applicable)", "headers": {"Retry-After": {"schema": {"type": "string"}}}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "503": {"description": "Dependency unavailable (Retry-After for database failures)", "headers": {"Retry-After": {"schema": {"type": "string"}}}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}, "428": {"description": "CLINICAL_VERSION_REQUIRED: GET current version before writing"}}

## DTO y validaciones exactas publicados

Cada bloque corresponde al esquema OpenAPI generado. Las restricciones de reglas adicionales del dominio se documentan en 02, 05, 06 y 07; no todas pueden expresarse mediante JSON Schema.

### CatalogItemResponse

```json
{
  "properties": {
    "catalog_version": {
      "type": "string",
      "title": "Catalog Version",
      "default": "cat-2026.08"
    },
    "clinically_validated": {
      "type": "boolean",
      "title": "Clinically Validated",
      "default": false
    },
    "marker_code": {
      "type": "string",
      "title": "Marker Code"
    },
    "name": {
      "type": "string",
      "title": "Name"
    },
    "panel_code": {
      "type": "string",
      "title": "Panel Code"
    },
    "specimen": {
      "type": "string",
      "title": "Specimen"
    },
    "canonical_unit": {
      "type": "string",
      "title": "Canonical Unit"
    },
    "supported_units": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Supported Units"
    },
    "pillars": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Pillars"
    },
    "typical_range": {
      "additionalProperties": true,
      "type": "object",
      "title": "Typical Range"
    }
  },
  "type": "object",
  "required": [
    "marker_code",
    "name",
    "panel_code",
    "specimen",
    "canonical_unit",
    "supported_units",
    "pillars",
    "typical_range"
  ],
  "title": "CatalogItemResponse"
}
```

### ClinicalTestResponse

```json
{
  "properties": {
    "clinical_version": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Clinical Version"
    },
    "clinical_test_id": {
      "type": "string",
      "title": "Clinical Test Id"
    },
    "patient_id": {
      "type": "string",
      "title": "Patient Id"
    },
    "title": {
      "type": "string",
      "title": "Title"
    },
    "test_type": {
      "$ref": "#/components/schemas/TestType"
    },
    "test_date": {
      "type": "string",
      "title": "Test Date"
    },
    "notes": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Notes"
    },
    "case_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Case Id"
    },
    "appointment_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Appointment Id"
    },
    "file": {
      "$ref": "#/components/schemas/FileInfo"
    },
    "status": {
      "$ref": "#/components/schemas/UploadStatus"
    },
    "review": {
      "$ref": "#/components/schemas/ReviewInfo"
    },
    "created_at": {
      "type": "string",
      "title": "Created At"
    },
    "updated_at": {
      "type": "string",
      "title": "Updated At"
    }
  },
  "type": "object",
  "required": [
    "clinical_test_id",
    "patient_id",
    "title",
    "test_type",
    "test_date",
    "file",
    "status",
    "review",
    "created_at",
    "updated_at"
  ],
  "title": "ClinicalTestResponse"
}
```

### ClinicianValidationRequest

```json
{
  "properties": {
    "expected_version": {
      "anyOf": [
        {
          "type": "string",
          "pattern": "^[a-f0-9]{64}$"
        },
        {
          "type": "null"
        }
      ],
      "title": "Expected Version"
    },
    "validation_status": {
      "type": "string",
      "enum": [
        "validated",
        "rejected"
      ],
      "title": "Validation Status",
      "default": "validated"
    },
    "marker_corrections": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/components/schemas/MarkerCorrection"
          },
          "type": "array",
          "maxItems": 1000
        },
        {
          "type": "null"
        }
      ],
      "title": "Marker Corrections"
    },
    "clinical_note": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Clinical Note"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "title": "ClinicianValidationRequest"
}
```

### CompleteUploadRequest

```json
{
  "properties": {
    "client_upload_id": {
      "type": "string",
      "title": "Client Upload Id"
    },
    "sha256": {
      "type": "string",
      "maxLength": 64,
      "minLength": 64,
      "title": "Sha256"
    },
    "size_bytes": {
      "type": "integer",
      "exclusiveMinimum": 0.0,
      "title": "Size Bytes"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "client_upload_id",
    "sha256",
    "size_bytes"
  ],
  "title": "CompleteUploadRequest"
}
```

### CompleteUploadResponse

```json
{
  "properties": {
    "clinical_test_id": {
      "type": "string",
      "title": "Clinical Test Id"
    },
    "upload_id": {
      "type": "string",
      "title": "Upload Id"
    },
    "status": {
      "$ref": "#/components/schemas/UploadStatus"
    },
    "local_file_can_be_deleted": {
      "type": "boolean",
      "title": "Local File Can Be Deleted"
    },
    "status_url": {
      "type": "string",
      "title": "Status Url"
    }
  },
  "type": "object",
  "required": [
    "clinical_test_id",
    "upload_id",
    "status",
    "local_file_can_be_deleted",
    "status_url"
  ],
  "title": "CompleteUploadResponse"
}
```

### ConfidenceScores

```json
{
  "properties": {
    "value": {
      "type": "number",
      "maximum": 1.0,
      "minimum": 0.0,
      "title": "Value",
      "default": 1.0
    },
    "unit": {
      "type": "number",
      "maximum": 1.0,
      "minimum": 0.0,
      "title": "Unit",
      "default": 1.0
    },
    "reference": {
      "type": "number",
      "maximum": 1.0,
      "minimum": 0.0,
      "title": "Reference",
      "default": 1.0
    },
    "name": {
      "type": "number",
      "maximum": 1.0,
      "minimum": 0.0,
      "title": "Name",
      "default": 1.0
    }
  },
  "type": "object",
  "title": "ConfidenceScores"
}
```

### DocumentEdits

```json
{
  "properties": {
    "collection_date": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Collection Date"
    },
    "document_type": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/DocumentType"
        },
        {
          "type": "null"
        }
      ]
    },
    "identity_confirmed": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "title": "Identity Confirmed"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "title": "DocumentEdits"
}
```

### DocumentMetadata

```json
{
  "properties": {
    "document_type": {
      "$ref": "#/components/schemas/DocumentType",
      "default": "blood_panel"
    },
    "description": {
      "type": "string",
      "title": "Description",
      "default": ""
    },
    "language": {
      "type": "string",
      "title": "Language",
      "default": "es"
    },
    "page_count": {
      "type": "integer",
      "title": "Page Count",
      "default": 1
    },
    "collection_date": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Collection Date"
    },
    "report_date": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Report Date"
    }
  },
  "type": "object",
  "title": "DocumentMetadata"
}
```

### DocumentType

```json
{
  "type": "string",
  "enum": [
    "blood_panel",
    "urine_panel",
    "imaging_report",
    "other",
    "unreadable"
  ],
  "title": "DocumentType"
}
```

### DownloadUrlResponse

```json
{
  "properties": {
    "url": {
      "type": "string",
      "title": "Url"
    },
    "expires_at": {
      "type": "string",
      "title": "Expires At"
    },
    "file_name": {
      "type": "string",
      "title": "File Name"
    }
  },
  "type": "object",
  "required": [
    "url",
    "expires_at",
    "file_name"
  ],
  "title": "DownloadUrlResponse"
}
```

### EditClinicalTestRequest

```json
{
  "properties": {
    "title": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 200,
          "minLength": 1
        },
        {
          "type": "null"
        }
      ],
      "title": "Title"
    },
    "test_type": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/TestType"
        },
        {
          "type": "null"
        }
      ]
    },
    "test_date": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Test Date"
    },
    "notes": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 2000
        },
        {
          "type": "null"
        }
      ],
      "title": "Notes"
    },
    "case_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Case Id"
    },
    "appointment_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Appointment Id"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "title": "EditClinicalTestRequest"
}
```

### ExcludedMarker

```json
{
  "properties": {
    "marker_code": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Marker Code"
    },
    "raw_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Raw Name"
    },
    "reason": {
      "type": "string",
      "title": "Reason"
    }
  },
  "type": "object",
  "required": [
    "reason"
  ],
  "title": "ExcludedMarker"
}
```

### ExtractionResponse

```json
{
  "properties": {
    "clinical_version": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Clinical Version"
    },
    "schema_version": {
      "type": "string",
      "title": "Schema Version",
      "default": "1.0"
    },
    "clinical_test_id": {
      "type": "string",
      "title": "Clinical Test Id"
    },
    "extraction_id": {
      "type": "string",
      "title": "Extraction Id"
    },
    "status": {
      "$ref": "#/components/schemas/ExtractionStatus"
    },
    "document": {
      "$ref": "#/components/schemas/DocumentMetadata"
    },
    "panels": {
      "items": {
        "$ref": "#/components/schemas/PanelItem"
      },
      "type": "array",
      "title": "Panels",
      "default": []
    },
    "flags": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Flags",
      "default": []
    },
    "extraction_meta": {
      "additionalProperties": true,
      "type": "object",
      "title": "Extraction Meta",
      "default": {}
    },
    "confirmation": {
      "additionalProperties": true,
      "type": "object",
      "title": "Confirmation",
      "default": {}
    }
  },
  "type": "object",
  "required": [
    "clinical_test_id",
    "extraction_id",
    "status",
    "document"
  ],
  "title": "ExtractionResponse"
}
```

### ExtractionStatus

```json
{
  "type": "string",
  "enum": [
    "queued",
    "extracting",
    "awaiting_confirmation",
    "confirmed",
    "clinically_validated",
    "extraction_failed",
    "unreadable",
    "discarded",
    "not_applicable",
    "rejected"
  ],
  "title": "ExtractionStatus"
}
```

### FileInfo

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name"
    },
    "mime_type": {
      "type": "string",
      "title": "Mime Type"
    },
    "size_bytes": {
      "type": "integer",
      "title": "Size Bytes"
    }
  },
  "type": "object",
  "required": [
    "name",
    "mime_type",
    "size_bytes"
  ],
  "title": "FileInfo"
}
```

### FlagSeverity

```json
{
  "type": "string",
  "enum": [
    "critical",
    "high",
    "info"
  ],
  "title": "FlagSeverity"
}
```

### HTTPValidationError

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "type": "array",
      "title": "Detail"
    }
  },
  "type": "object",
  "title": "HTTPValidationError"
}
```

### InitiateUploadRequest

```json
{
  "properties": {
    "client_upload_id": {
      "type": "string",
      "maxLength": 200,
      "minLength": 1,
      "title": "Client Upload Id"
    },
    "file_name": {
      "type": "string",
      "maxLength": 255,
      "minLength": 1,
      "title": "File Name"
    },
    "mime_type": {
      "type": "string",
      "title": "Mime Type"
    },
    "size_bytes": {
      "type": "integer",
      "exclusiveMinimum": 0.0,
      "title": "Size Bytes"
    },
    "sha256": {
      "type": "string",
      "maxLength": 64,
      "minLength": 64,
      "title": "Sha256"
    },
    "test_type": {
      "$ref": "#/components/schemas/TestType"
    },
    "title": {
      "type": "string",
      "maxLength": 200,
      "minLength": 1,
      "title": "Title"
    },
    "test_date": {
      "type": "string",
      "title": "Test Date"
    },
    "ai_consent": {
      "type": "boolean",
      "title": "Ai Consent",
      "default": false
    },
    "notes": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 2000
        },
        {
          "type": "null"
        }
      ],
      "title": "Notes"
    },
    "case_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Case Id"
    },
    "appointment_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Appointment Id"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "client_upload_id",
    "file_name",
    "mime_type",
    "size_bytes",
    "sha256",
    "test_type",
    "title",
    "test_date"
  ],
  "title": "InitiateUploadRequest"
}
```

### InitiateUploadResponse

```json
{
  "properties": {
    "upload_id": {
      "type": "string",
      "title": "Upload Id"
    },
    "clinical_test_id": {
      "type": "string",
      "title": "Clinical Test Id"
    },
    "status": {
      "$ref": "#/components/schemas/UploadStatus",
      "default": "initiated"
    },
    "upload": {
      "$ref": "#/components/schemas/SignedUrlResponse"
    }
  },
  "type": "object",
  "required": [
    "upload_id",
    "clinical_test_id",
    "upload"
  ],
  "title": "InitiateUploadResponse"
}
```

### LabReportExportRequest

```json
{
  "properties": {
    "clinical_test_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Clinical Test Id"
    },
    "window_months": {
      "type": "integer",
      "maximum": 60.0,
      "minimum": 1.0,
      "title": "Window Months",
      "default": 12
    },
    "include_series": {
      "type": "boolean",
      "title": "Include Series",
      "default": true
    }
  },
  "additionalProperties": false,
  "type": "object",
  "title": "LabReportExportRequest"
}
```

### LabReportExportResponse

```json
{
  "properties": {
    "export_id": {
      "type": "string",
      "title": "Export Id"
    },
    "patient_id": {
      "type": "string",
      "title": "Patient Id"
    },
    "status": {
      "type": "string",
      "const": "ready",
      "title": "Status"
    },
    "file_name": {
      "type": "string",
      "title": "File Name"
    },
    "download_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Download Url"
    },
    "expires_at": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Expires At"
    },
    "size_bytes": {
      "type": "integer",
      "title": "Size Bytes"
    },
    "sha256": {
      "type": "string",
      "title": "Sha256"
    },
    "storage": {
      "type": "string",
      "const": "gcs",
      "title": "Storage"
    },
    "replayed": {
      "type": "boolean",
      "title": "Replayed"
    },
    "generated_at": {
      "type": "string",
      "title": "Generated At"
    }
  },
  "type": "object",
  "required": [
    "export_id",
    "patient_id",
    "status",
    "file_name",
    "download_url",
    "expires_at",
    "size_bytes",
    "sha256",
    "storage",
    "replayed",
    "generated_at"
  ],
  "title": "LabReportExportResponse"
}
```

### LabReportResponse

```json
{
  "properties": {
    "generated_at": {
      "type": "string",
      "title": "Generated At"
    },
    "header": {
      "additionalProperties": true,
      "type": "object",
      "title": "Header"
    },
    "score": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Score"
    },
    "flags": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Flags"
    },
    "results": {
      "additionalProperties": true,
      "type": "object",
      "title": "Results"
    },
    "longitudinal": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Longitudinal"
    },
    "imaging_findings": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Imaging Findings"
    },
    "traceability": {
      "additionalProperties": true,
      "type": "object",
      "title": "Traceability"
    },
    "actions": {
      "additionalProperties": {
        "type": "string"
      },
      "type": "object",
      "title": "Actions"
    }
  },
  "type": "object",
  "required": [
    "generated_at",
    "header",
    "score",
    "flags",
    "results",
    "longitudinal",
    "imaging_findings",
    "traceability",
    "actions"
  ],
  "title": "LabReportResponse"
}
```

### LabScoreResponse

```json
{
  "properties": {
    "current_snapshot": {
      "$ref": "#/components/schemas/ScoreSnapshotModel"
    },
    "history": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/components/schemas/ScoreSnapshotModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "History"
    }
  },
  "type": "object",
  "required": [
    "current_snapshot"
  ],
  "title": "LabScoreResponse"
}
```

### ListClinicalTestsResponse

```json
{
  "properties": {
    "items": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Items"
    },
    "next_cursor": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Next Cursor"
    }
  },
  "type": "object",
  "required": [
    "items"
  ],
  "title": "ListClinicalTestsResponse"
}
```

### MarkerCorrection

```json
{
  "properties": {
    "marker_code": {
      "type": "string",
      "title": "Marker Code"
    },
    "value_raw": {
      "type": "string",
      "title": "Value Raw"
    },
    "unit_raw": {
      "type": "string",
      "title": "Unit Raw"
    },
    "reason": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Reason",
      "default": "clinical_correction"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "marker_code",
    "value_raw",
    "unit_raw"
  ],
  "title": "MarkerCorrection"
}
```

### MarkerEdit

```json
{
  "properties": {
    "op": {
      "type": "string",
      "enum": [
        "add",
        "update",
        "remove"
      ],
      "title": "Op"
    },
    "marker_code": {
      "type": "string",
      "title": "Marker Code"
    },
    "value_raw": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Value Raw"
    },
    "unit_raw": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Unit Raw"
    },
    "reference": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/ReferenceRange"
        },
        {
          "type": "null"
        }
      ]
    },
    "reason": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Reason"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "op",
    "marker_code"
  ],
  "title": "MarkerEdit"
}
```

### MarkerItem

```json
{
  "properties": {
    "marker_code": {
      "type": "string",
      "title": "Marker Code"
    },
    "loinc": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Loinc"
    },
    "raw_name": {
      "type": "string",
      "title": "Raw Name"
    },
    "mapping_status": {
      "type": "string",
      "title": "Mapping Status",
      "default": "mapped"
    },
    "value_type": {
      "type": "string",
      "title": "Value Type",
      "default": "numeric"
    },
    "value_raw": {
      "type": "string",
      "title": "Value Raw"
    },
    "unit_raw": {
      "type": "string",
      "title": "Unit Raw"
    },
    "value_canonical": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Value Canonical"
    },
    "unit_canonical": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Unit Canonical"
    },
    "conversion_factor": {
      "type": "number",
      "title": "Conversion Factor",
      "default": 1.0
    },
    "censoring": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Censoring"
    },
    "value_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Value Text"
    },
    "reference": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/ReferenceRange"
        },
        {
          "type": "null"
        }
      ]
    },
    "status": {
      "$ref": "#/components/schemas/MarkerStatus",
      "default": "normal"
    },
    "confidence": {
      "$ref": "#/components/schemas/ConfidenceScores"
    },
    "provenance": {
      "additionalProperties": true,
      "type": "object",
      "title": "Provenance"
    },
    "validation": {
      "additionalProperties": true,
      "type": "object",
      "title": "Validation"
    },
    "edited": {
      "type": "boolean",
      "title": "Edited",
      "default": false
    },
    "edited_by": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Edited By"
    },
    "edited_by_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Edited By Id"
    },
    "edited_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Edited At"
    },
    "original_value_canonical": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Original Value Canonical"
    }
  },
  "type": "object",
  "required": [
    "marker_code",
    "raw_name",
    "value_raw",
    "unit_raw"
  ],
  "title": "MarkerItem"
}
```

### MarkerPoint

```json
{
  "properties": {
    "measured_on": {
      "type": "string",
      "title": "Measured On"
    },
    "value": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Value"
    },
    "unit": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Unit"
    },
    "reference": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Reference"
    },
    "status": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Status"
    },
    "subscore": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Subscore"
    },
    "clinical_test_id": {
      "type": "string",
      "title": "Clinical Test Id"
    },
    "confirmation_level": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Confirmation Level"
    },
    "edited": {
      "type": "boolean",
      "title": "Edited"
    }
  },
  "type": "object",
  "required": [
    "measured_on",
    "value",
    "unit",
    "reference",
    "status",
    "subscore",
    "clinical_test_id",
    "confirmation_level",
    "edited"
  ],
  "title": "MarkerPoint"
}
```

### MarkerSeries

```json
{
  "properties": {
    "marker_code": {
      "type": "string",
      "title": "Marker Code"
    },
    "unit": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Unit"
    },
    "points": {
      "items": {
        "$ref": "#/components/schemas/MarkerPoint"
      },
      "type": "array",
      "title": "Points"
    }
  },
  "type": "object",
  "required": [
    "marker_code",
    "unit",
    "points"
  ],
  "title": "MarkerSeries"
}
```

### MarkerSeriesResponse

```json
{
  "properties": {
    "patient_id": {
      "type": "string",
      "title": "Patient Id"
    },
    "from": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "From"
    },
    "to": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "To"
    },
    "only_confirmed": {
      "type": "boolean",
      "title": "Only Confirmed"
    },
    "series": {
      "items": {
        "$ref": "#/components/schemas/MarkerSeries"
      },
      "type": "array",
      "title": "Series"
    }
  },
  "type": "object",
  "required": [
    "patient_id",
    "from",
    "to",
    "only_confirmed",
    "series"
  ],
  "title": "MarkerSeriesResponse"
}
```

### MarkerStatus

```json
{
  "type": "string",
  "enum": [
    "low",
    "normal",
    "high",
    "critical_low",
    "critical_high",
    "indeterminate"
  ],
  "title": "MarkerStatus"
}
```

### PanelItem

```json
{
  "properties": {
    "panel_code": {
      "type": "string",
      "title": "Panel Code"
    },
    "panel_name_raw": {
      "type": "string",
      "title": "Panel Name Raw"
    },
    "specimen": {
      "type": "string",
      "title": "Specimen",
      "default": "blood"
    },
    "collection_date": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Collection Date"
    },
    "fasting": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "title": "Fasting"
    },
    "markers": {
      "items": {
        "$ref": "#/components/schemas/MarkerItem"
      },
      "type": "array",
      "title": "Markers",
      "default": []
    }
  },
  "type": "object",
  "required": [
    "panel_code",
    "panel_name_raw"
  ],
  "title": "PanelItem"
}
```

### PatientConfirmationRequest

```json
{
  "properties": {
    "action": {
      "type": "string",
      "enum": [
        "confirm",
        "discard"
      ],
      "title": "Action",
      "default": "confirm"
    },
    "extraction_id": {
      "type": "string",
      "title": "Extraction Id"
    },
    "acknowledged_marker_codes": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "maxItems": 1000,
      "title": "Acknowledged Marker Codes"
    },
    "document_edits": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/DocumentEdits"
        },
        {
          "type": "null"
        }
      ]
    },
    "marker_edits": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/components/schemas/MarkerEdit"
          },
          "type": "array",
          "maxItems": 1000
        },
        {
          "type": "null"
        }
      ],
      "title": "Marker Edits"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "extraction_id"
  ],
  "title": "PatientConfirmationRequest"
}
```

### PillarContribution

```json
{
  "properties": {
    "marker_code": {
      "type": "string",
      "title": "Marker Code"
    },
    "name": {
      "type": "string",
      "title": "Name"
    },
    "value": {
      "type": "number",
      "title": "Value"
    },
    "unit": {
      "type": "string",
      "title": "Unit"
    },
    "subscore": {
      "type": "number",
      "title": "Subscore"
    },
    "weight": {
      "type": "number",
      "title": "Weight"
    },
    "clinical_test_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Clinical Test Id"
    },
    "measured_on": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Measured On"
    }
  },
  "type": "object",
  "required": [
    "marker_code",
    "name",
    "value",
    "unit",
    "subscore",
    "weight"
  ],
  "title": "PillarContribution"
}
```

### PillarScore

```json
{
  "properties": {
    "score": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Score"
    },
    "coverage": {
      "type": "number",
      "title": "Coverage"
    },
    "confidence": {
      "$ref": "#/components/schemas/ScoreConfidence"
    },
    "status": {
      "type": "string",
      "title": "Status",
      "default": "published"
    },
    "contributions": {
      "items": {
        "$ref": "#/components/schemas/PillarContribution"
      },
      "type": "array",
      "title": "Contributions",
      "default": []
    }
  },
  "type": "object",
  "required": [
    "coverage",
    "confidence"
  ],
  "title": "PillarScore"
}
```

### ProcessingStatus

```json
{
  "properties": {
    "malware_scan": {
      "$ref": "#/components/schemas/ScanStatus"
    },
    "mime_validation": {
      "$ref": "#/components/schemas/ScanStatus"
    }
  },
  "type": "object",
  "required": [
    "malware_scan",
    "mime_validation"
  ],
  "title": "ProcessingStatus"
}
```

### ReferenceRange

```json
{
  "properties": {
    "low": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Low"
    },
    "high": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "High"
    },
    "unit": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Unit"
    },
    "source": {
      "type": "string",
      "title": "Source",
      "default": "document"
    },
    "text_raw": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Text Raw"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "title": "ReferenceRange"
}
```

### RefreshUrlRequest

```json
{
  "properties": {
    "client_upload_id": {
      "type": "string",
      "title": "Client Upload Id"
    },
    "sha256": {
      "type": "string",
      "maxLength": 64,
      "minLength": 64,
      "title": "Sha256"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "client_upload_id",
    "sha256"
  ],
  "title": "RefreshUrlRequest"
}
```

### RefreshUrlResponse

```json
{
  "properties": {
    "upload_id": {
      "type": "string",
      "title": "Upload Id"
    },
    "status": {
      "$ref": "#/components/schemas/UploadStatus"
    },
    "upload": {
      "$ref": "#/components/schemas/SignedUrlResponse"
    }
  },
  "type": "object",
  "required": [
    "upload_id",
    "status",
    "upload"
  ],
  "title": "RefreshUrlResponse"
}
```

### ReprocessRequest

```json
{
  "properties": {
    "confirm_reprocess_confirmed": {
      "type": "boolean",
      "title": "Confirm Reprocess Confirmed",
      "default": false
    }
  },
  "additionalProperties": false,
  "type": "object",
  "title": "ReprocessRequest"
}
```

### ReviewInfo

```json
{
  "properties": {
    "status": {
      "$ref": "#/components/schemas/ReviewStatus"
    },
    "reviewed_at": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Reviewed At"
    },
    "reviewed_by": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Reviewed By"
    }
  },
  "type": "object",
  "required": [
    "status"
  ],
  "title": "ReviewInfo"
}
```

### ReviewRequest

```json
{
  "properties": {
    "expected_version": {
      "anyOf": [
        {
          "type": "string",
          "pattern": "^[a-f0-9]{64}$"
        },
        {
          "type": "null"
        }
      ],
      "title": "Expected Version"
    },
    "review_status": {
      "type": "string",
      "const": "reviewed",
      "title": "Review Status",
      "default": "reviewed"
    },
    "review_note": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 2000
        },
        {
          "type": "null"
        }
      ],
      "title": "Review Note"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "title": "ReviewRequest"
}
```

### ReviewStatus

```json
{
  "type": "string",
  "enum": [
    "not_reviewed",
    "reviewed"
  ],
  "title": "ReviewStatus"
}
```

### ScanStatus

```json
{
  "type": "string",
  "enum": [
    "pending",
    "passed",
    "failed"
  ],
  "title": "ScanStatus"
}
```

### ScoreConfidence

```json
{
  "type": "string",
  "enum": [
    "high",
    "medium",
    "insufficient"
  ],
  "title": "ScoreConfidence"
}
```

### ScoreFlag

```json
{
  "properties": {
    "code": {
      "type": "string",
      "title": "Code"
    },
    "severity": {
      "$ref": "#/components/schemas/FlagSeverity"
    },
    "marker_code": {
      "type": "string",
      "title": "Marker Code"
    },
    "value": {
      "type": "number",
      "title": "Value"
    },
    "unit": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Unit"
    },
    "message": {
      "type": "string",
      "title": "Message"
    }
  },
  "type": "object",
  "required": [
    "code",
    "severity",
    "marker_code",
    "value",
    "message"
  ],
  "title": "ScoreFlag"
}
```

### ScoreSnapshotModel

```json
{
  "properties": {
    "catalog_hash": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Catalog Hash"
    },
    "source_digest": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Source Digest"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object",
      "title": "Parameters",
      "default": {}
    },
    "catalog_clinically_approved": {
      "type": "boolean",
      "title": "Catalog Clinically Approved",
      "default": false
    },
    "snapshot_id": {
      "type": "string",
      "title": "Snapshot Id"
    },
    "patient_id": {
      "type": "string",
      "title": "Patient Id"
    },
    "computed_at": {
      "type": "string",
      "title": "Computed At"
    },
    "trigger": {
      "type": "string",
      "title": "Trigger"
    },
    "scoring_version": {
      "type": "string",
      "title": "Scoring Version",
      "default": "score-v1.0"
    },
    "catalog_version": {
      "type": "string",
      "title": "Catalog Version",
      "default": "cat-2026.08"
    },
    "window": {
      "additionalProperties": true,
      "type": "object",
      "title": "Window"
    },
    "lab_index": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Lab Index"
    },
    "base_score": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Base Score"
    },
    "penalty_applied": {
      "type": "number",
      "title": "Penalty Applied",
      "default": 0.0
    },
    "pillars": {
      "additionalProperties": {
        "$ref": "#/components/schemas/PillarScore"
      },
      "type": "object",
      "title": "Pillars"
    },
    "flags": {
      "items": {
        "$ref": "#/components/schemas/ScoreFlag"
      },
      "type": "array",
      "title": "Flags",
      "default": []
    },
    "excluded_markers": {
      "items": {
        "$ref": "#/components/schemas/ExcludedMarker"
      },
      "type": "array",
      "title": "Excluded Markers",
      "default": []
    }
  },
  "type": "object",
  "required": [
    "snapshot_id",
    "patient_id",
    "computed_at",
    "trigger",
    "window",
    "pillars"
  ],
  "title": "ScoreSnapshotModel"
}
```

### SignedUrlResponse

```json
{
  "properties": {
    "method": {
      "type": "string",
      "title": "Method",
      "default": "PUT"
    },
    "signed_url": {
      "type": "string",
      "title": "Signed Url"
    },
    "required_headers": {
      "additionalProperties": true,
      "type": "object",
      "title": "Required Headers"
    },
    "expires_at": {
      "type": "string",
      "title": "Expires At"
    }
  },
  "type": "object",
  "required": [
    "signed_url",
    "required_headers",
    "expires_at"
  ],
  "title": "SignedUrlResponse"
}
```

### TestType

```json
{
  "type": "string",
  "enum": [
    "blood_test",
    "urine_test",
    "imaging",
    "pathology",
    "other"
  ],
  "title": "TestType"
}
```

### UploadStatus

```json
{
  "type": "string",
  "enum": [
    "initiated",
    "object_uploaded",
    "processing",
    "ready_for_review",
    "rejected",
    "failed",
    "deleted"
  ],
  "title": "UploadStatus"
}
```

### UploadStatusResponse

```json
{
  "properties": {
    "clinical_test_id": {
      "type": "string",
      "title": "Clinical Test Id"
    },
    "upload_id": {
      "type": "string",
      "title": "Upload Id"
    },
    "status": {
      "$ref": "#/components/schemas/UploadStatus"
    },
    "processing": {
      "$ref": "#/components/schemas/ProcessingStatus"
    },
    "local_file_can_be_deleted": {
      "type": "boolean",
      "title": "Local File Can Be Deleted"
    },
    "error": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Error"
    },
    "completed_at": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Completed At"
    }
  },
  "type": "object",
  "required": [
    "clinical_test_id",
    "upload_id",
    "status",
    "processing",
    "local_file_can_be_deleted"
  ],
  "title": "UploadStatusResponse"
}
```

### ValidationError

```json
{
  "properties": {
    "loc": {
      "items": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "integer"
          }
        ]
      },
      "type": "array",
      "title": "Location"
    },
    "msg": {
      "type": "string",
      "title": "Message"
    },
    "type": {
      "type": "string",
      "title": "Error Type"
    },
    "input": {
      "title": "Input"
    },
    "ctx": {
      "type": "object",
      "title": "Context"
    }
  },
  "type": "object",
  "required": [
    "loc",
    "msg",
    "type"
  ],
  "title": "ValidationError"
}
```

## Cambios que el cliente historico necesita
No se modifico frontend: retirar firma HS256; implementar PUT/hash reales, encabezados, ediciones persistidas, review_note/marker_corrections, confidence por campo, manejo de permisos y seleccion consistente del paciente. Usar URL GCS real, nunca PDF fabricado o ruta exports.

## Limitaciones
Contrato local verificado con dobles en checks. No se valido identidad o infraestructura externa. Esquemas extensibles no permiten generar tipos precisos de todas las secciones de reportes. No hay contrato nuevo de planes comerciales ni endpoints de consentimiento revocable.


### Precondición de integridad clínica

GET `/clinical-tests/{id}` y GET `/clinical-tests/{id}/extraction` incluyen `clinical_version` (huella opaca de 64 caracteres hexadecimales del documento y de la extracción vigente). El listado no sustituye la lectura del detalle para preparar una mutación. PATCH `/clinical-tests/{id}/review` y POST `/clinical-tests/{id}/extraction/validate` reciben `expected_version`, obtenido del detalle sobre el que se preparó la operación. La comparación ocurre dentro de la transacción antes de los cambios; una carrera Mongo aborta la operación completa, incluida su auditoría.

- Versión obsoleta: 409 `CLINICAL_VERSION_CONFLICT`. Conflicto transitorio Mongo: 409 `RETRYABLE_CONFLICT`. Consultar estado actual; no reproducir automáticamente la mutación.
- Versión omitida: 428 `CLINICAL_VERSION_REQUIRED`, sin cambios. Formato inválido: 422. Los clientes anteriores conservan lecturas, pero deben actualizarse para nuevas escrituras clínicas. Omitir la versión no habilita una escritura insegura.
- Revisión ya aplicada por el mismo profesional y con la misma nota: 200 sin nuevas escrituras de dominio ni auditoría, incluso si la versión ya cambió. Otra nota o revisor: 409. Validación/rechazo no incorporan replay idempotente; ante resultado incierto consultar, sin atribuir automáticamente el resultado.
- GET de extracción permite `rejected` al clínico con relación y scope vigentes, conservando tenant y privacidad de notas. No habilita corrección ni validación posterior al rechazo. La política del paciente no cambia.

Campos aditivos, sin migración de datos. OpenAPI documenta los dos campos y 428; React conserva las versiones en RAM y bloquea snapshots mezclados, cambios concurrentes y servidores que no ofrecen la precondición.

### Precondición atómica de exportación PDF

GET `/patients/{id}/lab-report` entrega `source_version` opaca, ligada al tenant, revisión monotónica de fuentes y hash del reporte completo/política de publicación. Es estable entre proyecciones de series/snapshot y no incorpora `generated_at`; los filtros de examen/ventana sí forman parte de su significado. POST `/patients/{id}/lab-report/export` exige `expected_source_version` leída de ese GET y `Idempotency-Key`. Omitida/nula: **428** `EXPORT_VERSION_REQUIRED`; malformada: **422**; obsoleta: **409** `EXPORT_SOURCE_CHANGED`. Clientes antiguos deben actualizarse: no existe exportación insegura por compatibilidad. OpenAPI y tipos TS se regeneran juntos.

La reserva, el commit del artefacto y la publicación final usan transacciones MongoDB snapshot/majority con CAS sobre la revisión compartida; generación/carga/firma ocurren fuera. Las escrituras de fuentes mediante la fachada incrementan revisión e invalidan `pending`/`committed` en la misma transacción. Una nueva exportación no modifica la revisión. El ámbito conservador es todo el tenant. No se migran ni modifican snapshots previos.

- `pending`: 409 `EXPORT_IN_PROGRESS`, `Retry-After: 1`; reintento manual con igual clave, versión y filtros. Mongo transitorio: `RETRYABLE_CONFLICT`, sin replay automático.
- `failed` o lease vencido: 409 `EXPORT_ATTEMPT_FAILED`/`EXPORT_ATTEMPT_EXPIRED`; refrescar y solicitar explícitamente otro intento. Nunca reintentar automáticamente una carga con resultado externo ambiguo.
- `stale`: 409 `EXPORT_SOURCE_CHANGED`, sin enlace. Cambiar parámetros/versión de una clave ya registrada: 409 `IDEMPOTENCY_CONFLICT`.
- `committed`: 200 `ready` o `download_pending`; requiere `source_version` y `verified_at`. El firmador puede recuperarse con la misma clave sin duplicar PDF ni auditoría de éxito. Una URL solo sale después del commit de la verificación final; la sesión expirada y la relación clínica revocada impiden publicarla.

Los objetos cargados antes de un conflicto permanecen privados y referenciados por el intento para reconciliación revisada, sin borrado automático. Los fallos se auditan fuera de la transacción abortada. Un enlace ya emitido puede seguir válido hasta su expiración aunque cambie la fuente; `verified_at` expresa una comprobación puntual. Una escritura administrativa que eluda la fachada o una política externa modificada entre procesos necesita control adicional. Se conserva el bloqueo PDF productivo del portal y no se habilita ningún despliegue. Arquitectura, compatibilidad y límites operativos: `frontend/HISTORY.md`, sección Exportación y continuidad.
