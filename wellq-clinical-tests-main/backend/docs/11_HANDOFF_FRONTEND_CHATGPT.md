# Handoff backend para ChatGPT y futuros clientes

> **Vigencia tras cierre focalizado F01-F07 (2026-11-05):** Estado vigente en12_CIERRE_DEFECTOS_F01_F07: 276 aprobadas/209 omitidas, siete defectos cerrados localmente y OpenAPI actualizado. React visual con sinteticos puede avanzar; integracion real y produccion clinica siguen sin verificar. Tratar el contenido previo como contexto historico. [Detalle y evidencia](12_CIERRE_DEFECTOS_F01_F07.md).
> El contenido anterior al cierre se conserva a continuacion como referencia historica; esta nota y el documento12 prevalecen donde difieran.

**Fecha:** 2026-11-05 (America/Santiago). **Rama:** fix/wellq-backend-hardening. **Base:** fb8746cd42fe107bbda82dd92d3a4d11d545fd3e + cambios sin commit.

**Alcance:** backend; rutas de código relativas a wellq-clinical-tests-main/backend salvo indicación. **Método:** contraste estático, implementación y pruebas aisladas. **Límites:** sin servicios clínicos, datos reales, migraciones, despliegues ni validación clínica. No se modificó frontend.


## Identidad del snapshot
WellQ Medical Exams, C:/Dev/wellq-capstone, backend wellq-clinical-tests-main/backend. Rama fix/wellq-backend-hardening desde fb8746cd42fe107bbda82dd92d3a4d11d545fd3e; cambios sin commit. Esta documentación supera las afirmaciones A–F “100%” del antiguo HANDOFF_STATE, que se conservó como histórico.
La tarea fue exclusivamente backend. Se verificará el hash de ambos HTML contra la línea base; no se desarrolló frontend.

## Resultado
API FastAPI y MongoDB conservadas, GCS previsto y adaptador real sin fallback, aislamiento tenant, JWT RS256 externo, cargas verificables, trabajos Mongo persistentes, propuesta multimodal estricta sin generador ficticio, confirmación/validación y scoring corregidos, reporte y PDF privados.
No hay plataforma de usuarios nueva, proveedor multimodal concreto, catálogo ampliado aprobado o despliegue real probado. El entorno productivo está deliberadamente bloqueado si faltan identidad/esquema/dependencias.

## Mapa de código
- main/config/database: aplicación y fronteras de operación.
- dependencies/auth y access: autoridad externa, grants, rol, tenant y relación clínica.
- tenancy y services/transactions: acceso cerrado y transacciones Mongo.
- services/uploads/storage/file_validation: sesiones, GCS, hash/tipo/escáner.
- workers/processing: outbox, lease, reintento y fencing.
- services/extractor/evaluation: adaptación multimodal pendiente y evaluación offline.
- services/catalog/scoring: catálogo versionado original, normalización, ventana y manifests.
- routes/extractions y clinical_tests: operaciones HTTP; models/schemas/extraction/scoring/reporting: DTO.
- clinical_result_history: historia clínica privada de correcciones; audit_events/audit_logs: metadatos técnicos sin valores.
- checks: pruebas completamente en proceso; tests: suite histórica bloqueada antes de tocar servicios.
- scripts/recompute_scoring: tenant explícito y versión real; no ejecutar sobre datos existentes sin procedimiento aprobado.

## Contrato de confianza
No generar ni firmar JWT desde React o Flutter. Obtener token de autoridad aprobada. El backend solo tiene clave pública RS256, issuer/audience y claims requeridos. Patient_id/clinician_id y client_id vienen del token; no se aceptan campos de identidad en body de carga.
El cliente puede ocultar acciones por permisos, pero el servidor aplica rol, propiedad, relación clínica, scope y capacidad. Exportación exige reports:export y report_export; score y reporte son solo clínicos.
Los tokens de test se generan únicamente en memoria durante checks. No constituyen servicio de login de desarrollo/productivo.

## Flujo del paciente
Seleccionar archivo y copiar a almacenamiento privado; persistir client_upload_id, hash real y estado en Drift para móvil. initiate con MIME/tamaño/hash y ai_consent explícito. Ejecutar PUT a signed_url con required_headers completos. Avisar complete con la misma sesión y claves estables; consultar status con backoff/jitter.
Eliminar copia local solo cuando status.local_file_can_be_deleted sea true, aunque la IA siga pendiente. No inferir ese permiso desde complete, respuesta de extracción o una animación.
Leer propuesta; mostrar confidence.value/unit/reference/name, procedencia y banderas. Revisión de identidad no resuelta exige identity_confirmed; low_confidence exige códigos reconocidos. Enviar marker_edits reales: agregar/modificar/quitar no es solo cambiar DOM.
Confirmar conserva propuesta y genera derivados si hay catálogo clínico aprobado. Descartar/reprocesar según estado; reproceso es queued y requiere sondeo posterior.

## Flujo clínico
Obtener identidad clínica real y paciente autorizado. Listar exámenes del paciente, leer resultados confirmados, revisar o validar/corregir por rutas separadas. review_note y clinical_note tienen funciones diferentes; las notas no son públicas.
Lab-score devuelve snapshots vigentes e histórico solo al clínico. Sin aprobación o fuente vigente no existe score actual. Reporte JSON y PDF derivan de los mismos datos; exportar en servidor y descargar la URL GCS firmada, nunca fabricar un sustituto del original.
Si cambia la fuente, una clave de exportación antigua se rechaza para evitar presentar PDF viejo como actual. El histórico de snapshots se conserva; no se sobrescribe.

## React+TypeScript
Usar 03_CONTRATOS_API_FRONTEND y openapi.json para tipos. Las secciones extensibles de reporte todavía usan dict: no asumir precisión de un cliente generado más allá del esquema real. Mantener cliente HTTP común, manejo de 401/403/409/422/429/503 y estado de paciente activo coherente.
No reutilizar el generador HS256, progreso ficticio, SHA fijo, descargas fabricadas o fields incorrectos del HTML histórico. i18n/temas/accesibilidad siguen en alcance futuro; no se implementaron aquí.

## Flutter+Dart+Drift
Cola durable local, copia privada, checksum real, URLs expirables, reanudación y backoff. Guardar claves de idempotencia por operación; clave nueva solo para nueva intención/refresh tras expiración. Usar almacenamiento de sesión apropiado a la plataforma y política del proveedor, aún pendiente.
Paciente no consume score, reporte clínico ni contribuciones. La cola debe separar upload verified, extraction queued/awaiting_confirmation y validación humana.

## Evidencia y límites
215 aprobadas en checks con claves efímeras, documentos sintéticos, mongomock y dobles de storage/scanner/provider; 209 históricas omitidas, no aprobadas. JUnit y auditorías de dependencias conservados. Ruff y pip check correctos.
Mongo real, firmas/IAM GCS, ClamAV, proveedor/corpus, imagen Docker y privacidad clínica no se verificaron. Docker no está operativo. Un modelo de rollback en memoria no acredita transacciones de servidor.

## Qué entregar a otro asistente
Entregar los once Markdown de esta carpeta, openapi.json, test-results.xml y los informes dependencies-before/after.json. Empezar por 01, 03, 08, 10 y este 11; consultar 02 para compatibilidad y 09 antes de tocar infraestructura/datos.
El Documento Maestro completo debe incorporarse como fuente cuando esté disponible. No inventar contenido, migrar datos, activar proveedor, ampliar rangos o declarar producción lista sin cerrar los bloqueos de 10.

## Integridad final
Los dos HTML originales conservan exactamente sus SHA-256 de la linea base: backend/app/static/index.html y ../frontend/index.html. Todos los cambios versionados y archivos nuevos reportados por Git estan dentro de backend. No hay commits nuevos, push, merge, rebase, migraciones o despliegues. Git queda deliberadamente con cambios de trabajo para revision. change-manifest.json registra rutas y huellas de fuentes modificadas.
