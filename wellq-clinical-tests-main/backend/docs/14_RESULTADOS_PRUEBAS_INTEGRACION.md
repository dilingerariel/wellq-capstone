# Resultados de integración ejecutada

Fecha: 2026-11-05. Rama `fix/wellq-backend-hardening`; HEAD `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e` más cambios locales sin commit. Solo datos sintéticos y proyecto `wellq-int-39706292db88`. Preparación y comandos: [13](13_INTEGRACION_DOCKER_AISLADA.md). Dictamen y límites: [16](16_PENDIENTES_POST_INTEGRACION.md).

## Corridas y conteo

| Cohorte realmente ejecutada | Aprobadas | Fallidas/errores | Omitidas | Evidencia |
|---|---:|---:|---:|---|
| Primera integración real | 55 | 2 / 0 | 0 | [integration-first.xml](evidencias_integracion/integration-first.xml) |
| Integración tras D01/D02 | 57 | 0 / 0 | 0 | [integration-after-fixes.xml](evidencias_integracion/integration-after-fixes.xml) |
| Integración final ampliada | 59 | 0 / 0 | 0 | [integration.xml](evidencias_integracion/integration.xml), 83.71 s |
| Regresión general de aplicación, Python host 3.12.10 | 278 | 0 / 0 | 209 | [application-regressions.xml](evidencias_integracion/application-regressions.xml) |
| Primer ClamAV, muestra como comentario PDF | 5 | 1 / 0 | 0 | [clamav-first.xml](evidencias_integracion/clamav-first.xml) |
| Segundo ClamAV, cola con reintento anterior | 5 | 1 / 0 | 0 | [clamav-second.xml](evidencias_integracion/clamav-second.xml) |
| ClamAV final, daemon y firmas reales | 6 | 0 / 0 | 0 | [clamav.xml](evidencias_integracion/clamav.xml) |

No sumar corridas repetidas ni cohorts como cobertura única. Las 278 incluyen los 61 casos F01–F07 anteriores y dos regresiones nuevas (antes 276). Los 209 originales siguen omitidos por el guard; los ports se ejecutan explícitamente en otra suite. Las 171 históricas recuperadas en la tarea anterior no se volvieron a ejecutar aquí; su XML original permanece intacto y no se suma al total actual.

La suite Docker ampliada contiene 30 casos mapeados históricos, 17 casos de infraestructura/API/worker y 12 casos del archivo F01–F07/documentos (siete F y cinco negativos de archivo). Dos de los 30 son puros; los demás usan Mongo real. El escáner principal, objetos e IA son dobles explícitos. La cohorte ClamAV cambia únicamente el escáner a daemon real y conserva el doble de objetos. [runtime.json](evidencias_integracion/runtime.json) identifica todas las dependencias realmente instaladas en Python Docker 3.11.18, incluido MongoDB 7.0.43; instalar mongomock como dependencia dev no implica usarlo en estas pruebas de integración.

Sonda adicional de reinicio **aprobada**, fuera de pytest: [restart-probe.json](evidencias_integracion/restart-probe.json). Workers detenidos, job pendiente persistido, parada/arranque de API y dos workers, estado final terminado, archivo apto para borrar localmente y exactamente una extracción lógica. Ocho respuestas HTTP sintéticas capturadas en [frontend-examples.json](evidencias_integracion/frontend-examples.json); son ejemplos, no ocho pruebas adicionales.

## Infraestructura y operaciones verificadas

| Área | Evidencia concreta | Límite |
|---|---|---|
| Arranque | Build desde C:\Dev, API HTTP real, `/health` y `/ready`, Python 3.11, 20 operaciones y ErrorResponse 422 | Readiness no certifica GCS, IA ni scanner |
| Mongo | Autenticación, hello replica set, índices únicos compuestos del backend y validator client_id (error 121) | Replica set de un nodo; sin HA/failover |
| Tenancy | Fachadas separadas sobre Mongo real, aislamiento de lectura, duplicados y tenant inmutable | No se migraron registros legacy |
| Transacciones | Commit y rollback sobre dos colecciones, dos MongoClient independientes y WriteConflict real | Sin pruebas de pérdida de ack/red o desastre |
| Idempotencia | Dos clientes HTTP concurrentes en initiate y discard; una entidad/evento, cuerpo diferente en misma clave 409 | El helper HTTP reintenta acotadamente RETRYABLE_CONFLICT con la misma clave |
| Autorización | RS256 sintético; tokens inválidos y tenant/recurso/relación ajenos; permisos/capability; datos clínicos denegados al paciente | Sin SSO/autoridad productiva |
| Errores HTTP | 401, 403, 404, 409, 422, 429 por límite de reprocess y 503 por firmante inaccesible de upload | No se certifica rate limit global productivo; límite de test aumentado |
| Worker | Dos procesos; jobs reales, pending/running/done/failed, retry/backoff, agotamiento y lease expirado | Objetos e IA de prueba |
| Fencing y demora | Proveedor test demora 10 s; otra conexión cambia lease_token; sin extracción al perder lease, rollback real; recuperación posterior produce una | No evita llamadas/costes externos repetidos ni promete exactly once |
| Carga | PUT de bytes real a gateway, complete y polling de job, SHA/tamaño/MIME/magic/parseo, promoción privada modelada | No GCS ni firma IAM real |
| Contratos | OpenAPI estático igual a `app.openapi()` actual; HTTP Docker con 20 operaciones y errores 422; propuestas/series/reportes/PDF, nulos y roles | Cliente navegador aún sin puerto/origen configurado |

## Histórico: mapa individual de los 30

Mapa con origen `archivo:línea::caso`, port y resultado: [historical-matrix.md](evidencias_integracion/historical-matrix.md), versión estructurada [JSON](evidencias_integracion/historical-matrix.json). Fuente consultada sin modificar: `C:\Dev\wellq-auditoria-final\06_REGRESIONES_Y_PRUEBAS_HISTORICAS.md`.

**28 aprobados con Mongo/HTTP reales y dobles explícitos**: acceso clínico con/sin relación, corrección y validación, rechazo e invalidación, confirmación, propuesta inmutable/reprocess/carta, reglas/errores/límites, ciclo documental, reportes/vacíos, PDF/replay, series, recompute dry-run/apply, scoring y reproducción, upload completo. Ninguno certifica GCS o un modelo externo.

**Dos aprobados reclasificados como puros**: `test_same_input_gives_same_output` y `test_subscore_is_always_between_0_and_100`. Se importan y ejecutan sus funciones originales intactas desde una copia de referencia montada de solo lectura, sin activar el fixture inseguro. La clasificación previa de los 30 sobrestimaba los casos que necesitaban servicios; se conserva la auditoría anterior y se explica aquí la corrección.

Para estos 30: cero ports fallidos finales, cero pendientes de adaptación del port; **las variantes E2E con GCS/proveedor IA reales siguen pendientes para los 28 funcionales**. No se clasifican como bloqueados los ports ejecutados con dobles ni como cloud aprobados. Los ocho tests adicionales de título no pertenecen a estos 30: conservados, no ejecutados y pendientes de adaptación por contenido, propuesta en documento 16.

Cambios de dependencias/contratos al portar: RS256/tenant/relación/grants en lugar de HS256; transferencia real de archivo al gateway; Mongo propio y waits del worker; errores de enum inválido 422 INVALID_INPUT según DTO vigente; reprocess queued se espera hasta nuevo extraction_id. Se conservaron las aserciones de dominio actuales; no se reinstaló clasificación ficticia por título. Fuentes originales y guard de `tests/conftest.py` conservan sus hashes.

## Regresiones F01–F07

| ID | Prueba adicional contra estado real | Alcance explícito |
|---|---|---|
| F01 | Registro test no gana aprobación al activar variable; historial/snapshot rechazan procedencia no aprobada; puerta fuera de test no publica ni calcula sobre datos Mongo reales | Invocación de política en runner, API sigue ENVIRONMENT=test; cobertura HTTP extensa fuera de test permanece en los 61 casos aislados |
| F02 | Confirmación HTTP con glucosa unilateral incompleta; valor válido persistido, subscore null y motivo/exclusión coherentes | Sin alterar fórmulas ni inventar límites |
| F03 | Unidad inválida con provider_confidence .99 conserva confidence efectiva cero y no crea marcador puntuable | Entrada de proveedor sintético por contenido |
| F04 | Referencia documental y estado low llegan coherentes a extracción y serie clínica | HTTP/DB reales |
| F05 | Fecha futura de proveedor produce INVALID_CLINICAL_DATE; archivo verificado sigue permitiendo borrado local | No sustituye la fecha; proveedor sintético |
| F06 | download_pending con URL null persiste; replay tras recuperar firma conserva export_id, un registro y un evento | Firmante local explícito; no fallo real IAM |
| F07 | Dos confirmaciones discard concurrentes con misma clave devuelven respuesta equivalente, un evento; otro cuerpo 409 | Propuesta conservada, transacciones reales |

## Dos defectos pequeños de integración corregidos

**D01 — selección de snapshot dentro del mismo segundo.** `test_bulk_recompute_dry_run_vs_apply` insertaba el snapshot recompute, pero GET devolvía extraction_confirmed. `computed_at` truncado a segundos empataba; el desempate por `_id` entre procesos no preserva el orden de creación. Se retuvo precisión de microsegundos ISO UTC al crear snapshots nuevos. Regresión `checks/test_scoring.py::test_snapshots_keep_subsecond_order_across_client_object_ids` y port real batch aprobados. No se reescribieron snapshots históricos ni se implementó un reloj distribuido/orden global para escritores con relojes divergentes.

**D02 — contribuciones inestables tras corrección al mismo valor.** `test_recomputing_with_the_same_inputs_gives_the_same_score` fallaba porque updated_at cambiaba el orden de iteración/contribuciones, aun manteniendo valores y puntajes. Se recorren marcadores por código estable antes de agregarlos. Regresión `test_same_values_keep_contribution_order_after_correction` y port real aprobados. No se cambiaron fórmulas, pesos, rangos, redondeo ni endpoints; el orden de contribuciones ahora es determinista.

Único cambio productivo de esta tarea: esas dos líneas de scoring. `.dockerignore` agrega exclusiones del runtime/evidencias y `checks/test_scoring.py` las dos regresiones. No se modificaron requirements ni otros archivos previos. Los fallos iniciales se mantienen en XML como reproducción de los defectos, no se ocultaron como omisiones.

## Antivirus real y correcciones del arnés

Daemon registrado: **ClamAV 1.5.4**, firmas **28171**, fecha **2026-11-01**; [clamav-version.json](evidencias_integracion/clamav-version.json). Se usó la imagen oficial `clamav/clamav:stable` y volumen propio; actualización automática deshabilitada para esta corrida. No se redujo la base a una firma casera. El inventario registra su digest.

Se probaron limpio, EICAR inocuo y endpoint inaccesible mediante el scanner real; además los tres pasan por el worker con Mongo real y almacenamiento doble. Limpio queda ready_for_review y permite borrado; EICAR adjunto en PDF válido es rechazado con MALWARE_DETECTED y no permite borrado; scanner inaccesible permanece pendiente, DEPENDENCY_UNAVAILABLE y borrado deshabilitado. Sin consentimiento IA, extracción queda not_applicable.

Primera falla del arnés: EICAR añadido como comentario a un PDF no se detectó en ese formato con estas firmas, aunque el EICAR directo sí. El test exigía detección de una muestra no comprobada: se cambió a un adjunto `eicar.com` dentro del PDF y se añadió una aserción de detección directa del PDF completo antes del worker. No se cambió el scanner ni se debilitó el rechazo. El resultado también revela un límite del corpus: no afirmar cobertura universal de comentarios/representaciones de malware.

Segunda falla del arnés: un job pending de una ejecución anterior podía ser reclamado antes del job del caso actual. La prueba ahora mantiene la selección real de cola y procesa trabajos elegibles hasta observar que **su propio job** tiene un intento, con límite y aserciones de estado/error. No se borraron jobs ni se saltó la cola mediante mocks. Corrida final 6/6. Ninguno de estos ajustes requirió un cambio productivo.

## Calidad, preservación y entrega

Ruff limitado a F821/F822/F823 en integración y archivos tocados: aprobado. `pip check` host: sin dependencias incompatibles. `git diff --check`: sin errores de whitespace; advertencia LF/CRLF preexistente en storage.py. Warnings pytest/deprecaciones permanecen visibles: no se contaron como fallos ni se suprimieron para aparentar una ejecución limpia.

[preservation.json](evidencias_integracion/preservation.json) verifica 197 archivos de línea base: 194 intactos, tres cambios permitidos, cero ausentes, misma rama/HEAD. Incluye docs 01–12, evidencias F01–F07, pruebas históricas, frontend, requirements y catálogo sin cambios. No se escribió en la auditoría externa ni OneDrive. [delivery-manifest.json](evidencias_integracion/delivery-manifest.json) registra fuentes/hash/status Git; [sha256.json](evidencias_integracion/sha256.json) los hashes de evidencias.

Archivos nuevos: `integration/` (Compose, imagen, guardias, provisionamiento, adaptadores test, runner, tests, scripts y generador de informes), documentos 13–16 y `docs/evidencias_integracion/`. `.runtime` con claves/env se mantiene ignorado y fuera de la imagen. No hubo commit, push, merge ni modificación de frontend. Todos los servicios nuevos se detienen al cerrar; recursos y volúmenes quedan retenidos. La parada es acotada al proyecto propio, sin eliminar nada.

Resumen generado: [summary.json](evidencias_integracion/summary.json). Una repetición actualiza XML/evidencias; conservarlos antes de una nueva corrida si se necesita auditoría de cada intento. Para esta entrega se guardaron los intentos iniciales y posteriores por separado.
