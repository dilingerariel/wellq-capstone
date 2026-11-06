# Calidad Ruff y gate CI — fase 4B

Fecha: 2026-11-05. Rama `fix/wellq-backend-hardening`, HEAD `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`. Fase de calidad controlada, sin cambios clínicos ni operaciones de publicación Git.

## Dictamen

Se implementó un **gate reproducible con Ruff 0.17.3 y Python objetivo 3.11**, con reglas obligatorias y deuda existente explícita que no puede crecer. **El gate pasa, Ruff estricto todavía no pasa:** quedan 414 observaciones revisadas, visibles y pendientes; no se afirma cero advertencias ni aprobación bajo todas las reglas posibles.

No se reprodujo un defecto funcional productivo entre los hallazgos priorizados. Se corrigió el registro de fixtures que originaba F811/F401, se eliminó un import sin uso y se ordenaron tres bloques de imports de dos módulos de pruebas. No se modificaron fuentes productivos, firmas, permisos, persistencia, fórmulas, catálogo, rangos, fechas clínicas ni generador PDF. Se separan las propuestas que exigen revisar UTC, excepciones y muchos módulos clínicos.

## Línea base e integridad

Se inspeccionaron estado Git, diff, untracked, rama, HEAD, documentos 23–25 y la selección de publicación. El estado inicial tenía 335 archivos tracked/untracked no ignorados inventariados. Se respaldó en `C:\Dev\wellq-quality-backups\20261105-210314\` el inventario con hashes, diff y ZIP privado comprobado. Contiene snapshots antiguos con configuraciones privadas: no versionarlo.

El inventario Ruff se obtuvo **antes de corregir** y con la versión fijada en requirements-dev: [before.json](evidencias_ruff/before.json). Resultado actual: **467 observaciones**, frente a las 454 del informe anterior. No se atribuye la diferencia a una regresión clínica: hubo nuevas herramientas desde aquella fotografía.

[Inventario clasificado](evidencias_ruff/classified-before.json): cada observación tiene ruta, regla, ubicación, mensaje, grupo y comparación con HEAD; cada regla incluye archivos, severidad y riesgo de corrección. No contiene fragmentos de fuente, fixes automáticos, credenciales ni valores clínicos.

Comparación con HEAD: 238 sitios coinciden por regla y texto de línea; 141 observaciones están en archivos nuevos respecto de HEAD; las restantes 88 están en archivos tracked pero no coinciden en ese criterio. Es una comparación de sitios diagnósticos, no una atribución de autoría ni una certificación semántica. Los Python de HEAD se exportaron solo al respaldo privado y nunca se ejecutaron.

## Conteos antes/después y comparabilidad

Hay tres mediciones distintas:

1. Perfil efectivo anterior sin configuración versionada: **467**.
2. Mismo árbol anterior, analizado con la política propuesta: **440**.
3. Árbol corregido, con esa misma política: **414**.

La política introduce la excepción específica FastAPI para 31 B008 y explicita los paquetes first-party, que hacen visibles cuatro I001 adicionales. Los cambios de código de pruebas eliminan 26 observaciones bajo el mismo perfil: 18 F811, cinco F401 y tres I001. No se presentan las 31 excepciones como 31 defectos arreglados ni se mezclan perfiles para inflar el resultado.

[Árbol previo bajo la política nueva](evidencias_ruff/policy-before.json), [inventario posterior](evidencias_ruff/after.json), [resumen](evidencias_ruff/summary.json).

| Regla | Perfil anterior | Pol?tica nueva antes | Pol?tica nueva despu?s | Revisi?n |
|---|---:|---:|---:|---|
| B008 | 31 | 0 | 0 | medium in general; legitimate FastAPI markers here |
| BLE001 | 20 | 20 | 20 | medium |
| DTZ003 | 41 | 41 | 41 | medium |
| F401 | 43 | 43 | 38 | low/medium |
| F811 | 18 | 18 | 0 | high in general; fixture shadowing here |
| F841 | 5 | 5 | 5 | low |
| FURB167 | 5 | 5 | 5 | low |
| I001 | 85 | 89 | 86 | low |
| PIE804 | 1 | 1 | 1 | low |
| PLW1510 | 3 | 3 | 3 | low in these tests |
| RUF059 | 8 | 8 | 8 | low/medium |
| RUF100 | 4 | 4 | 4 | low |
| SIM115 | 1 | 1 | 1 | low, historical test only |
| SIM117 | 3 | 3 | 3 | low |
| TRY004 | 3 | 3 | 3 | low finding; high correction risk |
| UP006 | 51 | 51 | 51 | low |
| UP017 | 5 | 5 | 5 | low |
| UP035 | 16 | 16 | 16 | low |
| UP045 | 124 | 124 | 124 | low |

Grupos iniciales: producción 310, workers 6, scripts 22, pruebas 46, integración Docker 70 y herramientas de publicación 13. Grupos posteriores: producción 280, workers 6, scripts 22, pruebas 48, integración Docker 45 y publicación 13. La reducción en producción procede de la excepción FastAPI y la reclasificación de imports; **no de haber modificado esos fuentes**.

## Revisión priorizada

### F811 y fixtures

Las 18 observaciones estaban en `integration/edit_review.py` y `integration/security_s01_s02.py`: fixtures `ctx`/`raw` importadas en el módulo y nombres locales usados como parámetros. No había una función productiva redefinida accidentalmente. Borrar esos imports con un fix F401 sin registrar las fixtures habría roto las pruebas.

Se trasladó el registro a `integration/conftest.py`, con reexport explícito `ctx as ctx` y `raw as raw`. Los tests reciben las mismas funciones fixture; una regresión comprueba su identidad. Los dos módulos dejaron de importar esos nombres, se quitó el import `copy` sin uso y se ordenaron únicamente sus bloques de imports. Los AST de todas sus funciones permanecen iguales frente al ZIP inicial. No se modificó su lógica de assertions, cuerpos HTTP ni preparación de datos. [pytest documenta el descubrimiento de fixtures mediante conftest](https://docs.pytest.org/en/stable/reference/fixtures.html).

### B008 y FastAPI

Las 31 ocurrencias son marcadores `fastapi.Depends` válidos. La configuración usa `extend-immutable-calls = ["fastapi.Depends", "fastapi.Query"]`, sin ignorar B008 ni modificar firmas. Es el mecanismo [documentado por Ruff](https://docs.astral.sh/ruff/settings/#lint_flake8-bugbear_extend-immutable-calls).

Las pruebas ejecutan Ruff contra ejemplos inventados: Depends/Query de FastAPI están permitidos, pero una función local llamada Depends sigue generando B008. No hay una excepción por nombre corto que autorice cualquier llamada predeterminada.

### DTZ003 y fechas

Las 41 ocurrencias conservan su estado de deuda revisada. Incluyen timestamps técnicos persistidos/comparados con Mongo y fechas de prueba. No se sustituyó ingenuamente `utcnow()` por datetime aware: [PyMongo interpreta datetimes naive como UTC y devuelve por defecto valores naive](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/data-formats/dates-and-times/), por lo que una migración parcial puede romper comparaciones, leases y expiración.

Propuesta separada: política de reloj técnico UTC, codec/normalización de lecturas, límites de fecha clínica y pruebas de comparaciones, expiración, microsegundos y cambio de día. Esa intervención debe conservar contratos y decidir explícitamente la relación con las fechas clínicas locales. No se implementó aquí ni se declara que todos los usos naive sean el diseño final recomendado.

### BLE001 y recuperación

Se inspeccionaron los 20 sitios: disponibilidad/readiness, parsing de cursores, límites de dependencias de storage, verificador S01, scanner, exportación, recuperación del worker y rechazo de exportación pública/escaneo. Muchos capturan deliberadamente errores heterogéneos para fallar cerrado, no reflejar datos de salud ni degradar un commit ya completado.

No se estrecharon automáticamente. Una propuesta futura debe enumerar errores por adaptador y preservar retry, fencing, rollback y mensajes acotados con fault tests. El worker mantiene máximo de intentos y comprobaciones de estado; una excepción de programación puede terminar clasificada como dependencia, lo que sigue siendo deuda de observabilidad/precisión, no algo ocultado como corregido.

### F401/F841 y otras reglas

Permanecen 38 F401 y cinco F841. Las F841 son cuatro alias de excepción no usados y un snapshot de prueba; no se borró la operación asociada. Los imports productivos pueden inicializar módulos/proveedores: no se eliminan muchos imports clínicos para conseguir un cero superficial.

TRY004 merece cuidado: `numeric_bound` en Pydantic usa ValueError para validación; cambiarlo mecánicamente a TypeError puede cambiar la conversión de errores de entrada. Los otros dos sitios pertenecen al script de recálculo y requieren revisar su contrato de errores. No se aplicó ese cambio.

Las tres PLW1510 están en tests del saneador que comprueban explícitamente returncode, incluidos errores esperados; no se reprodujo un resultado ignorado. SIM115 aparece en un test histórico bloqueado, sin ocurrencia productiva. RUF059 requiere conservar llamadas/validación de generación aunque no se use un binding. Las cuatro RUF100 son marcadores noqa anteriores; no se agregó ningún noqa nuevo.

I001 y modernización UP se mantienen visibles; ordenar imports o cambiar anotaciones de muchos modelos/routers requiere revisar efectos de módulo y OpenAPI. No se usó formatter ni un fix global.

## Gate implementado

Configuración: [ruff.toml](../ruff.toml). Ejecutable: [integration/quality_gate.py](../integration/quality_gate.py). Baseline revisado: [debt-baseline.json](evidencias_ruff/debt-baseline.json).

- Versión exacta Ruff 0.17.3, target py311, sin preview y sin ignores globales ni per-file añadidos.
- Reglas obligatorias: familia F y E9, con B008 activo. Dentro de F, únicamente F401/F841 existentes son deuda condicionada; los demás errores no se pueden eximir mediante el baseline.
- Robustez revisada: BLE001, DTZ003, TRY004, PLW1510 y SIM115; los sitios existentes tienen revisión y huella, no una desactivación de regla.
- Estilo/modernización: I001, UP006/UP035/UP045/UP017, PIE804, SIM117, RUF059, FURB167 y RUF100. Son deuda no bloqueante solo en los sitios congelados; cualquier observación nueva sí bloquea.
- E4/E7, E501, formatter y otras reglas no evaluadas no se incluyen como condición nueva de este gate. En una exploración de configuración E4/E7 ampliaban el trabajo a 394 avisos de estilo adicionales; no se presentan como corregidos ni se intenta resolverlos mediante una refactorización masiva. El gate contiene las reglas diagnosticadas originalmente y corrección Pyflakes/E9 explícita.

El baseline registra contador de huellas SHA-256 de ruta/regla/mensaje/línea normalizada, **sin almacenar la línea**. Cambiar contenido o introducir otra copia de una advertencia falla; mover la misma línea no añade ruido. Una reducción de deuda está permitida y se informa. Las pruebas verifican los casos de incremento, duplicación, desplazamiento y cambio de contenido.

No hay opción de autoaceptar nuevas observaciones ni actualizar el baseline desde el gate. Se vincula a un hash de configuración y a su versión de política; cambiar reglas sin revisión provoca error. Un baseline ausente/corrupto o un error de Ruff no produce aprobación. Esto no es un mecanismo contra ediciones maliciosas de toda la política: configuración, script y baseline se revisan juntos en el futuro diff.

Resultado: [gate.json](evidencias_ruff/gate.json): aprobado bajo esta política, cero infracciones obligatorias, cero deuda nueva y **414 observaciones pendientes**. `ruff check` directo sigue devolviendo 1; `integration.quality_gate` devuelve 0 solo bajo las condiciones anteriores. La aceptación de esta política con deuda debe revisarse antes del commit; no se afirma aprobación de producción clínica.

## Comandos reproducibles para terminal VS Code y CI

Desde backend, con el entorno autorizado ya instalado:

```powershell
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m ruff check --config ruff.toml --no-cache --statistics .
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m integration.quality_gate
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m pip check
```

El primer comando informa deuda y devuelve 1 mientras exista; el segundo es el gate combinado. Para VS Code, seleccionar ese intérprete y usar la configuración del backend; una extensión con otra versión no reemplaza el comando fijado. No se modificaron ajustes del editor.

Propuesta de job CI, no implementada ni publicada:

```text
Python 3.11
cd wellq-clinical-tests-main/backend
python -m pip install -r requirements-dev.txt
python -m pip check
python -m integration.quality_gate
python -m pytest checks tests -q -p no:cacheprovider
```

Añadir un job Windows para `integration/test_publication.py`, porque el puente validado invoca PowerShell. El job Mongo debe provisionar su propio proyecto/DB aislados; no reutilizar nombres/credenciales del entorno antiguo ni confundir scanner/IA/objetos test con servicios reales. El escaneo local de publicación necesita el env privado para contrastar credenciales efectivas y falla cerrado si no está disponible; no trasladar ese env al repositorio o a un job público.

Los paquetes se mantienen como estaban; `pip check` pasó y no se añadió dependencia. Los pins directos y los tags de imágenes aún no constituyen un lock transitivo de producción.

## Pruebas ejecutadas en esta fase

| Conjunto | Aprobadas | Fallidas | Omitidas | Evidencia |
|---|---:|---:|---:|---|
| Ocho regresiones nuevas del gate y 35 del saneador | 43 | 0 | 0 | [gate-and-publication.xml](evidencias_ruff/gate-and-publication-public.xml) |
| Suite aislada completa más saneador | **447** | **0** | **209** | [full-and-publication.xml](evidencias_ruff/full-and-publication-public.xml) |
| Suite completa final, incluida portabilidad LF/CRLF | **448** | **0** | **209** | | | [full-final.xml](evidencias_ruff/full-final-public.xml) |
| Primer intento HTTP/Mongo | 62 | 3 | 0 | [integration-attempt1.xml](evidencias_ruff/integration-attempt1.xml) |
| HTTP/Mongo final | 65 | 0 | 0 | | | [integration-after.xml](evidencias_ruff/integration-after.xml) |

Los tres XML de pruebas aisladas contienen URI inventadas en IDs parametrizados del saneador. Se conservaron los originales locales, excluidos por `docs/evidencias_ruff/.gitignore`, y se generaron copias `*-public.xml`: solo cambian esos IDs, con ordinales ?nicos; resultados, conteos y atributos de suite permanecen iguales. [Registro de publicaci?n XML](evidencias_ruff/xml-publication.json). El esc?ner de 4A no se modific? para exceptuar esos archivos.

Los conjuntos se solapan: la ejecuci?n inicial de 447 aprobadas inclu?a 404 anteriores, ocho del gate y 35 del saneador. El cierre agrega una novena regresi?n del gate para portabilidad LF/CRLF; no se suman ejecuciones repetidas como cobertura distinta. Las 209 omisiones históricas conservan su guard; no son aprobaciones. Las advertencias datetime/Pydantic y del cliente de tests permanecen visibles. Las 65 verificaciones de integración incluyen S01/S02, G03–G06, concurrencia, rollback, lifecycle y F01–F07, con Mongo/HTTP/worker reales y adaptadores externos declarados.

Incidencia de ejecución: la secuencia inicial propia arrancó workers antes de que Mongo aceptara conexiones. Ambos terminaron por conexión rechazada; tres tests que esperaban ready_for_review fallaron por timeout. Se verificó el estado de esos dos contenedores propios, se arrancaron únicamente después de disponibilidad Mongo/API y se conservó el intento. No se corrigieron asserts, fuente productivo ni recuperación del worker para ocultar el error del arranque. La repetición usa la misma imagen con readiness ya establecido.

No se ejecutó otra demostración visual PDF ni ClamAV real. Sí se comprobó exportación en las suites pertinentes. Las nueve pruebas nuevas del gate cubren deuda visible, reducción, deuda nueva, duplicación, cambio de fuente, un F821 no eximible, excepciones FastAPI y la identidad de las fixtures compartidas.

## Archivos modificados y seguridad

Fuentes existentes cambiados en 4B: **solo** `integration/edit_review.py` y `integration/security_s01_s02.py`, por imports/registro de fixtures. Nuevos: `ruff.toml`, `integration/conftest.py`, `integration/quality_gate.py`, `checks/test_quality_gate.py`, este documento y `docs/evidencias_ruff/`, incluida su exclusi?n espec?fica de tres XML crudos. Se actualiza también la propuesta de selección y su reporte de escaneo de `docs/evidencias_publicacion/`; los informes históricos se conservan.

[Preservación](evidencias_ruff/preservation.json): ningún archivo inicial desapareció; fuentes productivos/dependencias y los 32 módulos importados siguen intactos. OpenAPI coincide exactamente con `docs/openapi.json` y conserva **20 operaciones clínicas**. No cambian frontend, DTO, permisos, PDF, política de asociaciones ni validación de archivos.

Los cinco originales privados de Compose siguen ignorados e intactos, igual que las copias públicas. No se cambió el redactor de 4A, reglas ignore, escáner de secretos o la URI de HANDOFF_STATE.md. El inventario Ruff no exporta fuentes del snapshot privado de HEAD ni contenido de fixtures.

La selección actualizada y el escaneo final están en [allowlist.json](evidencias_publicacion/allowlist.json) y [secret-scan.json](evidencias_publicacion/secret-scan.json). El escaneo final analiza **236 candidatos** y debe aprobar; el control negativo detect? las diez apariciones de credenciales efectivas al forzar los cinco originales. [Control negativo](evidencias_ruff/publication-negative-control.json). P05 sigue pendiente de decisión del responsable; no se reescribió la historia ni se rotaron credenciales.

Se utilizó exclusivamente `wellq-int-39706292db88`, sin puertos host ni acceso a Mongo antiguo/OneDrive. Se preservan runners, auxiliares y volúmenes. Al cierre solo se detienen servicios propios; [inventario final](evidencias_ruff/docker-final.json). No se modificó Docker de producción ni se ejecutó limpieza global.

Estado de rama/HEAD e índice: sin cambio de rama o HEAD y sin staging, commit, push, merge, rebase o PR. La lista de archivos acumulados no debe atribuirse enteramente a esta fase.

## Trabajo separado y siguiente paso

1. Revisar y aceptar o ajustar explícitamente esta política de deuda antes de consolidar. No interpretar gate aprobado como Ruff estricto verde.
2. Reducir deuda en grupos pequeños: imports por módulo con comprobación de efectos; tipos con OpenAPI; UTC con comparaciones/clock; excepciones con pruebas de fallos. Si exige numerosos módulos clínicos, preparar otra intervención.
3. Conservar las ocho pruebas históricas pendientes de adaptación y los bloqueos de asociaciones, identidad, catálogo, IA/GCS y operación. No se resolvieron por pasar calidad.
4. Resolver P05 con el responsable y volver a escanear la selección exacta antes de solicitar autorización explícita para consolidación Git.

Se detiene la fase aquí. No se implementaron React, Flutter, proveedores, endpoints nuevos ni un despliegue de CI. El resultado revisable es una política reproducible con deuda honesta y regresiones, no una promesa de ausencia de riesgos.
