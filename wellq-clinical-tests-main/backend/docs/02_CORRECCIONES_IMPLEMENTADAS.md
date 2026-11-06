# Correcciones implementadas

> **Vigencia tras cierre focalizado F01-F07 (2026-11-05):** Se agregan exclusivamente las correcciones focalizadas F01-F07; formulas, pesos, 20 rutas y dependencias se conservan. [Detalle y evidencia](12_CIERRE_DEFECTOS_F01_F07.md).
> El contenido anterior al cierre se conserva a continuacion como referencia historica; esta nota y el documento12 prevalecen donde difieran.

**Fecha:** 2026-11-05 (America/Santiago). **Rama:** fix/wellq-backend-hardening. **Base:** fb8746cd42fe107bbda82dd92d3a4d11d545fd3e + cambios sin commit.

**Alcance:** backend; rutas de código relativas a wellq-clinical-tests-main/backend salvo indicación. **Método:** contraste estático, implementación y pruebas aisladas. **Límites:** sin servicios clínicos, datos reales, migraciones, despliegues ni validación clínica. No se modificó frontend.


## Matriz de problemas y cambios
| Problema comprobado | Antes | Después / archivos | Evidencia de prueba |
|---|---|---|---|
| Confianza de identidad | HS256 aceptado sin exp/iss/aud obligatorios; HTML firma localmente | RS256 exclusivamente, clave pública >=2048 bits, issuer/audience y claims requeridos, binding resource_id/rol, grants firmados; auth.py/config.py | checks/test_security.py |
| Documentos públicos | Montaje condicional de exports | Sin rutas estáticas clínicas ni fallback local; main.py/storage.py | anonymous_and_private_paths y lifecycle |
| Tenant | Consultas sin client_id | TenantDatabase filtra toda operación soportada, inserts anotados, cambios de tenant rechazados | tenant_facade_reads_and_writes |
| Logs | URI de conexión y valores de corrección en eventos | Mensajes técnicos acotados, audit.py con allowlist; historia clínica separada en clinical_result_history | lifecycle verifica ausencia de valores/notas en auditoría |
| Carga ficticia | complete compara metadatos; tarea espera y aprueba | complete persiste trabajo; worker lee bytes, valida, escanea y promueve generación | checks/test_processing.py |
| Fallback GCS | Error de credenciales/firma produce URL mock | Fallo explícito 503, sin archivo local público ni URL sintética productiva | storage_never_falls_back |
| Idempotencia | Replays consumen cuota/refrescos; claves incompletas | Fingerprint de initiate/confirm, respuestas de refresh cacheadas, unique indexes y serialización transaccional | replay/conflict/concurrent tests con doble transaccional |
| IA sintética | Marcadores fijos desde título | Interfaz de proveedor, lectura de documento verificado y JSON estricto; proveedor ausente => trabajo pendiente/fallido | provider_schema, no provider, test provider guard |
| Confirmación | Solo primer panel se desnormalizaba | Todos los paneles; validación de operaciones, identidad explícita y revisión de baja confianza | multi_panel_confirmation |
| Corrección parcial | Excepciones de score se ocultaban | Límite transaccional, historial de corrección y error que aborta ante cálculo fallido | lifecycle y modelo de rollback |
| Puntuación temporal | Se declaraba ventana sin filtrar | Ventana de meses calendario antes de escoger medición; excluye futuros, inválidos, no confirmados y padres borrados | calendar_window, ties, versions |
| Borrado | No invalidaba derivados | Invalidación y recálculo dentro de transacción; consultas ignoran padres borrados | lifecycle delete/series/report |
| Versionado nominal | --version solo renombraba algoritmo | Versión desconocida rechazada; snapshot conserva catálogo/huella/inputs/parámetros | reproducibility/version tests |
| Paginación | Cursor solo created_at con orden test_date | Tupla completa test_date, created_at y clinical_test_id | inspección estática; prueba HTTP específica pendiente |
| Reportería | Envelopes libres, posibilidad de snapshot obsoleto | DTO de respuesta; score vigente comprobado; replay PDF rechaza cambios de fuente | OpenAPI/lifecycle |
| Dependencias antiguas | Avisos conocidos en línea base | Versiones actualizadas, fijadas y probadas; informes before/after | pip-audit y pip check |
| Pruebas peligrosas | Guardia creaba un centinela antes de comprobar DB; bypass configurable | Guardia histórica bloquea antes de red/escritura; suite checks totalmente en proceso | 209 legacy skipped; 215 checks passed |

## Precisión respecto de la auditoría
config.py original exigía JWT_SECRET_KEY: no tenía fallback de secreto. La auditoría anterior atribuía un valor por defecto a ese archivo y no se reprodujo esa afirmación. El problema confirmado era el modelo HS256 compartido, la firma en cliente, los valores de demostración y los claims insuficientes.

## Compatibilidad
Se mantienen rutas /api/v1 y nombres principales de recursos. Cambios deliberados:
1. JWT HS256 y tokens sin tenant/grants ya no se aceptan.
2. /demo, /dashboard y /exports ya no se publican.
3. Idempotency-Key tiene longitud 8–200; objetos de entrada rechazan campos desconocidos.
4. initiate añade ai_consent=false; sin opt-in no se solicita IA.
5. confirmación exige identity_confirmed explícito si la identidad no está verificada y acknowledged_marker_codes para marcadores de baja confianza.
6. Reproceso devuelve queued y persiste trabajo; no ejecuta inferencia en la solicitud.
7. Cursor opaco cambia a tupla completa; cursores antiguos deben descartarse.
8. Export no devuelve almacenamiento local; una clave reutilizada tras cambiar fuente genera EXPORT_SOURCE_CHANGED.
9. Arranque no cambia índices ni catálogo. CLI exige --client-id y rechaza versiones inexistentes.
10. Catálogo sin aprobación no publica puntaje fuera del entorno test.

## Riesgos y controles
El aislamiento y las transacciones necesitan migración/provisionamiento revisados. Se preparó código y procedimiento, no se aplicaron datos/índices. Las pruebas de aplicación usan rollback en memoria: no acreditan atomicidad real de Mongo.
La actualización de dependencias es amplia por avisos comprobados; pip check y los casos aislados pasan. La imagen Python 3.11 no se construyó; la ejecución local fue Python 3.12. Debe verificarse en CI antes de desplegar.
