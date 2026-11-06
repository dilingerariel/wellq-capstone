# Contratos verificados para frontend

Fecha: 2026-11-05. Rama `fix/wellq-backend-hardening`, HEAD `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`, con cambios locales. Complementa los documentos 03, 11 y 12 sin sobrescribirlos. No se modificó el frontend.

## Fuente y evidencia

[openapi.json](openapi.json) coincide exactamente con `app.openapi()` tras los ajustes de integración. La API Docker expuso las **20 operaciones clínicas**, y todas documentan HTTP 422 mediante `ErrorResponse`. No hay nuevas rutas ni cambios en schemas en esta tarea. La prueba `test_00_runtime_startup_and_contract` comprueba HTTP real, health/readiness, número de operaciones, esquema 422 y denegación de dashboard/static/export públicos.

[frontend-examples.json](evidencias_integracion/frontend-examples.json) contiene ocho respuestas HTTP capturadas realmente con datos sintéticos: documento paciente, extracción, serie clínica, reporte clínico, reporte denegado al paciente, error 422, exportación pendiente y replay listo. Los IDs son opacos; enlaces firmados fueron redactados y no se guardaron tokens. Son ejemplos de contrato, no fixtures con fechas/IDs permanentes.

## Operaciones conservadas

Todas usan prefijo `/api/v1`. La lista enumera operaciones, no promete que cada rol tenga acceso a todas.

| Método | Ruta relativa |
|---|---|
| POST | `/clinical-tests/uploads/initiate` |
| POST | `/clinical-tests/uploads/{upload_id}/refresh-url` |
| POST | `/clinical-tests/uploads/{upload_id}/complete` |
| GET | `/clinical-tests/uploads/{upload_id}/status` |
| GET | `/clinical-tests` |
| GET | `/clinical-tests/{clinical_test_id}` |
| PATCH | `/clinical-tests/{clinical_test_id}` |
| DELETE | `/clinical-tests/{clinical_test_id}` |
| POST | `/clinical-tests/{clinical_test_id}/download-url` |
| GET | `/patients/{patient_id}/clinical-tests` |
| PATCH | `/clinical-tests/{clinical_test_id}/review` |
| GET | `/patients/{patient_id}/lab-score` |
| GET | `/patients/{patient_id}/markers` |
| GET | `/patients/{patient_id}/lab-report` |
| POST | `/patients/{patient_id}/lab-report/export` |
| GET | `/marker-catalog` |
| GET | `/clinical-tests/{clinical_test_id}/extraction` |
| PATCH | `/clinical-tests/{clinical_test_id}/extraction` |
| POST | `/clinical-tests/{clinical_test_id}/extraction/reprocess` |
| POST | `/clinical-tests/{clinical_test_id}/extraction/validate` |

Autorización en servidor: JWT RS256 de autoridad confiable, tenant obtenido del token, permisos y recurso propio; el clínico requiere relación asistencial. La exportación exige también capability `report_export`. No enviar un tenant elegido en frontend como sustituto de la identidad. Pacientes no acceden a rutas clínicas de puntuación/series/reportes/exportación; ocultar botones no reemplaza la denegación HTTP.

## Flujo de carga y extracción

1. Iniciar con metadatos, tamaño, SHA-256 e `Idempotency-Key` estable para la misma intención. Guardar `upload_id` y `clinical_test_id`.
2. Ejecutar PUT de los bytes sobre el enlace devuelto, respetando `required_headers`; no simular una carga solo llamando complete.
3. Completar con los datos de la misma carga. Consultar status: completar no significa terminar el procesamiento persistente.
4. Borrar la copia local solo si `local_file_can_be_deleted=true`. No deducirlo de health, del HTTP 200 de complete, ni del estado de extracción IA.
5. Consultar extracción hasta un estado consumible. Una propuesta puede esperar confirmación; reprocess es asíncrono y puede responder queued con `extraction_id:null`. Esperar el ID nuevo antes de aplicar ediciones a esa propuesta.

Estados upload del schema: `initiated`, `object_uploaded`, `processing`, `ready_for_review`, `rejected`, `failed`, `deleted`. Estados extracción: `queued`, `extracting`, `awaiting_confirmation`, `confirmed`, `clinically_validated`, `extraction_failed`, `unreadable`, `discarded`, `not_applicable`, `rejected`.

La seguridad del archivo y la extracción son independientes: un archivo verificado puede permitir borrar la copia local aunque IA falle, no sea aplicable o rechace una fecha. Scanner inaccesible conserva procesamiento pendiente/fallo cerrado y no habilita borrado; archivo rechazado tampoco. La suite distingue estas condiciones con Mongo real. La suite principal usa scanner de prueba; la suite antivirus identifica por separado el daemon real.

Confirmación, descarte, validación y exportación deben conservar la misma clave al reintentar la misma intención. Cambiar cuerpo con una clave usada puede responder 409; no generar claves nuevas automáticamente ante una respuesta incierta. `RETRYABLE_CONFLICT` puede reintentarse acotadamente con la misma clave. Un descarte repetido conserva respuesta/propuesta y un evento lógico.

## Nulos, fechas y confianza

`null` significa ausencia de dato o cálculo justificable; nunca sustituirlo por cero, rango inventado ni estado normal. `MarkerPoint` permite valor, unidad, referencia, estado y subscore nulos; `subscore_blank_reason` explica ausencia de cálculo donde corresponde. El reporte puede tener `score:null`. F02 confirma rangos incompletos sin inventar límites ni puntajes.

`provider_confidence` conserva lo declarado por el proveedor; `confidence` es la confianza efectiva tras validación. Un campo invalidado puede tener provider 0.99 y confianza efectiva 0: no promoverlo a válido mediante fallback numérico. La propuesta conserva el origen y el motivo. Referencia y estado deben provenir de la misma resolución; un rango documental no puede mostrarse con un estado calculado usando otro rango.

Fechas clínicas `YYYY-MM-DD` se validan en servidor y no admiten futuro. No sustituir fechas rechazadas por la del día. Timestamps son ISO 8601 UTC; aceptar segundos con o sin fracción. `computed_at` nuevo conserva microsegundos para ordenar snapshots de procesos diferentes creados durante el mismo segundo. Las contribuciones del score se ordenan establemente por código de marcador. No cambian fórmulas, pesos ni rangos; no ordenar eventos por fragmentos internos de ObjectId.

En esta instalación de pruebas se ven valores numéricos por la excepción test. No prueba aprobación clínica: fuera de test, catálogos/caches sin procedencia aprobada quedan sin subscore publicable. F01 se comprobó contra datos persistidos usando la política fuera de test en el runner; no se levantó una API productiva con identidades reales.

## Exportación y errores

`LabReportExportResponse.status=download_pending` indica PDF almacenado sin enlace utilizable: `download_url:null`, `expires_at:null`, `error_code=DOWNLOAD_URL_UNAVAILABLE`. Mantener `export_id`, mostrar pendiente y reintentar la misma solicitud/clave. Al recuperarse la firma, el replay responde ready con el mismo export_id, objeto y un solo evento. `ready` exige enlace utilizable y expiración; no habilitar descarga antes de ello. Cambios de fuente/política pueden exigir nueva intención mediante `409 EXPORT_SOURCE_CHANGED`.

La prueba de recuperación de firma usa un fallo inyectado del firmante local y Mongo real. No certifica IAM ni firma GCS. El enum `storage:gcs` se mantiene por compatibilidad del schema incluso en el doble local; esta evidencia no demuestra almacenamiento cloud.

Los errores usan `{"detail":{"code":"..."}}`, con campos opcionales `message`, `errors` y `reason`, y posibles campos de contexto. HTTP 422 de validación usa `code=INVALID_INPUT` y lista de errores estructurada; no asumir la lista FastAPI cruda como `detail`. Enums inválidos se rechazan como 422 antes de la lógica de negocio. Se comprobaron por HTTP real 401, 403, 404, 409, 422, 429 (límite de reprocess por examen) y 503 (dependencia de firma de upload). El límite global de solicitudes se elevó solo en test para evitar interferencias de la suite; el 429 observado no certifica su configuración productiva.

## Alcance para React

Se puede desarrollar UI y cliente tipado con OpenAPI y los ocho ejemplos; la autorización y lógica de negocio tienen evidencia de HTTP/Mongo/worker real con adaptadores externos declarados. Este Compose no publica API al host: un navegador no resuelve `api-int` ni `objects-int`. Una integración navegador completa requerirá exponer deliberadamente una API en un puerto libre de 127.0.0.1, revisar CORS/origen y un modo de transferencia de objetos accesible; esos cambios no se hicieron en esta tarea. Nunca utilizar los puertos de servicios antiguos ni transportar claves privadas de prueba al frontend.

GCS, IAM, proveedor IA/OCR, autoridad de identidad externa, SSO y despliegue cloud siguen pendientes. No usar este entorno con documentos de pacientes reales.
