# Consolidación Git y handoff del backend WellQ

Fecha: 2026-11-05. Fase 3 de inspección y preparación, sin cambios productivos ni operaciones de escritura en Git. Repositorio `C:\Dev\wellq-capstone`, rama `fix/wellq-backend-hardening`, HEAD `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`.

## Dictamen y respuesta ejecutiva

**El backend acumulado está íntegro respecto al cierre de fase 2. La rama todavía no debe publicarse tal como está.** Hay dos asuntos que requieren una decisión antes de consolidar: cinco evidencias Compose contienen una credencial efectiva del Mongo sintético y Ruff no pasa. Se conserva todo sin corregirlo automáticamente, conforme a las restricciones de esta fase.

Se recomienda **un commit de consolidación coherente**, después de aprobar y comprobar el saneamiento de evidencias y resolver o aceptar explícitamente la deuda de calidad. Puede prepararse la revisión local ahora; no abrir un PR ni subir toda la carpeta de documentación mientras las credenciales sigan entre los candidatos. No se ejecutaron git add, commit, push, PR, cambio de rama, reset, clean, stash, merge o rebase.

## Estado Git e inventario

Antes de crear este documento: **151 archivos tracked, 21 modificados y 169 archivos nuevos sin seguimiento**. No hay archivos eliminados ni cambios staged. Son 190 archivos modificados/nuevos para revisar, todos dentro de `wellq-clinical-tests-main/backend/`. Este documento agrega un archivo nuevo: el total sin seguimiento pasa a 170, sin staging. Los directorios abreviados por `git status` no equivalen a archivos individuales.

| Responsabilidad | Modificados tracked | Nuevos antes del documento 24 |
|---|---:|---:|
| Aplicación y scripts productivos | 14 | 14 |
| Pruebas de aplicación/históricas | 1 | 9 |
| Configuración, dependencias y Docker raíz backend | 6 | 2 |
| Integración aislada, scripts y pruebas Docker | 0 | 40 |
| Documentación, contratos y evidencias | 0 | 104 |
| Total | **21** | **169** |

El anexo contiene el inventario exacto de los 190 archivos previos y la clasificación para el futuro commit. Los nuevos no son basura: incluyen servicios necesarios, DTO, tenant facade, worker, regresiones y evidencias. Los scripts de integración, aunque aún untracked, son parte del trabajo verificable.

El commit base es un merge anterior del proyecto. Los cambios acumulados incluyen sustituciones importantes de autenticación, almacenamiento, extracción, scoring, reporte y dependencias; no deben describirse como un parche pequeño únicamente de review. La fase 3 no modificó ninguno de ellos. El frontend y los archivos académicos/diagramas externos al backend no presentan cambios locales. Git no identifica al autor de un archivo untracked ni distingue por sí solo trabajo de otros desarrolladores: no se atribuye propiedad de todos los cambios al agente ni se descartan por esa razón.

## Integridad frente a la última validación

Se cotejaron **298 rutas**: las 294 de la línea base de fase 2 más sus cuatro archivos nuevos, aplicando los hashes finales del manifiesto de aquella fase sobre sus seis archivos existentes modificados. **Cero faltantes y cero diferencias.** Coinciden también las diez entradas del manifiesto final de fase 2. Esto cubre los fuentes productivos, las pruebas nuevas, el código de integración y las dependencias declaradas que respaldan sus resultados.

Referencias: [manifiesto de fase 2](evidencias_g03_g06/change-manifest.json), [preservación](evidencias_g03_g06/preservation.json), [suite aislada](evidencias_g03_g06/full-after.xml), [HTTP/Mongo](evidencias_g03_g06/integration-after.xml). Los registros auxiliares de evidencia producidos al final de la fase anterior no se convierten en resultados nuevos por ser leídos aquí.

Los artefactos PDF sintéticos de demo permanecen locales e ignorados; se conserva la verificación previa de sus bytes y revisión visual del documento 19. No se regeneraron ni se presentan como una nueva validación visual.

## Seguridad de publicación: bloqueo confirmado

La revisión inspeccionó candidatos tracked/untracked no ignorados, reglas de exclusión y coincidencias de credenciales sin imprimir valores. Se buscaron claves privadas, tokens literales, URI con contraseña, material de firma y asignaciones sensibles; se compararon en memoria los valores hallados con las credenciales locales de integración. Es una inspección focalizada, no una certificación universal de ausencia de secretos ni una auditoría del historial completo.

### Cinco archivos que NO deben entrar al commit actual

Rutas relativas a backend:

1. `docs/evidencias_integracion/compose-resolved-redacted.json`.
2. `docs/evidencias_s01_s02/compose-resolved-redacted.json`.
3. `docs/evidencias_s01_s02/compose-at-stop-redacted.json`.
4. `docs/evidencias_g03_g06/compose-resolved-redacted.json`.
5. `docs/evidencias_g03_g06/compose-at-stop-redacted.json`.

Cada archivo contiene **dos apariciones de la contraseña efectiva de la cuenta app del Mongo sintético**: `x-env.MONGODB_URI` y `x-app.environment.MONGODB_URI`. Son diez apariciones en total. No son referencias `${VARIABLE}`. Los valores no se incluyen en este informe. Son datos del entorno aislado, no evidencia de una credencial productiva, pero siguen siendo credenciales y bloquean su publicación.

Causa identificada: `integration/Common.ps1::Assert-IntegrationIsolation` redacta variables de los servicios resueltos, pero Compose conserva extensiones `x-*` con copias de environment. El nombre “redacted” no garantiza un saneamiento completo. Ninguno de estos cinco archivos está ignorado por Git.

**Propuesta, NO aplicada:** conservar los originales históricos como evidencia local privada, fuera de la selección del commit; preparar copias públicas nuevas con redacción recursiva de credenciales/URI en todas las ramas del JSON, incluidos `x-*`; comprobar las copias contra los valores reales en memoria y patrones de secretos; agregar exclusiones explícitas para los originales y dirigir futuras capturas a destinos privados/públicos diferenciados. No sobrescribir silenciosamente evidencias históricas ni eliminar archivos. Los enlaces públicos deberán apuntar a las copias saneadas con una nota de procedencia. Cambiar el redactor, los ignores o esos enlaces requiere autorizar una intervención posterior; aquí solo se propone.

No se subió ni stageó ningún archivo. No se rotaron credenciales ni se tocó Mongo. Si alguien ya compartió externamente los JSON, corresponde verificar la exposición y rotar las credenciales del entorno afectado; no se afirma que esa exposición haya ocurrido.

### Otras coincidencias revisadas y límites

- `docs/dependencies-before.json` contiene un JWT de ejemplo dentro de la descripción pública de una vulnerabilidad del informe de dependencias, en `dependencies.54.vulns.18.description`. No se identificó como un token emitido por la identidad WellQ de pruebas. Es un contexto técnico, no una prueba de autenticación vigente; conservar su contexto al revisar alertas del escáner.
- `wellq-clinical-tests-main/HANDOFF_STATE.md:105` ya contiene en HEAD una URI Mongo con credencial literal heredada. No coincide con la credencial actual de integración. Su vigencia es desconocida y no se probó conectando a ese servidor. Requiere revisión del responsable antes de publicar el repositorio completo; corregir el archivo actual no eliminaría por sí solo el dato de la historia. No se modificó ese documento fuera del alcance.
- Las coincidencias en Compose fuente son interpolaciones de variables; los adaptadores generan firmas/leen claves locales, y los tests históricos incluyen configuración de prueba. No se imprimieron sus valores ni se consideró automáticamente real toda coincidencia de un nombre como password o secret.
- No se encontraron bloques de clave privada ni tokens de acceso de los proveedores buscados entre los candidatos. Esto no sustituye un escaneo posterior de la selección exacta de publicación y, si corresponde, del historial.

### Archivos que deben permanecer locales

| Ruta/clase | Comprobación y decisión |
|---|---|
| `integration/.runtime/private.pem`, `gateway.key` | Ignorados; claves sintéticas privadas, nunca versionar |
| `integration/.runtime/integration.env` | Ignorado; contiene credenciales efectivas, nunca versionar |
| `integration/.runtime/public.pem`, `state.json`, `historical-reference.py` | Ignorados junto con el directorio; regenerar por scripts, no publicar el runtime completo |
| `integration/.runtime/render-venv/` y `.venv/` | Entornos locales; ignorados, no versionar |
| `integration/demo-output/` | **71 archivos**, incluidos **15 PDF sintéticos**; todos ignorados. Decisión: artefactos locales reproducibles, no fixtures binarios versionados |
| Backups externos `C:\Dev\wellq-*-backups\...` | Fuera del repositorio; mantener locales, sin trasladarlos a Git |
| Cachés, logs, exports, bases de datos y volúmenes | Mantener fuera de Git; no se añadieron/copiaron bases ni se inspeccionaron datos de contenedores |
| Cinco JSON con credenciales indicados arriba | Actualmente candidatos NO ignorados: exclusión manual de la futura selección hasta saneamiento; no considerarlos seguros por su nombre |

No hay nuevos `.pem`, `.key`, `.env`, bases, logs o PDF entre los nuevos archivos backend no ignorados. El repositorio ya contiene documentos académicos y un PDF de diagrama fuera del backend; están sin cambios y no se reclasifican como documentos de pacientes. No se accedió a documentos clínicos reales.

### Reglas de exclusión revisadas

`.gitignore` raíz excluye entornos Python, bytecode, `.env`/`*.env`, cachés de tests, logs y exports. `integration/.gitignore` excluye `.runtime/` y `demo-output/`; se verificó la exclusión efectiva de las claves y artefactos anteriores. El ignore raíz no establece una protección global para todos los posibles `.pem`/`.key` futuros: la protección actual depende de su ubicación en `.runtime`. Se propone reforzar patrones específicos de material privado sin ignorar indiscriminadamente certificados públicos legítimos.

`.dockerignore` excluye env, claves, credentials JSON, runtime, demo-output, tests/checks, estáticos y evidencias antiguas de integración/demo. **No excluye las evidencias S01–S02/G03–G06**, por lo que los JSON señalados pueden viajar en el contexto de build. Los Dockerfiles copian rutas explícitas y no copian `docs` a las capas de la aplicación; esto no elimina la necesidad de minimizar el contexto. Se propone excluir futuras evidencias privadas o todo el directorio de evidencias del contexto. Dockerignore no sustituye gitignore.

## Control de calidad: resultados nuevos y evidencia anterior

| Comprobación | Resultado | Naturaleza |
|---|---|---|
| Sintaxis Python mediante AST, sin compilar bytecode | **79 archivos**, cero errores | Nueva, candidatos del repositorio |
| Importaciones productivas explícitas | **32 módulos**, cero errores de importación | Nueva; sin lifespan, sockets ni conexión Mongo |
| Versiones declaradas | **22 pins directos** runtime/dev coinciden con el venv | Nueva; 16 runtime y 6 dev |
| `python -m pip check` | **No broken requirements found** | Nueva; consistencia, no análisis de CVE |
| `git diff --check` | Pasa; aviso de conversión LF/CRLF para storage.py | Nueva; no se normalizaron finales de línea |
| OpenAPI local vs snapshot y captura HTTP de fase 2 | Coinciden; **20 operaciones clínicas** | Comparación nueva, captura HTTP anterior |
| Recolección pytest desde backend | **613 tests collected**, sin errores | Nueva; no ejecuta los casos |
| Suite aislada final de fase 2 | **404 aprobadas, 0 fallidas, 209 omitidas** | Anterior vigente por hashes, no reejecutada |
| HTTP/Mongo focalizado de fase 2 | **65 aprobadas, 0 fallidas** | Anterior vigente, no se arrancó Docker |
| Ocho regresiones PDF | Incluidas en la suite de aplicación previa | No se regeneró PDF ni revisión visual |
| ClamAV real | Evidencia histórica separada del documento 14 | No reejecutado; la suite final usa scanner test |
| Ruff 0.17.3 | **Falla: 454 observaciones, 316 en app** | Nueva; sin `--fix` |

El comando de colección desde raíz descubre también tests de integración y da 672 casos; no es la suite habitual. La cifra canónica de 613 se obtuvo desde backend, respetando `pytest.ini`. No se ejecutaron esos tests ni se alteró su guard. Las 209 omisiones no equivalen a 209 casos aprobados; las ocho pruebas históricas de clasificación por título pendientes son un subconjunto de trabajo de adaptación descrito en el documento 16, no ocho fallas nuevas.

Ruff reporta: I001=82, UP045=124, B008=31, DTZ003=41, BLE001=18, UP035=16, F401=43, TRY004=3, UP006=51, F841=5, PIE804=1, UP017=5, SIM117=3, RUF059=8, F811=18, RUF100=4, SIM115=1. No reportó F821, pero eso no acredita por sí solo calidad completa. La cifra corresponde a las reglas efectivas del entorno. No existe configuración Ruff versionada en el repositorio; un gate CI debe definir explícitamente reglas y baseline. No se comparó el mismo gate con todo HEAD, por lo que no se atribuyen todas las observaciones a una sola fase.

**Propuesta, NO aplicada:** acordar un gate Ruff reproducible, triage de los hallazgos y una corrección separada o aceptación explícita y acotada de deuda antes de exigir un estado verde. No agregar ignores masivos para ocultar advertencias ni aplicar correcciones automáticas de fechas/estilo a código clínico en esta fase.

Los requirements cambiaron ampliamente desde HEAD: actualización de FastAPI/Pydantic/PyMongo/JWT/storage/ReportLab, incorporación de cryptography, pypdf y soporte de imágenes, y separación dev. Los pins directos no son un lock transitivo con hashes. Las imágenes `python:3.11-slim` y `mongo:7.0` usan tags móviles. No se cambiaron dependencias aquí ni se hizo un nuevo análisis de vulnerabilidades: los reportes pip-audit existentes conservan su fecha y no se presentan como seguridad actual garantizada.

## Lectura correcta de documentos 01–23

| Documento | Cómo usarlo ahora |
|---|---|
| 01 Estado backend | Histórico del primer cierre; no tomar sus cifras como estado final |
| 02 Correcciones | Histórico de implementación inicial y decisiones |
| 03 Contratos API | Referencia detallada inicial; aplicar después los cambios de 12, 15, 22 y 23 |
| 04 Seguridad | Arquitectura inicial y límites; complementar con S01/S02 y auditoría de fase 2 |
| 05 Almacenamiento | Flujo y garantías base; conservar discrepancias de contrato identificadas posteriormente |
| 06 Extracción | Frontera multimodal/proveedor y limitaciones; no implica IA real aprobada |
| 07 Scoring | Política y reproducibilidad; no aprobación clínica del catálogo |
| 08 Pruebas | Resultados históricos iniciales, superados en conteo por 22/23 |
| 09 Despliegue | Configuración/migración propuesta; no evidencia de migración o producción ejecutada |
| 10 Pendientes | Backlog histórico; cruzar con cierres posteriores |
| 11 Handoff | Mapa inicial para clientes; no reemplaza OpenAPI actual |
| 12 F01–F07 | Cierre focalizado conservado; regresiones siguen incluidas en pruebas actuales |
| 13 Integración | Aislamiento y funcionamiento del arnés; comandos deben revisarse antes de reutilizarlos |
| 14 Resultados integración | Evidencia histórica Mongo/ClamAV y ports; mantener intentos fallidos |
| 15 Contratos frontend | Guía de consumo vigente, complementada por los cambios explícitos de 22/23 |
| 16 Pendientes postintegración | Límites externos y ocho históricos todavía pendientes |
| 17 Demo PDF | Recorrido sintético previo; sus archivos de salida son locales ignorados |
| 18 Cumplimiento cinco fuentes | **Fotografía anterior a S01/S02 y G03–G06**; no corregir retrospectivamente sus defectos observados |
| 19 Auditoría visual | Revisión visual anterior, con límites; no es una nueva revisión de esta fase |
| 20 Estado/roadmap | Fotografía anterior a los últimos cierres; leer 22/23 para estado posterior |
| 21 Guía Docker | Procedimiento y límites locales; no es despliegue navegador/cloud |
| 22 S01–S02 | Cierre de validación y fallo cerrado; adaptador productivo S01 sigue bloqueado |
| 23 G03–G06 | Último cierre funcional; referencia de PATCH/review/auditoría mínima y resultados vigentes |

Todos los enlaces relativos comprobados resuelven localmente. **22 enlaces** de los documentos 17–21 apuntan a artefactos ignorados que no acompañarían un checkout limpio. No se publicarán los PDF automáticamente para resolverlos. El handoff de un PR debe señalar qué salidas se regeneran con el arnés y qué evidencias públicas saneadas se adjuntan. Los enlaces a los cinco JSON inseguros tampoco deben inducir a subir sus originales. No se sobrescribieron documentos ni capturas para aparentar que los defectos siempre estuvieron corregidos.

## Qué versionar y qué no

Después de aprobar saneamiento y revisión, versionar juntos:

- Los fuentes runtime modificados y los 14 nuevos de `app/`, incluido worker/tenant/servicios y DTO; `scripts/recompute_scoring.py`.
- Requirements runtime/dev, `.env.example` solo con configuración no secreta, Dockerfiles/Compose fuente con variables interpoladas, `pytest.ini` y `.dockerignore`.
- Los nueve archivos de `checks/` y el guard modificado `tests/conftest.py`; conservar intactos los tests históricos existentes.
- Los 40 archivos fuente y scripts de `integration/`, incluida su `.gitignore`; nunca incluir el directorio runtime ni salidas de demo.
- Documentos 01–24, `docs/openapi.json`, manifiestos/reportes y XML históricos revisados, incluidos intentos fallidos. Las cinco capturas inseguras requieren copias saneadas y selección explícita; no hacer una inclusión recursiva ciega de `docs/`.

Los datos sintéticos versionables son generadores y fixtures en código, ejemplos HTTP redactados y evidencia mínima revisada. Los 15 PDF de la demostración son salidas reproducibles locales: **no se propone versionarlos** en esta consolidación. No agregar archivos de pacientes, entornos, credenciales, backups, DB, volúmenes o logs sensibles.

## Plan propuesto de commits

**Número recomendado: 1**, después de resolver los bloqueos de publicación. No se ejecuta staging.

| Campo | Propuesta |
|---|---|
| Mensaje | `fix(backend): consolidate validated clinical backend hardening` |
| Archivos | Los 21 modificados, los nuevos runtime/tests/config/integración/documentación del inventario y este documento; reemplazar la intención de publicar las cinco capturas por copias públicas saneadas autorizadas |
| Justificación | Los routers concentran seguridad, carga, extracción, reportería y review; importan DTO/servicios nuevos. Configuración, requirements, tenant facade, worker, guard y arnés se necesitan mutuamente. Dividir por etiquetas de fases produciría commits artificiales o intermedios no ejecutables |
| Dependencia | El HEAD actual y el árbol completo verificado; saneamiento aprobado y selección exacta de archivos previamente inspeccionada |
| Riesgos | Diff acumulado amplio, cambios de versiones/contrato y nueva persistencia; archivos untracked omitidos romperían imports; staging amplio podría filtrar credenciales; 209 tests omitidos y Ruff pendiente no deben presentarse como éxito total |
| Comprobaciones antes del commit | Escanear selección exacta y rutas excluidas; verificar copias saneadas y hashes; gate Ruff acordado; pip check, sintaxis/imports, OpenAPI/20 operaciones y diff check; ejecutar pruebas afectadas solo si cambian fuentes/dependencias, y suite completa antes de congelar un árbol funcional distinto |
| Revisión y eventual PR | Descripción basada en conducta final, contratos y límites; adjuntar resultados vigentes con fecha, explicar omisiones y dobles; aprobación humana antes de commit/publicación según el flujo que se acuerde |

No se propone recrear retroactivamente commits F01/Gxx usando parches parciales de los mismos routers. Una futura separación de documentos o limpieza de estilo solo tiene sentido si se verifica cada árbol intermedio y se obtiene una ventaja real de revisión. El plan de un commit no autoriza a incluir secretos ni a presentar Ruff como aprobado.

## Handoff para React: contratos actuales

La autoridad técnica es `docs/openapi.json`, corroborado contra `app.openapi()` y la captura HTTP de fase 2. Los DTO están en `app/models/schemas.py`, `extraction.py`, `scoring.py` y `reporting.py`; los documentos 15, 22 y 23 explican reglas no expresadas enteramente en tipos.

| Área | Contrato de consumo |
|---|---|
| Identidad | JWT RS256 emitido por autoridad externa confiable. Tenant, rol y recurso propio proceden del token; no implementar login/OTP ficticio en este módulo |
| Permisos | `clinical:read/write`, `documents:download`, `extractions:confirm/validate`, `clinical:review`, `reports:export`; export requiere también capability `report_export`. Relación asistencial se comprueba en servidor |
| Roles | Paciente sobre sus exámenes y confirmación; clínico autorizado para review/validación y reportes/score clínicos. UI no reemplaza autorización |
| Carga | Initiate, PUT de bytes con required_headers, complete y polling de status; borrar copia local solo con `local_file_can_be_deleted=true` |
| Asociaciones | Opcionales. Nuevas o efectivas se verifican; 503 si no existe adaptador autorizado, 403 si autoridad rechaza. Nunca quitar una asociación automáticamente para eludir una denegación |
| PATCH | Omitido conserva; null limpia notas/asociaciones; title/type/date no admiten null; vacío/desconocidos 422; examen revisado 409 |
| Review | Solo documento listo y seguro. Primera revisión inmutable; replay idéntico mismo clínico 200, otro revisor o nota cambiada 409. No equivale a validar extracción |
| Extracción | Propuesta, confirmación/corrección y validación separadas. Polling cuando está queued; reprocess puede devolver extraction_id:null. Conservar intención/clave en reintentos |
| Nulos | No inventar ceros ni rangos; mostrar motivos de falta de score/subscore y datos insuficientes |
| Estados | Upload: initiated/object_uploaded/processing/ready_for_review/rejected/failed/deleted. Review: not_reviewed/reviewed. Estados extracción independientes conforme al enum OpenAPI |
| Errores | Envelope detail objeto con code y contexto opcional. Manejar 401/403/404/409/413/422/429/503 y Retry-After donde corresponda; no asumir detail[] nativo ni reintentar sin límite |
| Reportes/PDF | JSON de score/series/reporte para clínicos autorizados. Export ready entrega enlace y expiración; download_pending conserva export_id con URL/expiración nulos. Reintentar misma intención y no habilitar descarga antes de ready |
| Privacidad | Notas privadas de review no se muestran al paciente; no guardar tokens, URLs firmadas o cuerpos clínicos en logs del navegador |

**React puede comenzar** componentes, tipos y cliente con contratos/fixtures sintéticos. La integración real en navegador necesita, como propuesta no implementada: publicar deliberadamente una API de desarrollo en un puerto libre de loopback, configurar un origen CORS explícito y los headers necesarios, hacer que el transporte de objetos y sus URLs sean accesibles desde navegador, y acordar emisión/custodia de identidades de prueba. `api-int`/`objects-int` son nombres de red Docker, no URLs del navegador. No reutilizar 8000/27017 de servicios antiguos ni portar claves privadas al frontend. No se agregaron endpoints, puertos o excepciones de autenticación.

## Pendientes que no deben desaparecer del handoff

| Pendiente | Dependencia/límite |
|---|---|
| Adaptador productivo S01 | Fuente real de casos/citas y política de propiedad, estado y relación; hoy fallo cerrado |
| Rechazos y correlación | Sink duradero seguro separado del rollback de dominio; auditoría mínima de éxito no cubre auditoría forense |
| Rectificación clínica | Política formal de cambio de review/nota/autores; no existe endpoint administrativo nuevo |
| GCS real | Bucket autorizado, IAM, firmas, generaciones y durabilidad reales; gateway test no lo acredita |
| IA autorizada | Proveedor aprobado, tratamiento de datos y evaluación de calidad; fixture anotado no sustituye IA real |
| Catálogo clínico | Aprobación, procedencia/versionado de rangos/pesos; mantener las puertas actuales |
| Identidad externa | Emisor, claims, grants/capabilities y relación asistencial integrados con plataforma |
| Privacidad/retención/operación cloud | Políticas aprobadas, consentimiento, operación, recuperación y despliegue reales |
| React y Flutter | Implementación/integración de clientes fuera de esta fase |
| Ocho históricos de título | Adaptación explícita del documento 16; conservar originales y guard |
| Publicación segura y gate Ruff | Cinco evidencias por sanear, referencias heredadas por revisar y 454 observaciones por triage |

## Recomendación final y límites de esta intervención

1. Mantener este árbol local íntegro y sin staging mientras se revisa el informe.
2. Autorizar por separado copias saneadas, corrección del redactor/ignores y referencias de publicación; conservar originales privados. Revisar la URI heredada con el responsable sin conectarse al sistema antiguo.
3. Acordar el gate Ruff y la corrección o aceptación explícita de deuda; no mezclarlo con cambios clínicos ni ajustes silenciosos del contrato.
4. Validar la selección final por allowlist y escaneo; si cambia código/dependencias, repetir pruebas pertinentes y documentar el nuevo árbol.
5. Preparar el único commit coherente propuesto y un PR revisable únicamente cuando el usuario autorice esas operaciones. Adjuntar evidencias saneadas, tests y límites, sin datos privados.

En esta fase no se ejecutó ninguna orden Docker: no hubo arranque, parada, inspección de datos/logs ni cambios a contenedores/volúmenes. Los resultados Docker citados son los anteriores verificados por manifiestos, no mediciones nuevas. No se modificaron frontend, API, permisos, scoring, PDF, dependencias, fuentes, tests, ignores, evidencias históricas ni recursos ajenos. La única incorporación versionable de esta fase es este documento. La recomendación es consolidar después del saneamiento; **no publicar el árbol actual en bloque**.

## Anexo: selección de archivos pendiente de revisión

Inventario anterior al documento 24. M = modificado tracked; N = nuevo sin seguimiento. Las rutas son relativas a backend. “Versionar tras revisión” no es una orden de staging; las cinco exclusiones son bloqueantes.

| Git | Archivo | Grupo | Decision propuesta |
|---|---|---|---|
| M | `.env.example` | Configuracion/dependencias | Versionar tras revision |
| M | `Dockerfile` | Configuracion/dependencias | Versionar tras revision |
| M | `app/config.py` | Producto | Versionar tras revision |
| M | `app/database.py` | Producto | Versionar tras revision |
| M | `app/dependencies/auth.py` | Producto | Versionar tras revision |
| M | `app/main.py` | Producto | Versionar tras revision |
| M | `app/models/extraction.py` | Producto | Versionar tras revision |
| M | `app/models/schemas.py` | Producto | Versionar tras revision |
| M | `app/models/scoring.py` | Producto | Versionar tras revision |
| M | `app/routes/clinical_tests.py` | Producto | Versionar tras revision |
| M | `app/routes/extractions.py` | Producto | Versionar tras revision |
| M | `app/services/catalog.py` | Producto | Versionar tras revision |
| M | `app/services/extractor.py` | Producto | Versionar tras revision |
| M | `app/services/scoring.py` | Producto | Versionar tras revision |
| M | `app/services/storage.py` | Producto | Versionar tras revision |
| M | `docker-compose.test.yml` | Configuracion/dependencias | Versionar tras revision |
| M | `docker-compose.yml` | Configuracion/dependencias | Versionar tras revision |
| M | `pytest.ini` | Configuracion/dependencias | Versionar tras revision |
| M | `requirements.txt` | Configuracion/dependencias | Versionar tras revision |
| M | `scripts/recompute_scoring.py` | Producto | Versionar tras revision |
| M | `tests/conftest.py` | Pruebas | Versionar tras revision |
| N | `.dockerignore` | Configuracion/dependencias | Versionar tras revision |
| N | `app/models/errors.py` | Producto | Versionar tras revision |
| N | `app/models/reporting.py` | Producto | Versionar tras revision |
| N | `app/services/associations.py` | Producto | Versionar tras revision |
| N | `app/services/audit.py` | Producto | Versionar tras revision |
| N | `app/services/clinical_dates.py` | Producto | Versionar tras revision |
| N | `app/services/evaluation.py` | Producto | Versionar tras revision |
| N | `app/services/file_validation.py` | Producto | Versionar tras revision |
| N | `app/services/references.py` | Producto | Versionar tras revision |
| N | `app/services/transactions.py` | Producto | Versionar tras revision |
| N | `app/services/upload_metadata.py` | Producto | Versionar tras revision |
| N | `app/services/uploads.py` | Producto | Versionar tras revision |
| N | `app/tenancy.py` | Producto | Versionar tras revision |
| N | `app/workers/__init__.py` | Producto | Versionar tras revision |
| N | `app/workers/processing.py` | Producto | Versionar tras revision |
| N | `checks/conftest.py` | Pruebas | Versionar tras revision |
| N | `checks/test_edit_review.py` | Pruebas | Versionar tras revision |
| N | `checks/test_final_defects.py` | Pruebas | Versionar tras revision |
| N | `checks/test_lifecycle.py` | Pruebas | Versionar tras revision |
| N | `checks/test_pdf_presentation.py` | Pruebas | Versionar tras revision |
| N | `checks/test_processing.py` | Pruebas | Versionar tras revision |
| N | `checks/test_scoring.py` | Pruebas | Versionar tras revision |
| N | `checks/test_security.py` | Pruebas | Versionar tras revision |
| N | `checks/test_security_s01_s02.py` | Pruebas | Versionar tras revision |
| N | `docs/01_ESTADO_BACKEND.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/02_CORRECCIONES_IMPLEMENTADAS.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/03_CONTRATOS_API_FRONTEND.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/04_SEGURIDAD_BACKEND.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/05_ALMACENAMIENTO_Y_PROCESAMIENTO.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/06_EXTRACCION_MULTIMODAL.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/07_SCORING_Y_REPRODUCIBILIDAD.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/08_PRUEBAS_Y_RESULTADOS.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/09_DESPLIEGUE_Y_CONFIGURACION.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/10_PENDIENTES_Y_BLOQUEOS.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/11_HANDOFF_FRONTEND_CHATGPT.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/12_CIERRE_DEFECTOS_F01_F07.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/13_INTEGRACION_DOCKER_AISLADA.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/14_RESULTADOS_PRUEBAS_INTEGRACION.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/15_CONTRATOS_FRONTEND_ACTUALIZADOS.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/16_PENDIENTES_POST_INTEGRACION.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/17_DEMOSTRACION_FUNCIONAL_PDF.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/18_CUMPLIMIENTO_CINCO_ARCHIVOS_ORIGINALES.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/19_AUDITORIA_VISUAL_PDF.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/20_ESTADO_REAL_BACKEND_Y_ROADMAP.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/21_GUIA_DESARROLLADOR_DOCKER.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/22_CIERRE_SEGURIDAD_ASOCIACIONES_ARCHIVOS.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/23_CIERRE_EDICION_REVISION_CLINICA.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/change-manifest.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/dependencies-after.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/dependencies-before.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_demo/application-regressions.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_demo/integration-first.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_demo/integration.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_demo/pdf-regressions-first.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_demo/pdf-regressions.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_demo/runtime.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_demo/sources.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_demo/visual-pages.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_f01_f07/01_suite_antes.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_f01_f07/02_siete_reproducciones_antes.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_f01_f07/03_primer_intento_tests_nuevos.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_f01_f07/04_suite_despues.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_f01_f07/05_historicos_puros_despues.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_f01_f07/06_contrato_openapi_final.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_f01_f07/manifest_final.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_f01_f07/resultados.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/baseline-pointer.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/before.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/change-manifest.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/collection-error.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/compose-at-stop-redacted.json` | Documentacion/evidencia | EXCLUIR original; proponer copia saneada |
| N | `docs/evidencias_g03_g06/compose-resolved-redacted.json` | Documentacion/evidencia | EXCLUIR original; proponer copia saneada |
| N | `docs/evidencias_g03_g06/docker-final.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/full-after.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/git-status-final.txt` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/http-after.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/initial-after.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/integration-after.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/integration-attempt1.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/openapi-before.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/openapi-http.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/preservation.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/related-after.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/review-http-attempt1.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/review-http-mongo.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/runtime-docker.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/security-http-attempt1.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_g03_g06/test-counts.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/application-regressions.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/clamav-first.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/clamav-second.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/clamav-version.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/clamav.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/compose-resolved-redacted.json` | Documentacion/evidencia | EXCLUIR original; proponer copia saneada |
| N | `docs/evidencias_integracion/delivery-manifest.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/frontend-examples.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/historical-matrix.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/historical-matrix.md` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/integration-after-fixes.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/integration-first.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/integration.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/preservation.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/resources.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/restart-probe.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/runtime.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/sha256.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_integracion/summary.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/before.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/change-manifest.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/compose-at-stop-redacted.json` | Documentacion/evidencia | EXCLUIR original; proponer copia saneada |
| N | `docs/evidencias_s01_s02/compose-resolved-redacted.json` | Documentacion/evidencia | EXCLUIR original; proponer copia saneada |
| N | `docs/evidencias_s01_s02/docker-final.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/focused-after.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/full-after.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/git-status-final.txt` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/http-after.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/http-attempt1.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/http-before.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/integration-after.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/integration-attempt1.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/preservation.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/related-after.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/runtime-docker.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/runtime-local.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/evidencias_s01_s02/test-counts.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/openapi.json` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/test-results.xml` | Documentacion/evidencia | Versionar tras revision |
| N | `docs/tested-dependencies.json` | Documentacion/evidencia | Versionar tras revision |
| N | `integration/.gitignore` | Integracion | Versionar tras revision |
| N | `integration/Build.ps1` | Integracion | Versionar tras revision |
| N | `integration/ClamAV.ps1` | Integracion | Versionar tras revision |
| N | `integration/Common.ps1` | Integracion | Versionar tras revision |
| N | `integration/Demo.ps1` | Integracion | Versionar tras revision |
| N | `integration/DemoProbes.ps1` | Integracion | Versionar tras revision |
| N | `integration/DemoTests.ps1` | Integracion | Versionar tras revision |
| N | `integration/Dockerfile` | Integracion | Versionar tras revision |
| N | `integration/Examples.ps1` | Integracion | Versionar tras revision |
| N | `integration/Inspect.ps1` | Integracion | Versionar tras revision |
| N | `integration/OpenDemo.ps1` | Integracion | Versionar tras revision |
| N | `integration/Prepare.ps1` | Integracion | Versionar tras revision |
| N | `integration/Report.ps1` | Integracion | Versionar tras revision |
| N | `integration/RestartProbe.ps1` | Integracion | Versionar tras revision |
| N | `integration/Review.ps1` | Integracion | Versionar tras revision |
| N | `integration/Security.ps1` | Integracion | Versionar tras revision |
| N | `integration/Start.ps1` | Integracion | Versionar tras revision |
| N | `integration/Stop.ps1` | Integracion | Versionar tras revision |
| N | `integration/Test.ps1` | Integracion | Versionar tras revision |
| N | `integration/__init__.py` | Integracion | Versionar tras revision |
| N | `integration/adapters.py` | Integracion | Versionar tras revision |
| N | `integration/av_checks.py` | Integracion | Versionar tras revision |
| N | `integration/bootstrap.py` | Integracion | Versionar tras revision |
| N | `integration/compose.yaml` | Integracion | Versionar tras revision |
| N | `integration/demo.py` | Integracion | Versionar tras revision |
| N | `integration/edit_review.py` | Integracion | Versionar tras revision |
| N | `integration/examples.py` | Integracion | Versionar tras revision |
| N | `integration/functional_probes.py` | Integracion | Versionar tras revision |
| N | `integration/guard.py` | Integracion | Versionar tras revision |
| N | `integration/objects.py` | Integracion | Versionar tras revision |
| N | `integration/prepare.py` | Integracion | Versionar tras revision |
| N | `integration/provision.py` | Integracion | Versionar tras revision |
| N | `integration/render_demo.py` | Integracion | Versionar tras revision |
| N | `integration/report.py` | Integracion | Versionar tras revision |
| N | `integration/restart_probe.py` | Integracion | Versionar tras revision |
| N | `integration/security_s01_s02.py` | Integracion | Versionar tras revision |
| N | `integration/tests/conftest.py` | Integracion | Versionar tras revision |
| N | `integration/tests/test_f01_f07_real_db.py` | Integracion | Versionar tras revision |
| N | `integration/tests/test_historical_ports.py` | Integracion | Versionar tras revision |
| N | `integration/tests/test_mongo_api.py` | Integracion | Versionar tras revision |
| N | `requirements-dev.txt` | Configuracion/dependencias | Versionar tras revision |

El documento 24 se agrega al grupo documental; no altera los 190 elementos inventariados arriba.
