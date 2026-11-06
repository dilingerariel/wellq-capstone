# Cierre de edición y revisión clínica — G03–G06

Fecha: 2026-11-05. Intervención focalizada de fase 2, sobre `fix/wellq-backend-hardening`, HEAD `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`. El trabajo anterior permanece sin commit. Este documento complementa las fotografías históricas 18, 20 y 22; no modifica sus evidencias.

## Estado inicial y requisitos contrastados

Se inspeccionaron Git status/diff y archivos sin seguimiento, código vigente, documentos 15, 18, 20, 22 y `docs/openapi.json`. El esquema inicial coincidía con la aplicación y contenía 20 operaciones clínicas. Se respaldaron 294 archivos inventariados, diff y artefactos PDF en `C:\Dev\wellq-phase2-backups\20261105-200004\`; ambos ZIP se comprobaron antes de modificar producción. [Referencia de respaldo](evidencias_g03_g06/baseline-pointer.json).

La línea base S01–S02 se verificó ejecutando sus 70 pruebas: todas pasaron. Su protección por verificador con fallo cerrado y la validación de archivos permanecen vigentes. No se introdujo un modelo de casos/citas ni una nueva identidad.

Se contrastaron las fuentes originales disponibles y sus extracciones locales, identificadas por nombre, versión y hash en el documento 18. P indica párrafo XML, no página:

| Fuente | Requisito aplicable |
|---|---|
| Especificación española de endpoints v1.0, P0584/P0590–0619 | PATCH actualiza campos presentes, requiere alguno; solo notas/asociaciones admiten limpieza; no editar tras revisión y registrar auditoría |
| Misma fuente, P0624–0635 | Propiedad, inexistencia, 409 ALREADY_REVIEWED y errores de asociación |
| Misma fuente, P0794/P0800–0834 | Revisar solo ready_for_review; autoría y fecha inmutables; replay del mismo clínico 200 y otro clínico 409; nota privada |
| Especificaciones inglesas (4)/(5), idénticas, P0282–0294 y P0364–0376 | Edición y auditoría antes/después; revisión, identidad y disponibilidad del documento |
| Documento Maestro WellQ v1.0, P0050/P0098/P0759–0763/P0791 y §12.8 | Confirmación/validación humana y trazabilidad; preservar autorías, evidencia y privacidad |
| Estándares transversales Alloxentric, P0009/P0013–0015/P0024–0027 | Tenant, identidad/permisos y auditoría aplicable; sin ampliar a auditoría comercial o forense |

Las instrucciones operativas de esta fase prevalecen sobre instrucciones que pudieran aparecer dentro de las fuentes de requisitos. Se mantuvo la separación vigente entre revisión documental y validación de extracción; no se cambió scoring ni se implementó una rectificación administrativa.

## Reproducción y causas

Las cuatro regresiones se escribieron antes de la corrección. [before.xml](evidencias_g03_g06/before.xml) contiene **4 fallas esperadas y 70 aprobaciones S01–S02**:

| Hallazgo | Resultado anterior observado | Causa |
|---|---|---|
| G03 | PATCH notes:null respondía 200 conservando la nota | Comprobación `is not None` confundía limpieza con omisión; tampoco se exigía un campo |
| G04 | Cambio de título 200 con cero eventos correspondientes | PATCH y review no llamaban al servicio de auditoría |
| G05 | Review sobre initiated respondía 200 | No se verificaba estado del upload ni aprobación de seguridad del archivo |
| G06 | Segundo clínico autorizado respondía 200 y reemplazaba reviewed_by | Actualización incondicional de revisor, fecha y nota |

El PATCH vacío también se cubre de forma independiente en las pruebas posteriores; en la reproducción combinada G03, la primera aserción de notes:null ya detectó el defecto. Una invocación inicial de pytest desde el directorio equivocado no recopiló pruebas; su diagnóstico se conserva en `collection-error.xml` y no cuenta como prueba funcional.

## Correcciones y decisiones de contrato

### PATCH

`EditClinicalTestRequest` exige al menos una propiedad y rechaza campos extra. `title`, `test_type` y `test_date` siguen siendo opcionales por presencia, pero su valor explícito no puede ser null. `notes`, `case_id` y `appointment_id` conservan null permitido. Los errores de entrada usan **422 INVALID_INPUT** y el envelope estructurado previamente aprobado; no se reintroduce `detail[]` de la especificación inicial.

El handler usa presencia explícita para notes/asociaciones: omitido conserva, null limpia y una cadena vacía válida de notes se almacena como tal. Se mantienen límites y fechas. Asociaciones efectivas se verifican con el verificador S01 incluso al editar un campo ordinario. Desvincular mediante null funciona; añadir una asociación sin verificador responde 503. Un examen revisado permanece bloqueado con 409 ALREADY_REVIEWED.

Se comparan valores antes de escribir. Un PATCH válido que ya coincide con el estado actual devuelve 200 sin cambiar updated_at ni emitir otro evento. Esta es idempotencia por estado para replays consecutivos, no una nueva garantía de exactly-once con historial de claves: PATCH no requiere Idempotency-Key y un replay tras cambios intermedios podría volver a aplicar su intención. No se inventó una versión de recurso ni un endpoint nuevo.

**Compatibilidad de propiedad:** se conserva el 404 del backend aprobado para paciente no propietario/otro tenant, aunque la especificación española menciona 403 para el primer caso. La consulta permanece acotada a propietario/tenant y no se agrega una búsqueda que revele existencia ajena. Los códigos 403/503 de asociaciones de S01 permanecen sin cambios, aunque la tabla PATCH original menciona 422 para asociación inválida.

### Revisión y revisor

Se exige `upload.status=ready_for_review`, documento no eliminado, `verified_at`, generación persistida y ambos controles de procesamiento aprobados. Ningún otro estado habilita revisión. Se conserva `review.status` separado de `upload.status`; reviewed no se convierte en un estado nuevo del archivo ni equivale a clinically_validated.

Primera revisión válida: revisor obtenido exclusivamente del JWT, fecha UTC y nota privada almacenados en el documento, con un evento de auditoría. Para el mismo revisor y misma nota, el replay devuelve el estado actual con 200 y conserva fecha, autoría, nota y un único evento. Otro clínico, o el mismo intentando cambiar su nota ya registrada, recibe **409 DOCUMENT_NOT_READY**, conforme al conflicto de revisión original. Cambiar una nota ya revisada requeriría un flujo formal de rectificación que no está definido ni implementado.

Estados initiated, object_uploaded, processing, rejected, failed, deleted y cualquier estado inválido responden 409 DOCUMENT_NOT_READY. Un documento soft-deleted del tenant, si el clínico tiene relación, responde ahora 409 en review como indica la especificación; el inexistente/otro tenant sigue respondiendo 404. Rol o relación no autorizados se deniegan antes de modificar. El default existente review_status=reviewed se conserva; no se hizo obligatorio silenciosamente un campo que el contrato actual permitía omitir.

La actualización incluye una condición de estado y se ejecuta dentro de `atomic_write`, cuya transacción ya serializa escrituras del paciente. No se reemplazó el mecanismo de concurrencia. Dos clínicos simultáneos producen un único ganador: el perdedor puede recibir un conflicto transitorio reintentable y luego 409 de dominio. No se rerunea silenciosamente toda la operación dentro del servidor. La revisión no modifica extracción, validación, marcadores, score ni PDF.

### Auditoría mínima y privacidad

Se reutiliza `audit()` y su colección existente append-only, dentro de la misma transacción que el dominio:

- `clinical_test_metadata_updated`: solo si cambian valores; lista ordenada de nombres de campos con `before_present` y `after_present`.
- `clinical_test_reviewed`: solo en la primera revisión; estado previo, sujeto autenticado, rol, recurso, fecha UTC, origen API y resultado success.

El tenant lo impone la fachada de base de datos. No se guardan valores previos/nuevos de notas, títulos u otros textos clínicos, ni hashes de esos textos. La comparación antes/después se minimiza a presencia y campo cambiado: permite saber que cambió un campo y si fue limpiado sin copiar contenido sensible al evento. La nota privada permanece solo en el registro de dominio, y nunca en la respuesta al paciente ni en el evento técnico. No se registran tokens, cuerpos completos, documentos, valores de laboratorio, secretos ni URLs firmadas.

No se encontró un identificador de correlación de petición ya instalado. No se amplió middleware para inventarlo en esta fase. Existe `_audit_denied_access` para otras rutas clínicas, pero no es un sink de seguridad independiente: dentro de una transacción rechazada también se revertiría. No se reutilizó para generar eventos falsos de éxito ni se abrió una transacción fuera de la política existente. **La auditoría duradera de rechazos y correlación queda pendiente** de una infraestructura apropiada, sin bloquear los eventos atómicos exitosos requeridos aquí. No se implementaron WORM, SIEM, firma, retención comercial ni servicios nuevos.

## Pruebas y evidencias

| Ejecución | Total | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|---:|
| Antes: cuatro defectos y baseline S01–S02 | 74 | 70 | 4 esperadas | 0 |
| Primera corrección: originales y S01–S02 | 74 | 74 | 0 | 0 |
| Nuevas y relacionadas de aplicación | 185 | 185 | 0 | 0 |
| Suite aislada completa final | 613 | **404** | **0** | **209** |
| Primer intento Docker | 65 | 61 | 4 del arnés | 0 |
| Docker final | 65 | **65** | **0** | **0** |

[Inicial posterior](evidencias_g03_g06/initial-after.xml), [relacionadas](evidencias_g03_g06/related-after.xml), [suite completa](evidencias_g03_g06/full-after.xml), [intento Docker conservado](evidencias_g03_g06/integration-attempt1.xml), [Docker final](evidencias_g03_g06/integration-after.xml). No sumar suites solapadas. Las 404 aprobaciones contienen las 356 anteriores y **48 nuevas regresiones** de edición/revisión. Se conservan las 209 omisiones históricas del guard y las advertencias de deprecación; no se habilitaron servicios antiguos.

Las pruebas nuevas cubren null/omisión/vacío, campos prohibidos, no-op/replay, asociación S01, restricciones tras revisión, propietario/tenant, roles y grants, notas privadas, ocho estados del upload, indicadores de seguridad incompletos, identidad de cliente rechazada, nota distinta, revisor distinto, extracción intacta y errores de auditoría antes/después del insert. El rollback aislado es un modelo en memoria; la prueba Docker correspondiente comprueba la transacción real por separado.

El primer intento Docker falló en cuatro expectativas del arnés: el helper HTTP reintentaba el 503 deliberado de auditoría hasta agotar su presupuesto y lanzaba una aserción antes de inspeccionar la respuesta. Se cambió únicamente esa prueba para observar el fallo una vez. Se preservaron XML y capturas del intento. No se corrigió código productivo para ocultar esas fallas.

La ejecución focalizada Docker comprende **22 casos nuevos**, las 30 verificaciones S01–S02, el lifecycle histórico de edición/revisión y 12 casos F01–F07/seguridad documental. Incluye exportación y replay de PDF; no se regeneró la auditoría visual completa. Mongo 7 autenticado, transacciones, API y workers son reales; almacenamiento/firma, IA, scanner y asociaciones son dobles explícitos ya declarados. Las identidades RS256 y los documentos son exclusivamente sintéticos.

[Capturas HTTP y eventos Mongo minimizados](evidencias_g03_g06/review-http-mongo.json) registran códigos, metadatos de review y eventos de estas dos operaciones, sin guardar respuestas clínicas completas. [S01–S02 por HTTP](evidencias_g03_g06/http-after.json) conserva evidencia separada. Los estados negativos se preparan explícitamente sobre registros sintéticos; la aceptación ready_for_review se obtiene mediante PUT de bytes, complete y worker reales con scanner test.

La sonda de fallos vive solo en `integration/adapters.py`, tras el guard de entorno/ownership: inserta o falla en la colección real durante la transacción y provoca abort. Se limita al recurso sintético indicado en `__integration_control`. No existe en el arranque de producción ni deshabilita permisos. Se comparan documento y eventos antes/después y se comprueba que un reintento sin el fallo produce una sola modificación y evento.

## OpenAPI y archivos intervenidos

Se conservan 20 operaciones clínicas, rutas, parámetros y respuestas exitosas. Solo cambia `components.schemas.EditClinicalTestRequest`: `minProperties=1` y tipos no nulos de title/test_type/test_date. `docs/openapi.json` se actualizó a la aplicación y el anterior se conserva como [openapi-before.json](evidencias_g03_g06/openapi-before.json). Los nuevos rechazos 409/422 ya pertenecen al envelope y categorías de error documentados; los detalles de semántica se explicitan arriba.

Existentes modificados en esta fase:

1. `app/models/schemas.py`: validación PATCH y esquema.
2. `app/routes/clinical_tests.py`: únicamente `edit_clinical_test` y `review_clinical_test`.
3. `app/services/audit.py`: admite el detalle minimizado metadata_changes.
4. `docs/openapi.json`: contrato actualizado.
5. `integration/adapters.py`: inyección de fallo de auditoría exclusivamente test.
6. `integration/bootstrap.py`: modo focalizado review-test.

Nuevos: `checks/test_edit_review.py`, `integration/edit_review.py`, `integration/Review.ps1`, este documento y `docs/evidencias_g03_g06/`. No se modificaron requirements ni dependencias. [Preservación y diferencias de OpenAPI](evidencias_g03_g06/preservation.json).

## Preservación y cierre

Se verificaron los 294 archivos de baseline: ninguno desapareció y solo los seis existentes enumerados cambiaron. La comparación AST de rutas identifica únicamente las dos funciones autorizadas. Frontend, scoring, catálogo, fórmulas, pesos, generador PDF, documentos 01–22 y sus evidencias anteriores conservan sus hashes. Los artefactos de la demo conservan sus bytes frente al ZIP previo.

No se cambió rama/HEAD ni se ejecutaron reset, clean, stash, commit, push o merge. `git diff --check` se comprueba al cierre; los cambios previos siguen presentes. El estado Git contiene trabajo acumulado anterior, por lo que no debe atribuirse todo el diff a esta fase.

Docker usa exclusivamente `wellq-int-39706292db88` y su DB/volúmenes/red existentes, sin puertos host. Los scripts se ejecutaron secuencialmente, sin Demo/DemoTests. Los helpers canónicos propios se reutilizaron por nombre y labels verificados; los intentos previos detenidos se conservaron. Compose recrea solo API/objetos/workers propios para cargar código. Los runners de esta fase se conservan, sin `--rm`, limpieza global ni eliminación de volúmenes. Los contenedores antiguos y OneDrive permanecen fuera del alcance; únicamente se inspecciona metadata del contenedor antiguo para confirmar identidad/arranque, nunca sus datos/logs. [Inventario final](evidencias_g03_g06/docker-final.json).

**G03, G04, G05 y G06 quedan corregidos y verificados dentro del alcance de esta fase.** Se acreditan eventos at?micos de ?xito para edici?n/revisi?n, estados y revisor protegidos, concurrencia e idempotencia. Esto no certifica una auditor?a forense completa ni disponibilidad de las integraciones productivas.

Permanecen pendientes el adaptador real de asociaciones S01, decisiones previas de producto/contrato y fuentes externas, y la auditoría de rechazos/correlación. La siguiente fase recomendada es acordar esos contratos y la política de rectificación con plataforma/producto. No se implementaron auditoría comercial, IA real, GCS, Flutter ni React.

Para repetir desde backend con evidencias en un directorio nuevo (sin sobrescribir esta entrega):

```powershell
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --tb=short
powershell -NoProfile -ExecutionPolicy Bypass -File integration\Review.ps1
```

El bypass es solo del proceso; no cambia políticas persistentes de Windows. El script focalizado usa por defecto este directorio de evidencia: antes de repetir una entrega cerrada debe seleccionarse otro destino. Al terminar se detienen únicamente servicios del proyecto aislado y se retienen datos y recursos.
