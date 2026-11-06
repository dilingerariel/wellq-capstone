# Cierre focalizado F01–F07

**Fecha:** 2026-11-05, America/Santiago. **Rama:** `fix/wellq-backend-hardening`.
**Commit base/HEAD:** `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`.
**Alcance:** corregir siete defectos reproducidos; conservar el hardening previo, las 20 operaciones `/api/v1`, fórmulas, pesos, rangos y pruebas históricas. Sin frontend, nuevas dependencias, proveedor IA, Docker, servicios existentes, migraciones, recálculos de bases existentes ni commits/push.

## Línea base y fuentes

Se comprobó la rama y se conservaron status, diff y SHA-256 de los 184 archivos tracked/untracked iniciales. Había 21 archivos tracked modificados y 33 untracked, todos anteriores a esta tarea. Se revisaron los hallazgos, contratos, restricciones y pruebas de `C:\Dev\wellq-auditoria-final\`; esos informes y evidencias se conservan intactos, verificados por hash.

El Documento Maestro completo está disponible en `C:\Users\vegal\Downloads\Documento_Maestro_Proyecto_Examenes_Medicos_WellQ(2).docx`, v1.0, 4 de septiembre de 2026. Se contrastaron las reglas relevantes de §§5.1, 5.2.5, 5.3.2, 5.5, 7, 8 y 9 con las reproducciones y RF/RNF. Las referencias Pn de la auditoría corresponden a párrafos XML, incluidas tablas. No se aprobaron parámetros clínicos ni se completaron funcionalidades fuera del alcance.

Antes de editar se reprodujeron **7/7 defectos**, y la suite completa dio **215 aprobadas, 209 omitidas, 0 fallidas**. Las 209 omisiones no son aprobaciones. Las dos suites se ejecutaron sin lifespan real, usando datos sintéticos y sin contactar Docker ni localhost de servicios existentes.

## Matriz de cierre

| ID | Causa raíz | Solución aplicada | Test principal en checks/test_final_defects.py | Resultado |
|---|---|---|---|---|
| F01 | La puerta clínica protegía el snapshot nuevo, pero no caches de marcadores, historia, tablas y PDF | Política única de publicación; sello de aprobación/hash/versión; filtrado en cada salida; caches antiguos sin procedencia no ganan aprobación al activar una variable | test_f01_unapproved_catalog_must_not_publish_subscores; pruebas de todas las superficies, historia, PDF y corrección clínica | Cerrado en aplicación; pruebas aisladas aprobadas |
| F02 | float(None), fallback por clave ausente y supuestos bilaterales | Resolución explícita de límites y parámetros; referencias inválidas se rechazan o excluyen; sin inventar límites; None + motivo cuando no hay cálculo justificable | test_f02_nullable_reference_must_not_crash_scoring; vectores, DTO y confirmación HTTP | Cerrado; rangos completos previos conservan fórmulas |
| F03 | El pipeline reemplazaba confianza efectiva cero por confianza del proveedor | provider_confidence separada; confidence efectiva cero para datos invalidados; motivos y salida original guardados en propuesta | test_f03_invalid_field_confidence_must_be_zero; invalid_provider_marker_stays_out_of_scoring | Cerrado; datos inválidos no entran al scoring |
| F04 | Se reemplazaba reference después de calcular status con catálogo | Una resolución de referencia/estado compartida; conversión canónica; ediciones preservan rango documental; lectura resuelve estado con la misma referencia | test_f04_document_reference_must_drive_display_status; conversiones y corrección paciente/clínico/serie/reporte | Cerrado con incertidumbre explícita |
| F05 | Solo se validaba sintaxis de fecha | Reloj UTC inyectable; validación de fechas de documento, reporte, paneles, carga y ediciones; defensa antes de confirmar; código de worker específico | test_f05_future_date_must_not_pass_deterministic_validation; reloj, provider, legacy, DTO y worker | Cerrado; no fechas sustitutas |
| F06 | Se capturaba fallo de firma y se respondía ready con URL nula | Estado download_pending para PDF almacenado sin enlace; DTO coherente; replay firma otra vez y conserva export_id/objeto/evento | test_f06_signer_failure_must_not_report_ready; recuperación, enlace parcial y DTO | Cerrado; recuperación idempotente comprobada con doble |
| F07 | Discard guardaba clave sin request_hash; replay comparaba contra hash ausente | Persistir fingerprint también al descartar y usar el mismo serializador para primer resultado/replay; conservar propuesta y un solo evento | test_f07_discard_replay_must_be_idempotent; concurrencia modelada | Cerrado; 200 equivalente, cuerpo diferente 409 |

## F01: publicación y procedencia

`ScoringEngine.publication_allowed()` permite cálculo/publicación con catálogo aprobado o en el entorno de pruebas explícito existente. No se modificó el valor productivo de aprobación ni se habilitó una excepción nueva por defecto.

Fuera de test, un subscore cacheado requiere `subscore_clinically_approved=true`, `subscore_catalog_hash` coincidente con el catálogo actual y `scoring_version` vigente. Los marcadores nuevos/corregidos incorporan ese sello. Un cache anterior, sintético o de origen desconocido no queda aprobado simplemente porque se active la configuración. Los snapshots también requieren aprobación registrada, hash y versión conocidos; los no publicables se excluyen del histórico y de series de pilares. No se borran ni se modifican snapshots previos.

Sin aprobación: confirmación y corrección de valores siguen funcionando; no calculan subscores nuevos. GET markers y tabla conservan valores y devuelven `subscore:null` con motivo. El reporte devuelve `score:null`, sin banderas derivadas del score ni series históricas no aprobadas; PDF usa ese mismo payload. El estado derivado exclusivamente de rango de catálogo/no documentado se presenta indeterminado mientras no sea publicable. Un rango del propio documento puede seguir describiendo fielmente el resultado, sin sustituir una aprobación clínica de scoring.

El paciente no obtiene puntajes por rutas de scoring/reportes/series/export: se mantienen las denegaciones de rol. MarkerItem no expone subscore. El identificador opaco `score_snapshot_id` de confirmación no es un puntaje y conserva compatibilidad.

Una exportación anterior no se firma de nuevo si cambió la política de publicación o el payload: `409 EXPORT_SOURCE_CHANGED`, con una nueva clave para generar el contenido actualmente autorizado. Los datos/PDF originales no se borran. URLs firmadas ya emitidas siguen teniendo su expiración corta; esta tarea no revoca accesos cloud retroactivamente ni verifica IAM real.

**Relación funcional:** Maestro §8/P858 exige parámetros aprobados antes de exposición clínica; RF-1.3.3–5 y RNF-2.4.1. Los tests con aprobación true modelan exclusivamente la condición positiva, sin aportar aprobación médica real.

## F02 y F04: rangos efectivos sin modificar fórmulas

`app/services/references.py` resuelve referencia documental o de catálogo, conversión de unidades y estado. No rellena un límite documental ausente con uno del catálogo. Si no existe referencia documental (`None`), puede usarse la de catálogo conforme a prioridad de §5.5.3. Una referencia explícita vacía o source=none no se convierte silenciosamente en un rango completo.

| Entrada | Comportamiento |
|---|---|
| Ambos límites finitos, low < high | Se usan esos límites, con parámetros de scoring coherentes y sin cambiar la función por tramos |
| Solo superior, lower_better | Puede calcularse usando la rama superior si óptimo/crítico aplicables existen y son coherentes |
| Solo inferior, higher_better | Puede calcularse usando la rama inferior si óptimo/crítico aplicables existen y son coherentes |
| Un límite en two_sided o falta el lado necesario | No se puntúa: INCOMPLETE_REFERENCE_RANGE |
| Sin ambos límites | No se puntúa: NO_REFERENCE_RANGE |
| Low >= high, texto no numérico, NaN, infinito, booleano | DTO rechaza; defensa de servicio excluye legacy con INVALID_REFERENCE_RANGE |
| Unidad incompatible | No se adivina conversión; rechazo o exclusión REFERENCE_UNIT_MISMATCH |
| Óptimo/crítico incompatible con rango efectivo | Exclusión INCONSISTENT_SCORING_PARAMETERS; no se inventan nuevos óptimos/críticos |

Si falta amplitud completa, no se fabrica una extensión crítica del 50%; una rama unilateral necesita su crítico explícito. Sin amplitud, tampoco se inventa el umbral proporcional de desviación high. Los vectores anteriores completos mantienen la fórmula, redondeo, pesos y penalizaciones: 106 casos de rejilla y 7 ejemplos Tabla20 siguen aprobados dentro de los históricos puros.

`calculate_subscore` devuelve `(None, None)` para un marcador no puntuable, en lugar de una cifra ficticia o una excepción por null. El snapshot registra la exclusión y la tabla/serie presenta el motivo en `subscore_blank_reason`. El valor clínico confirmado permanece almacenado. No se publica un cache antiguo para un rango que ya no justifica scoring.

El estado usa exactamente el rango resuelto. Un límite unilateral permite afirmar low/high cuando el valor viola ese límite; si no lo viola, se informa indeterminate, sin afirmar normalidad sobre el lado desconocido. La corrección del paciente conserva el rango documental si no entrega otro; el clínico corrige el valor y conserva ese rango. Propuesta y antecedentes permanecen. La referencia explícita en unidades originales admitidas se convierte mediante el factor existente, compartido con extracción.

**Relación funcional:** Maestro §§5.5.2–3, 8.1 y 8.2; RF-1.2.5, RF-1.3.3, RF-1.4.4. Las decisiones conservadoras excluyen datos insuficientes; no agregan parámetros médicos.

## F03: tres capas de evidencia

- `provider_confidence`: declaración del proveedor por campo, conservada como tal.
- `validation`: resultado determinista y motivos de rechazo.
- `confidence`: confianza efectiva para confirmación, cero cuando falla validación; el proveedor no puede restaurarla.

El contenido estructurado original del proveedor se copia a `proposal.provider_output` antes de las ediciones. No se registra en logs ni se publica como puntaje. Las respuestas de extracciones legacy también reducen confianza efectiva si validation.passed=false. Un rango con unidad desconocida queda explícitamente sin referencia y con confianza efectiva de referencia cero. Los valores rechazados permanecen visibles para corregir o descartar, y no generan marcador puntuable.

**Relación funcional:** Maestro §§5.1, 5.2.5 y 5.3.2; RF-1.2.6 y RF-1.3.1.

## F05: fecha de referencia y recuperación

`app/services/clinical_dates.py` proporciona un único día UTC. Las pruebas inyectan `as_of` en el pipeline o una fecha de referencia en el validador; el reloj no depende de fechas sustitutas del documento. Se validan `collection_date`, `report_date`, fecha por panel cuando se proporciona, `test_date` en carga/edición y fechas efectivas antes de insertar marcadores al confirmar.

Un proveedor con fecha futura/sintaxis inválida provoca `ClinicalDateError`, no una propuesta confirmable. GET extraction comunica al paciente HTTP409 INVALID_CLINICAL_DATE despues de verificar su acceso y el reproceso puede recuperarse aunque ese intento no haya producido extraction_id. El worker conserva `extraction_failed` y `extraction_job.error_code=INVALID_CLINICAL_DATE`, sin convertirlo en fallo genérico del proveedor ni reintento inútil de la misma fecha. Subida verificada y permiso de borrado local siguen siendo independientes. Los errores de fechas en solicitudes son HTTP422 con el formato existente. Una fecha inválida almacenada previamente no puede entrar a la serie por confirmación; puede corregirse mediante los campos admitidos o reprocesarse. Esta tarea no agrega un editor de paneles ni rellena fechas ausentes.

`DocumentEdits.report_date` y las fechas opcionales ya previstas por documento/panel se conservan como extensiones compatibles. No se completó la extracción de identidad/imagen o el esquema clínico entero.

**Relación funcional:** Maestro §5.1/P399, §7 y §8.4; RF-1.2.5 y RNF-2.4.1.

## F06: contrato de exportación

| HTTP / status | Significado | Acción del cliente |
|---|---|---|
| 200 / ready | PDF almacenado, URL y expiración no vacías | Descargar mediante enlace privado |
| 200 / download_pending | PDF/registro conservados; firma no disponible | Repetir con el mismo body e Idempotency-Key; aplicar backoff |
| 409 / EXPORT_SOURCE_CHANGED | Cambió contenido o política de publicación | Consultar estado y usar una nueva clave para un reporte actualizado |

`download_pending` devuelve `download_url:null`, `expires_at:null`, `error_code:DOWNLOAD_URL_UNAVAILABLE`. El replay no genera otro PDF, registro o evento de exportación; solo reintenta firmar el mismo objeto. El DTO impide representar ready con enlace parcial y pending con enlace parcial. No se lanza un error dentro de la transacción que deshaga el registro ya generado. No se utiliza almacenamiento local ni URL ficticia.

**Cambio de contrato explícito:** el enum status se amplía; clientes deben procesar download_pending antes de intentar descargar. El camino de éxito ready conserva sus campos previos. No hay cambio de método/ruta. Maestro §9.5.4 y RF-1.4.5.

## F07: idempotencia del descarte

Se persisten clave y fingerprint del body validado. Primer resultado y replay usan `_response_from_ext_doc`, de modo que la respuesta de dominio es equivalente. Body válido diferente con la misma clave devuelve409; la misma propuesta/historial permanece y solo existe un evento extraction_discarded. La prueba concurrente usa dos peticiones con la transacción modelada por RLock del fixture, sin afirmar una garantía Mongo real. El rate limiter y contador de serialización de transacciones siguen funcionando: no son nuevas confirmaciones ni eventos clínicos duplicados.

**Relación funcional:** Maestro §§7.4.2, 10.3/P1290 y 13.4/P1537; RNF-2.2.1.

## OpenAPI y compatibilidad

Se mantienen exactamente las 20 parejas método/ruta clínicas y el prefijo `/api/v1`. Se conservan autenticación RS256, rechazo HS256, grants, tenant, relación clínica, privacidad documental, ausencia de dashboard demo y condiciones de borrado local, respaldadas por la suite previa.

Se documentó mediante `ErrorResponse` el formato deliberado ya usado en HTTP422: `detail` objeto con `code`, mensaje y errores opcionales. Se describen asimismo401/403/404/409/429/503 sin modificar su formato HTTP real. La prueba valida la respuesta422 y las referencias OpenAPI de las20operaciones. El archivo `docs/openapi.json` se regenera y se compara con app.openapi() sin arrancar servicios.

Adiciones del contrato: provider_confidence; report_date editable; subscore_blank_reason en puntos de serie; status download_pending/error_code en exportación. Los consumidores no deben inferir normalidad cuando status=indeterminate ni sustituir un subscore nulo por0. Mantener la leyenda no diagnóstica y la restricción de scoring a clínicos.

## Pruebas y evidencia

| Grupo | Recogidos | Ejecutados/aprobados | Fallidos | Omitidos/bloqueados |
|---|---:|---:|---:|---|
| Suite antes |424|215|0|209omitidos|
| Reproducciones originales antes |7|0aprobados,7ejecutados|7|0|
| Suite después |485|276|0|209omitidos|
| Nuevos casos permanentes incluidos arriba |61|61|0|0|
| Históricos puros complementarios |171|171|0|0en esa selección|

Los61 casos nuevos incluyen recuperación de las siete reproducciones y pruebas de superficies, bordes y contratos. **No se suman** 171 casos históricos a la cobertura nueva:140 ya reutilizan las mismas aserciones en checks. Siguen30 históricos de integración bloqueados y8 de clasificación por título pendientes de adaptar; el fixture original conserva209skip en la ejecución habitual.

Dos reproducciones se adaptan al requisito explícito de esta tarea: F02 exige excluir con None/motivo en lugar de exigir cualquier número; F05 espera error controlado ante fecha futura, en lugar de exigir una respuesta de pipeline. No se borraron ni modificaron originales de auditoría. F01/F03/F04/F06/F07 conservan sus comprobaciones de fallo esenciales.

Primer intento de los nuevos tests:19fallidos/33aprobados.18fallos provinieron del bloqueo de socket.connect, que también bloqueaba el pipe interno socketpair de asyncio en Windows; uno comprobó que la copia del proveedor añadía defaults del DTO. Se ajustó el guard de pruebas para permitir exclusivamente la construcción IPC de socketpair y seguir denegando conexiones de red; la aplicación conserva la salida exacta del proveedor antes de model_validate. El XML inicial se conserva, sin ocultarlo. No se desactivó autenticación, control tenant ni protección de pruebas históricas.

Evidencia versionable en [evidencias_f01_f07](evidencias_f01_f07/): línea base de suite, siete fallos iniciales, primer intento de tests nuevos, suite final y171históricos, más resultados/metadatos. Los reportes anteriores `test-results.xml` y la auditoría externa no se sobrescriben. Se usaron Python3.12.10, python -B/PYTHONDONTWRITEBYTECODE, pytest sin cache, sin instalar dependencias.

Comandos desde backend:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& '..\..\.venv\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --tb=short --disable-warnings
& '..\..\.venv\Scripts\ruff.exe' check app checks scripts --no-cache --select F821,F822,F823
& '..\..\.venv\Scripts\python.exe' -B -m pip check
git diff --check
```

Ruff de nombres indefinidos, pip check y whitespace pasan. No se afirma aprobación de lint amplio: sus advertencias anteriores no pertenecen a F01–F07. Hay744warnings en la suite final sin filtros por categoría, principalmente datetime.utcnow; no son fallos ni integración real. No se midió cobertura de líneas, precisión clínica o rendimiento.

## Archivos necesarios y límites de la entrega

Código existente modificado: app/main.py; models/extraction.py, reporting.py, schemas.py; routes/extractions.py, clinical_tests.py; services/catalog.py, extractor.py, scoring.py; workers/processing.py. Nuevos: models/errors.py, services/references.py, services/clinical_dates.py, checks/test_final_defects.py. Documentación actualizada01–11 mediante nota de vigencia, este12, OpenAPI y evidencias nuevas. El manifiesto final distingue los archivos de esta tarea del hardening previo.

**Defectos F01–F07 pendientes de corrección local:** ninguno dentro del alcance y contratos descritos. Esto no certifica transacciones reales, GCS/IAM, ClamAV, proveedor IA, precisión o despliegue. No se modificaron otras deficiencias de auditoría: catálogo ilustrativo, canon clínico parcial, conciliación/purga, operación, vigencia diaria de snapshots, ventana/desempates del reporte, auditoría operativa y aprobaciones legales/clínicas siguen pendientes.

**Preparación Docker:** apto para pasar a un encargo de integración aislada; integración todavía no verificada. Según información del usuario, Docker Desktop funciona, pero esta intervención no lo utiliza. No contactar/reiniciar/recrear wellq-api ni wellq-mongodb; no reutilizar backend_mongodb_data ni puertos8000/27017 ocupados. Crear después un proyecto Compose distinto, rutas y puertos distintos, volumen/replica set nuevo y datos sintéticos; comprobar identidad del ambiente antes de cualquier escritura. Provisionamiento e índices deben revisarse y probarse allí, sin migrar una DB existente. La suite histórica30requiere portar contratos y aislamiento, no quitar su guard.

**Frontend:** React visual/estructural puede avanzar con datos sintéticos y el OpenAPI actualizado. La integración funcional requiere el próximo staging aislado. Producción clínica sigue bloqueada por infraestructura verificada y aprobaciones externas; no se habilitó artificialmente el catálogo ni se seleccionó proveedor.
