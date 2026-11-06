# Pendientes, bloqueos y matriz de resultados

> **Vigencia tras cierre focalizado F01-F07 (2026-11-05):** F01-F07 ya corregidos en aplicacion y pruebas aisladas; no confundirlos con bloqueos externos. Siguen pendientes Mongo/GCS/ClamAV reales, IA aprobada, corpus, catalogo clinico y operacion; no se utilizo Docker. [Detalle y evidencia](12_CIERRE_DEFECTOS_F01_F07.md).
> El contenido anterior al cierre se conserva a continuacion como referencia historica; esta nota y el documento12 prevalecen donde difieran.

**Fecha:** 2026-11-05 (America/Santiago). **Rama:** fix/wellq-backend-hardening. **Base:** fb8746cd42fe107bbda82dd92d3a4d11d545fd3e + cambios sin commit.

**Alcance:** backend; rutas de código relativas a wellq-clinical-tests-main/backend salvo indicación. **Método:** contraste estático, implementación y pruebas aisladas. **Límites:** sin servicios clínicos, datos reales, migraciones, despliegues ni validación clínica. No se modificó frontend.


## Matriz por fase
Los estados corresponden a la fase completa, no a la mera presencia de archivos.

| Fase | Problema encontrado | Corrección aplicada | Evidencia | Pruebas | Estado |
|---|---|---|---|---|---|
| 0 Línea base | Checkout frontend y afirmaciones históricas | Rama independiente desde origin/main local coincidente, comparación de fuentes y baseline | 01/02; commit base fb8746c | Git y hashes | Completada y verificada |
| 1 Seguridad | HS256/claims, archivos públicos, sin tenant | Frontera RS256, tenant facade, permisos/capability, rutas retiradas, CORS/logs/límites | auth.py, tenancy.py, main.py | checks/security, lifecycle | Parcial |
| 2 Almacenamiento | Validación y firmas simuladas | Adaptador GCS sin fallback, bytes/hash/tipo/parseo/ClamAV/promoción y borrado local seguro | storage.py, file_validation.py, uploads.py | checks/processing | Parcial |
| 3 Asincronía/idempotencia | Trabajo en proceso y replays inconsistentes | Outbox embebido, lease/fencing/retry/backoff, claves/fingerprints/índices/transacciones | workers/processing.py, transactions.py | aplicación con dobles; Mongo real bloqueado | Parcial |
| 4 IA real | Extracción fija por título | Pipeline sin valores fijos, protocolo/JSON/procedencia/guardias | extractor.py, evaluation.py | esquema, fallo, proveedor test explícito | Bloqueada por dependencia |
| 5 Catálogo | Diez marcadores ilustrativos mutables | Congelación defensiva, hashes, no seed al arranque, no finitos | catalog.py | conversiones preservadas | Parcial |
| 6 Confirmación clínica | Notas expuestas y actualizaciones parciales | Whitelist, revisión explícita, todos los paneles, historial separado y transacción | extractions.py, clinical_result_history | lifecycle y rollback modelado | Parcial |
| 7 Scoring | Ventana no aplicada, borrados vigentes, versión nominal | Filtro real, invalidación/recálculo, manifests y versión desconocida rechazada | scoring.py, batch CLI | casos temporales/fórmula/reproducibilidad | Parcial |
| 8 Reportería | Score obsoleto, descarga local abierta | Envelopes, coherencia vigente, GCS privado, replay por fuente | clinical_tests.py, reporting.py | JSON/PDF/hash/permisos con dobles | Parcial |
| 9 Datos | Índices sin tenant y cambios automáticos | Esquema explícito vacío, chequeo startup y plan reversible | database.py y documento 09 | fachada y estático; DB real bloqueada | Parcial |
| 10 Reorganización | Carga/seguridad mezcladas en router | Extracción de uploads, tenancy, auditoría, transacciones, validación y worker | módulos nuevos sin microservicios | suite aislada + Ruff | Completada y verificada |
| 11 Transversales | Auditoría con valores, capacidades sin frontera | Metadatos acotados, grants externos, consentimiento inicial, append-only aplicación | audit.py, auth.py | seguridad/lifecycle | Parcial |
| 12 QA final | Suite live insegura y sin evidencia actual | 215 casos aislados aprobados, 209 históricos bloqueados, JUnit/OpenAPI/audit | 08 y archivos de resultados | sin fallos en conjunto ejecutado | Parcial |

## Qué impide cerrar cada fase parcial
1. **Identidad y tenant:** autoridad definitiva/parámetros de confianza y mapping/migración de registros legacy todavía faltan. No se declara seguridad productiva completa.
2. **GCS y escaneo:** falta cuenta/bucket/IAM/credenciales y ClamAV reales con documentos de prueba autorizados. No se ha probado promoción/firma en cloud.
3. **Atomicidad y operación:** motor Docker no disponible, sin replica set de prueba; transacciones/índices/caídas reales no verificados. Transporte Cloud Tasks/Pub/Sub no seleccionado/implementado. Sin conciliación/GC y sin procedimiento de reactivar jobs terminales.
4. **Multimodal:** proveedor aprobado, contrato de privacidad, credenciales, adaptación concreta, soporte PDF y corpus autorizado. Sin medición de umbrales ni clasificación/identidad automática completa.
5. **Clínica:** documento maestro completo, catálogo ampliado, rangos/pesos por edad/sexo y aprobación profesional. No se añadieron valores médicos inventados.
6. **Consistencia:** pruebas reales de rollback/write conflict/fencing; migración y revisión de política de consentimiento/historia.
7. **Scoring:** aprobación clínica, disponibilidad de implementaciones históricas y scheduler periódico. Se rechaza snapshot vigente cuando cambió el día/fuente; no hay recomputación diaria automática.
8. **Reportes:** validación GCS y transacciones reales; nested DTO de reporte mantiene secciones dict extensibles que deben concretarse antes de generar clientes exhaustivos.
9. **Datos:** backup/mapping/aprobación DBA; no se aplicó migración ni recálculo.
11. **Privacidad y comercio:** retención por plan, WORM/firma/auditoría física, consentimiento revocable y taxonomía de capacidades de plataforma. Cifrado/TLS/contratos no certificados.
12. **QA:** portar las 209 pruebas históricas a identidad/tenant/storage/provider explícitos y ejecutar contra infraestructura aislada; no se habilitó bypass.

## Otros pendientes de integración frontend
Los HTML demo no se editaron. Necesitarían autenticación externa, transferir bytes, encabezados idempotentes, campos review_note/marker_corrections, confianza como objeto y edición persistida. El backend no publica la demo.
React+TypeScript y Flutter+Dart+Drift siguen siendo tareas futuras. No se escribieron componentes, HTML, JS ni Dart.

## Condiciones de entrega
No listo para producción clínica ni para integración real con servicios aún inexistentes. Hay contratos y una base de desarrollo con dobles verificables. La siguiente aprobación útil es cerrar autoridad de identidad, fuente documental, entorno aislado y proveedores; no volver a afirmar “100%” por pasar pruebas sintéticas.
