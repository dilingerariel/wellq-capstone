# Cumplimiento de los cinco archivos originales

Fecha: 2026-11-05. Rama `fix/wellq-backend-hardening`; HEAD `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e` con cambios locales. Dictamen técnico del módulo revisado; no certifica cumplimiento clínico/legal de una plataforma externa. Primero se ejecutó la demo HTTP y se descargó el PDF; después se amplió esta comparación.

## Fuentes localizadas y versiones comprobadas

Los cinco archivos se localizaron y leyeron completos desde `C:\Users\vegal\Downloads`. Se extrajo `word/document.xml`, incluidos párrafos dentro de tablas; referencias **Pnnnn** son posiciones de párrafo XML, no páginas Word. Textos de referencia y metadatos de extracción se conservaron en `C:\Dev\wellq-demo-backups\20261105-130531\source-N.txt`. [Registro de fuentes y hashes](evidencias_demo/sources.json).

| ID | Nombre exacto | Versión realmente declarada | SHA-256 del DOCX |
|---|---|---|---|
| M | `Documento_Maestro_Proyecto_Examenes_Medicos_WellQ(2).docx` | 1.0, propuesta, 4 septiembre 2026; 1727 párrafos | `8998f513d9b0acd6dd4ac3772740aa3871cbd39671cac6f0bc42e042e0a0107a` |
| U | `Especificacion_Endpoints_Carga_Examenes_Medicos.docx` | 1.0, propuesta, 12-08-2026; 928 párrafos | `95ec6196fcde946a12e17870fc28a2ee7e135ce64f6a3ee9662fc413b39ba753` |
| E4 | `WellQ_Clinical_Test_Upload_API_Specification(4).docx` | Proposed for implementation; sin número/fecha de versión explícitos en el cuerpo; 468 párrafos | `53b31fdd545b126a8ba30c8532969ad0534ba32a65b6ad72c402ada62fc4a930` |
| E5 | `WellQ_Clinical_Test_Upload_API_Specification(5).docx` | Mismo contenido y bytes que E4 | `53b31fdd545b126a8ba30c8532969ad0534ba32a65b6ad72c402ada62fc4a930` |
| T | `Especificación Técnica de Estándares Transversales y Capacidades Comerciales.docx` | Sin versión/fecha semántica explícita; 28 párrafos | `5aaed1c113258a1d01b537a0ff9a42d19afe55773c75c4b25e53ace99a900eb4` |

E4 y E5 son **idénticos por SHA-256 de archivo y de texto**, por lo que **E** en la matriz significa ambos registros y una sola fuente normativa. Hay cinco archivos y cuatro contenidos diferentes; no se inventó un quinto conjunto. El título interno de T comienza con un marco estratégico de Alloxentric; su especificación técnica aparece desde P0007. Las fechas de sistema/edición de un DOCX no se interpretan como una nueva versión aprobada.

Jerarquía aplicada: M para extracción/scoring/reportería; U y E para transporte original; T agrega requisitos transversales. Un endpoint existente no basta para marcar un requisito como cumplido. La evidencia de dobles no acredita GCS/IA reales. No se consultaron documentos clínicos reales.

## Evidencias y cómo leer la matriz

- **D**: [demo HTTP (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion), respuestas redactadas y PDFs de los dos escenarios; Mongo/API/workers reales, objetos/IA/scanner test explícitos.
- **I**: [integración Docker de esta tarea](evidencias_demo/integration.xml); tests en `integration/tests/`. Una fila puede acreditar una propiedad de Mongo real y seguir dejando cloud pendiente.
- **A**: [regresión de aplicación](evidencias_demo/application-regressions.xml); `checks/`, con dobles en memoria, sin servicios reales. Incluye F01–F07 y ocho PDF nuevos.
- **P**: [ocho regresiones PDF](evidencias_demo/pdf-regressions.xml), tabla de 100 filas y reglas de contenido/pie. **V**: [revisión visual de todas las páginas](19_AUDITORIA_VISUAL_PDF.md).
- **AV anterior**: [ClamAV real 6/6](evidencias_integracion/clamav.xml) de la tarea de integración previa; no se reejecutó en la demo. **Código**: inspección actual, sin prueba suficiente para la obligación completa.

Los nombres de prueba de cada fila remiten al archivo indicado o al conjunto explícito en la leyenda; no significan que toda la obligación productiva esté cerrada. Las pruebas históricas originales no se modificaron ni se desactivó su guard. Las acciones pendientes son propuestas; no se ejecutaron migraciones ni ampliaciones clínicas para cerrar filas.

## API y especificaciones de carga

| Documento | Sección | Requisito | Archivo/función | Prueba | Evidencia | Estado | Acción pendiente |
|---|---|---|---|---|---|---|---|
| M/U/E | M §4; U §4; E §5 | 20 operaciones clínicas, incluidas 11 de carga | `app/main.py`, routers | `test_00_runtime_startup_and_contract` | I/OpenAPI | Cumplido y probado con servicios reales | Conservar schemas al integrar clientes |
| U/E | U §2.1; E §2 | JWT verificado y patient_id inferido | `dependencies/auth.py::get_current_user` | `test_authentication_and_grants_real_http`, security | I/A | Cumplido y probado con servicios reales | Autoridad RS256 de test; conectar emisor externo |
| U/E | U P0061; E P0034 | OTP/login/refresh de la plataforma | Integración externa no incluida | No ejecutada | Código | Bloqueado por dependencia externa | Parámetros y mapping de la identidad real |
| U/E | U §5.1; E §6.1 | Initiate valida y conserva una sesión idempotente | `services/uploads.py::initiate` | `test_http_idempotence_under_two_concurrent_clients`, quota | I/A/D | Cumplido y probado con dobles explícitos | Firma V4/IAM real pendiente |
| U/E | U §5.2; E §6.2 | Refresh no duplica y limita emisiones | `uploads.py::refresh` | `test_refresh_replay_does_not_consume_limit`, `test_full_upload_flow` | A/I | Parcial | Solo initiated; spec admite failed. Revisar contrato |
| U/E | U §5.1 P0293 | Replay initiate entrega enlace vigente si expiró | `uploads.py::initiate` retorna initial_response | Inspección, sin reloj cloud | Código | Parcial | Replay puede conservar enlace vencido; usar refresh y acordar semántica |
| U/E | U §5.3; E §6.3 | Complete encola atómicamente y no habilita borrado | `uploads.py::complete`, worker | `test_full_upload_flow`, demo | I/D | Cumplido y probado con dobles explícitos | Objeto se verifica en worker; no HEAD síncrono como spec |
| U/E | U §5.4; E §6.4 | Status autoriza borrado solo tras verificación | `uploads.py::upload_status` | `test_f05_provider_future_date_failure_does_not_block_local_delete`, documentos | I/D | Cumplido y probado con dobles explícitos | Validar durabilidad GCS con bucket autorizado |
| U/E | U §6.1; E §7.1 | Listado propio con filtros/cursor y sin URL | `clinical_tests.py::list_clinical_tests` | `test_endpoints_5_to_11_lifecycle` | I | Cumplido y probado con dobles explícitos | Rendimiento y paginación bajo carga pendientes |
| U/E | U §6.2; E §7.2 | Detalle propio/relación clínica, sin nota privada al paciente | `get_clinical_test`, formatter | lifecycle, access, demo | I/D | Cumplido y probado con dobles explícitos | Integrar relación de plataforma |
| U/E | U §6.3; E §7.3 | PATCH whitelist, null y bloqueo tras review | `edit_clinical_test` | lifecycle y sondas G03/G04 | I/sondas HTTP | Parcial | null no limpia, PATCH vacío acepta y edición sin evento de auditoría |
| U/E | U §6.4; E §7.4 | DELETE deja de publicar, invalida derivados | `delete_clinical_test` | lifecycle; scoring/series | I/A | Cumplido y probado con dobles explícitos | Separar soft delete de purga real |
| U/E | U §6.4; E §7.4 | Retención, legal hold, withdrawn y purga | Sin worker de purga/legal hold | No ejecutada | Código | No implementado | Definir política aprobada e implementar job sin borrar ahora |
| U/E | U §6.5; E §7.5 | Descarga privada y corta tras verificar acceso | `create_download_url`, storage | `test_full_upload_flow`, access; GET sin firma | I/D | Cumplido y probado con dobles explícitos | Verificar IAM/firma/Content-Disposition GCS real |
| U/E | U §7.1; E §8.1 | Listado clínico solo con relación, ready por defecto | `list_patient_clinical_tests` | clinician access/lifecycle | I | Cumplido y probado con dobles explícitos | Integración de clínica/relaciones externa |
| U/E | U §7.2; E §8.2 | Review, autor/momento y nota privada | `review_clinical_test` | demo y sondas G05/G06 | D/sondas HTTP | Parcial | Permite review de initiated y reemplazo por otro clínico; sin evento de review |
| U/E | U P0254/P0258; E P0173 | case/appointment pertenece al paciente | Campos aceptados sin resolver ownership | Sonda G01; lectura de ambas rutas | Sondas HTTP/Código | No implementado | Conectar registro autorizado; no aceptar asociaciones sin verificación |
| U/E | U §2; E §4 | Fechas clínicas válidas/no futuras | `clinical_dates.py`, DTO | F05 parametrizados; upload metadata | A/I | Cumplido y probado con dobles explícitos | Mantener reloj/formatos en clientes |
| U/E | U P0057; E P0067 | PDF/JPEG/PNG/HEIC válidos y límite configurable | `file_validation.py::validate_document`, config | documentos, `test_supported_image_content` | A/I | Parcial | PDF real E2E; imágenes/HEIC no se demostraron E2E cloud |
| U/E | U §9; E §11 | Hash/tamaño/MIME/magic/parseo y rechazo cerrado | worker + file_validation | cinco negativos reales y AV anterior | I/A/AV anterior | Cumplido y probado con dobles explícitos | Scanner principal demo es doble; ampliar corpus |
| U/E | U §9; E §11 | Antivirus real disponible/firmas mantenidas | `ClamAVScanner` | 6 anteriores; no ejecución actual | AV anterior | Parcial | Renovación, disponibilidad/alertas y política operacional |
| U/E | U P0294/P0694; E §2 | GCS V4 privado, precondiciones, generaciones e IAM | `services/storage.py` | argumentos con stub; gateway | A/D | Bloqueado por dependencia externa | Bucket exclusivo/credenciales autorizadas y pruebas cloud |
| U/E | U §2.2; E errores | Errores estables sin contenido sensible | `main.py::input_error`, errores DTO | `test_openapi_error_envelope_matches_actual_422` | A/I/D | Parcial | 422 estructurado vigente difiere de detail[] original; aprobar contrato |
| U/E | U §2 y §9; E §11 | Rate limits/pending/quota y Retry-After | auth limiter/uploads/config | `test_rate_limit_is_shared_and_retry_after_is_present`, quota/reprocess | A/I | Parcial | No hay cuota total de bytes/plan; verificar cada rama 429 |
| U/E | U §8; E §9 | Mongo e índices únicos por tenant | `database.py::init_indexes`, tenancy | `test_mongo_authenticated_replica_indices_validators` | I | Cumplido y probado con servicios reales | Solo base nueva; migración legacy requiere DBA |
| U/E | U P0888 | Idempotency TTL 24 h y outbox separado | Fingerprints/jobs embebidos | concurrencia/replays | I | Parcial | No colección/TTL genérico; acordar retención de claves |
| U/E | U P0892; E P0429 | EXIF sensible eliminado o no expuesto | Validación de imagen sin sanitizador EXIF completo | Sin prueba de saneamiento | Código | No implementado | Decidir original inmutable vs copia saneada con privacidad |
| U/E | U §9; E §11 | TLS y cifrado en reposo | Infraestructura externa | No certificada | Código | Bloqueado por dependencia externa | El Docker local HTTP no acredita cifrado cloud |
| U/E | U §10; E §12 | Cinco fases de carga completas en staging | Backend parcial + clientes ausentes | I/D no móviles | D/I | Parcial | GCS, móviles, monitoreo/retención y staging |
| U/E | U P0917; E §10/P0455 | Cola Drift offline y copia privada durable | Flutter fuera de este módulo | No ejecutada | Código | Pertenece al frontend | Drift, WorkManager/BGTaskScheduler y reanudación foreground |
| U/E | E §10 P0402–P0419 | Campos cola, SHA previo y borrado del path exacto | Cliente Flutter | No ejecutada | Código | Pertenece al frontend | Implementar/checksum/reintento de limpieza local |
| U/E | U P0918; E P0456 | Interrupción tras PUT sin duplicado | API/worker + cliente futuro | replays/concurrencia; sin caída móvil | I/A | Parcial | E2E iOS/Android con interrupción y misma intención |
| U/E | U P0919–P0923; E P0457–P0461 | Siete escenarios de aceptación completos | Dominios carga/acceso + móvil | negativos/tenancy/scanner; no móviles | I/D/AV anterior | Parcial | No declarar aceptación de staging por tests locales |

## Documento Maestro: extracción y esquema

| Documento | Sección | Requisito | Archivo/función | Prueba | Evidencia | Estado | Acción pendiente |
|---|---|---|---|---|---|---|---|
| M | §1.2/§3 | Confirmación humana antes de puntuar | `extractions.py::confirm_extraction` | confirmation rules, proposal immutable | I/D | Cumplido y probado con dobles explícitos | Puerta clínica de parámetros sigue pendiente |
| M | §3.3 | Estados upload/extraction independientes | `workers/processing.py`, extractor | safe_storage_does_not_wait_for_ai; F05 | I/A/D | Cumplido y probado con dobles explícitos | No confundir archivo seguro con IA exitosa |
| M | §3.2/P0221 | Cloud Tasks/PubSub + outbox de etapas | Outbox embebido Mongo y poller | retry/lease/restart anteriores | I | Parcial | No hay transporte cloud ni job independiente de scoring |
| M | §5.1/§5.2 | LLM multimodal lee documentos reales | `MultimodalProvider`, provider None productivo | provider test por contenido | D/A | Bloqueado por dependencia externa | Seleccionar proveedor, contrato y credenciales |
| M | §5.2.2 | HEIC→JPEG/raster/rotación/recorte/lotes | No preprocesador LLM completo | Sin prueba suficiente | Código | No implementado | PDFium de demo solo renderiza reportes; no confundir con pipeline IA |
| M | §5.2.3–4 | Clasificación y segunda llamada estructurada | `run_extraction_pipeline`, ProviderOutput | schema/flujo del adaptador test | I/D | Parcial | Protocolo existe; dos llamadas/modelo no implementados |
| M | §5.2.5 | Validación independiente, confianza efectiva cero si inválido | extractor/references/dates | F02–F05 | I/A | Cumplido y probado con dobles explícitos | Medir datos de proveedor real |
| M | §5.2.7 | Propuesta, versiones y persistencia | `run_extraction_pipeline` | proposal immutable/reprocess | I/D | Cumplido y probado con dobles explícitos | Campos meta extendidos aún faltan |
| M | §5.2.8 | Descubrir extracción por polling/push | GET extraction/status | demo polling | D | Parcial | Polling funcional; push y política cliente pendientes |
| M | §5.2/P0431 | Contenido como dato, salida estricta y escape | ProviderOutput y `_xml_escape` | schema y PDF | A/P | Parcial | No hay prompt real enviado ni evaluación de inyección multimodal |
| M | §5.3.2 | Confianza declarada/efectiva y umbrales | ConfidenceScores y confirm guards | F03/low_confidence_ack | I/A/D | Cumplido y probado con dobles explícitos | Presentación por bandas pertenece también a UI |
| M | §5.4 | PDF multipanel, unión de marcadores | extractor/confirm | multi_panel y diez marcadores/seis paneles demo | I/A/D | Cumplido y probado con dobles explícitos | Corpus multipanel real pendiente |
| M | §5.4/P0475 | Fechas distintas por panel y multiple_dates | Modelo admite fechas; detector limitado | No prueba E2E de multiple_dates | Código | Parcial | Generar bandera y semántica test_date más antigua |
| M | §5.4/§6.2 | Cualitativos/ordinales preservados y mapeados | Modelo expone campos; pipeline numérico | Sin flujo completo | Código | Parcial | Extracción/value_text/ordinal y banderas requieren implementación |
| M | §5.4 | Censura < / > sin perder literal | catalog normalizador y PDF | conversiones/censura en checks | A | Parcial | Censura existe; ampliar E2E y presentación literal left/right |
| M | §5.4/P0485 | Cotejo nombre/documento de otra persona | identity_confirmed manual; sin cotejo | No prueba de cotejo real | Código | No implementado | patient_stated e identity_match, UX y política aprobada |
| M | §5.5.1 | Resolver nombre exacto/sinónimos/fuzzy | `catalog.py`; provider exige marker_code | Sin prueba de resolver nombres completo | Código | No implementado | No delegar canonicidad a un código inventado del modelo |
| M | §5.5.2 | Conversión determinista, raw y factor | `catalog_service.validate_and_convert` | 12 conversiones preservadas, F04 | A/I | Cumplido y probado con dobles explícitos | Catálogo clínico ampliado y corpus multilenguaje |
| M | §5.5.3 | Prioridad documental, catálogo y ausencia explícita | `references.py`, scoring | F02/F04 y demo incompleta | I/A/D | Cumplido y probado con dobles explícitos | Rangos catálogo por edad/sexo no implementados |
| M | §5.6 | Retry/backoff/exhaustion, proveedor caído sin bloquear carga | `processing.py::run_once` | worker retries/fencing/exhaustion | I | Cumplido y probado con dobles explícitos | IA real, backpressure y concurrencia global aún no |
| M | §5.6/P0520 | Un retry por schema inválido + raw con TTL | Excepciones genéricas/jobs; proposal raw | schema unitarios | A/Código | Parcial | Política diferenciada y retención efectiva de raw |
| M | §5.6/P0524 | Cero marcadores no llega a confirmación y se trata como unreadable | extractor levanta Incomplete extraction; worker reintenta | schema/inspección | A/Código | Parcial | Se impide confirmar vacío, pero acaba como fallo/retry, no unreadable según spec |
| M | §5.7 | Corpus 150/15 emisores y métricas bloqueantes | `evaluation.py` sin corpus autorizado | empty_evaluation_does_not_claim_accuracy | A | Bloqueado por dependencia externa | Anotar 60 sangre/30 orina/30 imagen/30 difíciles; no sustituir por WQINT |
| M | §5.7.2 | Cobertura95/valor99/unidad99/rango97/clasificación98/alucinación≤0.2/calibración | evaluador parcial | No medición real | Código | No evaluable | Proveedor+corpus y reporte por bandas |
| M | §5.7.3 | Smoke20/CI y correcciones >10% alertan | Sin CI/calidad operacional completa | No ejecutada | Código | No implementado | Automatizar evaluación por versión y alertas |
| M | §6.1 | JSON canónico versionado completo | `models/extraction.py` | schema/lifecycle | A/I | Parcial | Faltan issuer, patient_stated, description desde provider y meta extendida |
| M | §6.2 | Marcadores con raw/canonical/ref/confianza/procedencia/edición | MarkerItem y normalizador | F03/F04 y demo HTTP | I/A/D | Cumplido y probado con dobles explícitos | LOINC/sinónimos y cualitativos incompletos |
| M | §6.3 | Imagen: modalidad/región/técnica/hallazgo/conclusión | provider/model sin bloque imaging completo | No ejecutada | Código | No implementado | No fabricar informe de imagen ni certificar placeholder |
| M | §6.3 | DXA con T/Z/DMO y pilar hueso | Sin DXA en catálogo actual | No ejecutada | Código | No implementado | Catálogo/esquema clínicamente aprobados |
| M | §6.4 | ~70 marcadores, Mongo versionado y parámetros por edad/sexo | Catálogo ilustrativo de diez en código | integridad/version/hash | A/Código | Requiere aprobación clínica/legal/producto | Ampliar/revisar catálogo y almacenamiento versionado |
| M | §6.5 | Versiones independientes y FHIR futuro | Campos de versión/LOINC nullable | reproducibilidad/metadata | I/A/D | Parcial | Render versiones antiguas; FHIR fuera de v1, no exigible como fallo |

## Documento Maestro: confirmación, scoring y reporte

| Documento | Sección | Requisito | Archivo/función | Prueba | Evidencia | Estado | Acción pendiente |
|---|---|---|---|---|---|---|---|
| M | §7.1 | Paciente confirma; clínico valida/corrige sin cambiar archivo | confirm/validate | complete_extraction, clinician correction y demo | I/D | Cumplido y probado con dobles explícitos | Revisar relación entre clinically_validated y review según producto |
| M | §7.2 | Edición/adición/eliminación y ack de baja confianza | confirm_extraction | rules/low_confidence_ack | I/A | Cumplido y probado con dobles explícitos | UI de cotejo/identity mismatch pendiente |
| M | §7.3 | Propuesta inmutable, original y quién/cuándo | proposal/history/audit | proposal immutable/correction | I/D | Cumplido y probado con dobles explícitos | No equivale a WORM ni auditoría forense completa |
| M | §7.3 | Operación por marker/emisor/prompt y unmapped | Sin panel/agregador operacional | No ejecutada | Código | No implementado | Métricas y responsables |
| M | §7.4.1 | GET propuesta al paciente, confirmada al clínico | `get_extraction` | extraction_rules/access | I | Cumplido y probado con dobles explícitos | Cliente debe esperar queued/extracting |
| M | §7.4.2 | Confirmación idempotente y extraction_id vigente | `confirm_extraction` | confirm_rules/F07 | I/A | Cumplido y probado con dobles explícitos | Scoring actual síncrono en transacción difiere del encolado propuesto |
| M | §7.4.3 | Reprocess archiva/invalida y limita intentos | `reprocess_extraction` | reprocess rules/limit | I | Cumplido y probado con dobles explícitos | Política operativa para jobs terminales |
| M | §7.4.4 | Rechazo clínico invalida serie/score; nota privada | `validate_extraction_clinician` | clinical rejection/invalidations | I/A/D | Cumplido y probado con dobles explícitos | Integración con plataforma de notas |
| M | §8/P0858 | Parámetros aprobados antes de clínicos reales | publication gates/stamps | F01 todas superficies | A/I | Requiere aprobación clínica/legal/producto | Puerta técnica existe; firma clínica no se obtuvo |
| M | §8.1/§8.2 | Subscore determinista y límites correctos | `ScoringEngine.calculate_subscore` | reference formula + F02 | A | Cumplido y probado con dobles explícitos | Fórmula preservada; no significa validación médica |
| M | §8.2.4 | Cualitativo ordinal configurable | Sin motor ordinal completo | No ejecutada | Código | No implementado | Esquema/catálogo ordinal con aprobación |
| M | §8.3 | Pesos de cuatro pilares y cobertura | scoring/catalog | scoring flow y reporte demo | A/I/D | Requiere aprobación clínica/legal/producto | Pesos/denominadores del catálogo reducido no cierran catálogo propuesto |
| M | §8.4 | Última medición válida por código, ventana calendario | eligible_markers | calendar_window y full_scoring_flow | A/I | Cumplido y probado con dobles explícitos | Decisión ventana por marcador sigue pendiente D3 |
| M | §8.4–5 | Cobertura, confianza, índice y penalización | compute_patient_score | fórmulas/coverage, demo | A/I/D | Cumplido y probado con dobles explícitos | Validación clínica de umbrales y fórmula |
| M | §8.6 | Banderas con severidad/valor/límite, sin escalado | calculate_subscore/ScoreFlag | scoring tests y tres flags demo | A/D | Parcial | JSON flag no contiene límite explícito; PDF lo muestra en tabla de resultados |
| M | §8.8 | Snapshots nuevos, versiones, contributions y exclusiones | scoring + append-only facade | D01/D02, same_input, incomplete | A/I/D | Cumplido y probado con dobles explícitos | No orden global con relojes divergentes ni WORM físico |
| M | §8.8 | Recálculo masivo sin sobrescribir/distribuciones | `scripts/recompute_scoring.py` | bulk_recompute_dry_run_vs_apply | I | Parcial | Dry/apply propio probado; comparación de distribuciones y scheduler faltan |
| M | §9.1 | Ficha/listado clínico con lab_index/banderas | React no implementado aquí | No ejecutada | Código | Pertenece al frontend | Integrar pestaña/cabecera/listado con permiso servidor |
| M | §9.2 | Cabecera paciente/examen/tipo/estado/original | get_lab_report y PDF | D/V | D/P/V | Parcial | Identificación por ID; issuer/descripción no llegan del extractor |
| M | §9.2 | Cuatro pilares, cobertura/confianza/desglose | get_lab_report + PDF | export y demo suficiente | I/D/V | Cumplido y probado con dobles explícitos | Puntaje solo sintético permitido en test |
| M | §9.3 | Tabla agrupada, valor/unidad/rango/fuente/estado/delta/subscore/origen | _result_row/_build_lab_report_pdf | report tests, P y D | I/A/D/V | Cumplido y probado con dobles explícitos | Idiomas y estados cualitativos/censura completos pendientes |
| M | §9.3 | Modos examen y agregado coherentes | get_lab_report | lab_report_endpoint_19 | I | Cumplido y probado con dobles explícitos | Revisión de borde temporal bajo gran histórico |
| M | §9.4 | Series por marcador/pilar/cobertura y cambios de versión | get_marker_series/get_lab_report | marker_series, report tests | I/D | Parcial | PDF solo resumen primera/última; revisar límites de ventana e histórico >200 snapshots |
| M | §9.4 | Gráfico con banda temporal y selector | React | No ejecutada | Código | Pertenece al frontend | No confundir tabla de evolución PDF con gráfico interactivo |
| M | §9.5.1 | Payload resuelto en servidor y nulabilidad | get_lab_report | exact JSON de GET + F01/F02 | I/D/A | Cumplido y probado con dobles explícitos | Motivo global de score:null no es campo explícito |
| M | §9.5.2 | Serie autorizada y sin acceso paciente a score | get_marker_series | markers/access | I | Cumplido y probado con dobles explícitos | Consumir unidades y referencias en cliente |
| M | §9.5.3 | Score vigente e histórico; error sin score | get_lab_score | no_score_available/scoring_flow | I | Cumplido y probado con dobles explícitos | No prometer una API de algoritmos históricos inexistentes |
| M | §9.5.4 | PDF desde mismo payload por endpoint, ready/descarga/replay | export_lab_report | export endpoint y demo | I/D | Cumplido y probado con dobles explícitos | GCS real sigue bloqueado |
| M | §9.5.4/P1266 | Pie en cada página: paciente/fecha/clínico/versiones/leyenda | _build_lab_report_pdf.footer | ocho regresiones + siete páginas revisadas | P/D/V | Cumplido y probado con dobles explícitos | Ampliar corpus tipográfico; no afirmar accesibilidad PDF/UA |
| M | §9.2/§6.3 | Hallazgos imagen en reporte/PDF | get_lab_report placeholder imaging | No caso clínico sintético soportado completo | Código | No implementado | Extender contrato canónico antes de probar modalidad/región/técnica |
| M | §9.2 | Correcciones y notas privadas conservadas | validate/review/audit | demo y patient detail sin nota | D/I | Cumplido y probado con dobles explícitos | No exportar automáticamente notas privadas |
| M | §10 | Pantallas/polling/cola/confirmación durable del paciente | Flutter/Drift | No ejecutada | Código | Pertenece al frontend | Persistir ediciones y claves, backoff; sin puntaje al paciente |
| M | §11.1–4 | Colecciones/índices y tenant | database.py y fachada | índices/validator/unique | I | Parcial | Índices funcionales base probados; catálogo y todos los índices de monitorización no completos |
| M | §11.5 | Transacciones, invalidación y única extracción activa | processing/atomic_write | rollback/writeconflict/reprocess/fencing | I | Cumplido y probado con servicios reales | Efectos externos siguen al menos una vez; no exactly once |
| M | §11.5/P1420 | Conciliación periódica de huérfanos/atascos/snapshots | Sin job periódico | No ejecutada | Código | No implementado | Diseñar reporte y reparación revisable antes de operación real |

## Privacidad, fases, aceptación y transversales

| Documento | Sección | Requisito | Archivo/función | Prueba | Evidencia | Estado | Acción pendiente |
|---|---|---|---|---|---|---|---|
| M | §12.2 | Consentimiento de almacenamiento separado de IA | ai_consent upload y worker | safe_storage_does_not_wait_for_ai | A/I | Parcial | Consentimiento por carga existe; preferencia/revocación por paciente no |
| M | §12.2 | Transparencia, retirada y efecto registrado | Sin endpoints de consentimiento/revocación | No ejecutada | Código | Requiere aprobación clínica/legal/producto | Base de tratamiento y política; luego implementar |
| M | §12.3 | Minimización y ausencia de contenido en logs | provider recibe bytes/MIME; logs acotados | security/errores/redacción demo | A/D | Parcial | Adaptador real, páginas mínimas y verificación operativa de logs |
| M | §12.3 | Retención raw/intermedios efectiva | Sin TTL/purge operacional completos | No ejecutada | Código | No implementado | Política de plazos y job acotado; no borrar en esta tarea |
| M | §12.4–6 | Proveedor/DPA/no entrenamiento/región/DPIA | Acuerdos fuera del repositorio | No aportados | Fuentes | Requiere aprobación clínica/legal/producto | Validar con responsables; esta matriz no es dictamen jurídico |
| M | §12.7 | No diagnóstico/terapia/acción automática sobre paciente | Rol y leyenda; sin motor de escalado | patient403 y PDF | I/D/P | Cumplido y probado con dobles explícitos | Mantener restricción al integrar plataforma |
| M | §12.8 | Seguridad de cuarentena y acceso a cada petición | storage + auth | unsigned403/negative files/access | I/D | Cumplido y probado con dobles explícitos | Validar IAM/red/TLS reales |
| M | §12.8/P1491 | Eventos inmutables de todas las acciones | audit.py, eventos de routers y scoring | audit/application append-only/demo | A/I/D | Parcial | Metadatos heterogéneos, no registro completo por request ni WORM |
| M | §12.8 | Derechos/portabilidad/supresión y segregación interna | GET JSON/soft delete; sin servicio de derechos | No prueba integral | Código | Parcial | Export de titular, permisos operaciones, purga/retención aprobadas |
| M | §13.1 | Fase 0: catálogo/corpus/proveedor/DPIA/modelo aprobados | Artefactos preliminares, sin aprobaciones | No ejecutada | Fuentes/Código | Requiere aprobación clínica/legal/producto | No cerrada por aprobación de pruebas sintéticas |
| M | §13.2 | Fase 1: siete escenarios staging de carga | Backend + clientes/cloud faltantes | I/D | I/D | Parcial | Ver filas U/E de cinco fases |
| M | §13.3 | Fase 2: pipeline completo, schema y evaluación | extractor/model/evaluation | A/I/D | A/I/D | Parcial | Provider/preproceso/esquema extendido/corpus |
| M | §13.4 | Fase 3: confirmación app/validación/panel de operación | Backend confirma, UI/panel no | demo y lifecycle | D/I | Parcial | UI durable y métricas de correcciones |
| M | §13.5 | Fase 4: scoring revisado/explicable/recálculo | scoring/gates/batch | A/I/D | A/I/D | Parcial | Aprobación clínica y distribución antes/después |
| M | §13.6 | Fase 5: ocho secciones/portal/accesibilidad | Reporte API/PDF; React ausente | D/V | D/V | Parcial | Frontend accesible, imágenes y evolución gráfica |
| M | §13.7 | Fase 6: observabilidad/conciliación/privacidad/E2E | health, tests y leases | I/D; sin plataforma ops | I/D | Parcial | Alertas, staging móvil, métricas reales y retención |
| M | §13.8 | Aceptación 27 marcadores, p90≤90s y score<10s | Demo diez marcadores sin benchmark | No medición estadística | D | No evaluable | Catálogo/corpus/clientes y prueba de rendimiento representativa |
| M | §13.8 | Rechazo/carta/proveedor caído/clínico no autorizado | extract/validate/auth/worker | históricos ports y retries | I/A | Cumplido y probado con dobles explícitos | No confundir con aceptación completa iOS/Android |
| M | §14 | Mitigar alucinación, error unidad, deriva y escalado | esquema/normalizador/snapshots/gates | pruebas parciales; sin corpus | A/I | Parcial | Plan operativo, responsables y evaluación real |
| M | §15 D1–D10 | Proveedor/base legal/ventana/pesos/índice/riesgo/retención/carga clínica/unmapped/escalado | Decisiones no aprobadas aquí | No se inventaron autorizaciones | Fuentes | Requiere aprobación clínica/legal/producto | Producto/clínica/protección de datos según cada decisión |
| T | §1 P0009 | client_id en cada acceso y transacción | tenancy + auth + objetos con hash tenant | tenant facade/real indices/access | I/A | Cumplido y probado con servicios reales | Mapping legacy y plataforma deben conservar frontera |
| T | §2 P0011–12 | Tier comercial antes de toda solicitud/módulo | Capability reports:export, sin motor de tiers | export_capability_denied | I/A | Parcial | Perfil comercial/facturación/flags por módulo y middleware |
| T | §2 P0012 | Visibilidad de componentes según perfil | React/Flutter | No ejecutada | Código | Pertenece al frontend | Consumir perfil real; nunca sustituir permiso servidor |
| T | §3 P0014–15 | RBAC granular en JWT por recurso | permissions/capabilities y dos roles clínicos | grants/role/capability tests | I/A | Parcial | Jerarquía Admin/Auditor/Técnico y autogestión de personal ausentes |
| T | §4 P0017 | i18n dinámico sin cadenas hardcodeadas | Mensajes API/PDF en español/inglés fijos | No prueba de cambio de idioma | Código | No implementado | Catálogos centralizados y negociación de locale backend/PDF |
| T | §4 P0017 | Interfaz cambia idioma en tiempo real | React/Flutter no desarrollados | No ejecutada | Código | Pertenece al frontend | Diccionarios y traducciones aprobadas |
| T | §4 P0018 | Light/dark, tokens y accesibilidad de UI | Clientes web/móvil | No ejecutada | Código | Pertenece al frontend | No atribuir incumplimiento CSS al backend |
| T | §5 P0020 | API-first documentada y consistente entre clientes | FastAPI/OpenAPI, Demo HTTP | exact schema y 20 operaciones | I/A/D | Cumplido y probado con servicios reales | Negociar contrato de plataforma y extensiones comerciales |
| T | §5 P0020 | Escalado replicable según clientes | Docker dos workers, Mongo un nodo | concurrencia/leases | I | Parcial | Orquestación cloud, HA, cuotas/backpressure y pruebas de carga |
| T | §6 P0024 | Quién/qué/cuándo/dónde/resultado por evento | audit.py y eventos heterogéneos | audit_events de demo/append-only | A/I/D | Parcial | IP, User-Agent, verbo HTTP/status/correlación no sistemáticos |
| T | §6 P0024 | Persistencia especializada para auditoría | Mongo audit_events junto a dominio | No integración de collector | Código | No implementado | Servicio especializado y controles de acceso/retención |
| T | §6 P0026–27 | Retención por plan, firma/no repudio y write-only | Append-only solo fachada de aplicación | append_only_application_boundary | A | Parcial | WORM/firma, export forense, retención escalonada; DB readWrite no inmutable física |
| M/U/E/T | Conjunto | Cumplimiento completo de producto/plataforma | Alcance backend local | Todas las evidencias anteriores | D/I/A/V | Parcial | Nivel D no aprobado; roadmap en documento 20 |

## Contradicciones y decisiones que no se resolvieron arbitrariamente

| Fuentes/estado actual | Diferencia observada | Tratamiento en esta entrega | Decisión pendiente |
|---|---|---|---|
| M §2.4 frente a U §11/E §13 | Carga original excluye extracción; M amplía esa parte y mantiene fuera diagnóstico, ZIP/reemplazo y notas al paciente | Se aplica M como referencia funcional principal; no se etiqueta extracción como incumplimiento por estar excluida en la carga anterior | Congelar baseline documental de producto |
| M P0829/P1419 frente a implementación | Confirmación calcula scoring dentro de la transacción; M pide encolado por etapa | Se conserva conducta; demo demuestra funcionalidad, matriz la marca parcial | Revisar asincronía/latencia antes de ampliar catálogo |
| U P0082 frente a OpenAPI/error real actual | U pide detail[] nativo; backend documenta detail objeto INVALID_INPUT para no reflejar valores clínicos | No se revirtió F01–F07 ni la protección de errores; contrato real descrito en documento 15 | Aprobación/versionado de contrato con clientes |
| U P0378/P0405 y E P0209/P0215 frente a complete | Objeto se verifica en el worker después de complete; no HEAD síncrono; mismatches de body pueden ser 400 en vez de 409 | No se cambia semántica durante demo; status nunca autoriza borrado antes de verificación | Ratificar semántica y códigos exactos en contrato |
| U P0293/P0351 frente a initiate/refresh | Replay no renueva enlace automáticamente; refresh solo initiated, no failed | Documentado; cliente debe usar ruta de refresh para sesión válida | Aprobar reintento/recuperación de failed y expiración |
| M §§6.4/8 frente al catálogo actual | Catálogo reducido en código, algunos nombres/pesos diferentes del modelo amplio ilustrativo | No se inventaron ni cambiaron valores/rangos/pesos; puntuación solo test | Revisión clínica y catálogo versionado completo |
| M §7.1/P0762 frente a review/validate separados | Validar extracción no marca por sí solo review del documento | Demo llama a ambas rutas y PDF final muestra ambos estados coherentes | Unificar semántica solo si producto lo aprueba |
| T P0024/P0027 frente a M P1446 | Auditoría rica/IP-UA/no repudio vs minimización estricta de datos de salud | Se documentan carencias de auditoría sin añadir contenido sensible a logs | Política conjunta de privacidad, seguridad y retención |
| T §4 frente a código actual | i18n exige recursos dinámicos; traducciones puntuales PDF no son i18n | Se corrigió legibilidad local, se mantiene brecha backend/PDF y UI separadas | Arquitectura de locale y traducciones de producto |

## Brechas adicionales reproducidas por HTTP

[sondas-brechas-http.json (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#sondas-historicas) registra seis observaciones **sin contarlas como pruebas aprobadas**. Se ejecutaron con una identidad sintética diferente de los escenarios PDF; no se alteraron esos reportes ni archivos. Son obligaciones pendientes del contrato original, no fallos de GCS o de un proveedor ausente:

| ID | Requisito original | Observación real | Implementación/acción propuesta |
|---|---|---|---|
| G01 | U P0254/P0258/P0291, E P0173 | Initiate aceptó con 201 un case_id sintético sin owner verificado | Resolver case/appointment contra el modelo autorizado y rechazar asociación no verificable; no inventar una colección de plataforma |
| G02 | U P0057/P0290, E P0067/P0172 | Initiate aceptó con 201 `synthetic.exe` declarado `application/pdf` | Validar coherencia extensión/MIME antes de firmar; el worker valida bytes reales, pero eso no satisface la regla de metadatos |
| G03 | U P0584/P0605, E §7.3 | PATCH notes:null respondió 200 conservando la nota; PATCH vacío respondió 200 | Diferenciar campo omitido de null, whitelist explícita y al menos un cambio según contrato |
| G04 | U P0619, E P0294 | PATCH de título persistió el cambio con 200 y añadió cero eventos de auditoría | Evento atómico minimizado, sujeto/recurso/resultado sin registrar contenido clínico libre |
| G05 | U P0820, E P0376 | PATCH review de un documento aún initiated respondió 200 | Exigir ready_for_review; cubrir estados rechazado/procesando/eliminado |
| G06 | U P0821/P0819, E P0375 | Otro clínico con relación válida respondió 200 y reemplazó reviewed_by; cero eventos de review | Replay estable para mismo revisor/intención, 409 para otro según contrato y evento inmutable |

No se corrigieron estas rutas en esta intervención: el encargo limita los arreglos a bloqueos concretos de la demostración y presentación PDF; el flujo demostrado sí terminó. Su cierre necesita regresiones propias y, para G01, integración de asociaciones de plataforma. Se priorizan antes de cualquier uso con pacientes reales. Una suite existente aprobada no acredita los bordes que no contenía.

No hay un porcentaje global de cumplimiento: mezclar pruebas unitarias, servicios locales, decisiones legales y pantallas ausentes produciría una cifra engañosa. Esta matriz relaciona obligaciones con evidencia y su límite concreto. Las propuestas de privacidad se atribuyen a los documentos originales; no se presentan como una interpretación jurídica actualizada ni como aprobación regulatoria.
