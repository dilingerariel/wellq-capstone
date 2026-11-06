# Saneamiento seguro para publicación — fase 4A

Fecha: 2026-11-05. Repositorio `C:\Dev\wellq-capstone`, rama `fix/wellq-backend-hardening`, HEAD `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`. Alcance exclusivo de publicación de evidencias; sin correcciones Ruff, cambios clínicos ni operaciones de publicación.

## Dictamen

**P01–P04 quedan saneados para la selección propuesta de backend. P05 queda documentado para decisión del responsable, conforme al alcance autorizado.** Los cinco originales se mantienen intactos e ignorados; existen cinco copias públicas con estructura equivalente y sin credenciales efectivas. El redactor recorre estructuras anidadas, se minimizó el contexto Docker y se corrigieron referencias que inducían a subir artefactos locales.

La selección futura está en [allowlist.json](evidencias_publicacion/allowlist.json). Es una propuesta verificable, no staging ni autorización para publicar todo el repositorio. La URI heredada en HEAD y la calidad Ruff siguen condicionando una publicación global. No se declara que todo el historial esté libre de secretos.

## Línea base y protección

Se verificaron Git status/diff, archivos nuevos, rama y HEAD antes de intervenir. Línea base confirmada: **21 tracked modificados, 170 nuevos, cero eliminados y cero staged**; 321 archivos tracked/untracked no ignorados inventariados. El documento 24 estaba presente y se conserva sin cambios.

Respaldo privado previo: `C:\Dev\wellq-publication-backups\20261105-203805\baseline.json`, `baseline.diff` y `backend-before-private.zip`, comprobado legible. Contiene evidencia privada y no debe trasladarse a Git. Los respaldos anteriores no se tocaron.

Se cotejaron 38 fuentes productivos/dependencias/Dockerfiles/Compose con los hashes previos: sin diferencias. No se modificaron `app/`, rutas, identidad, permisos, scoring, extracción, generador PDF, requirements, Dockerfiles ni Compose fuente. Los 71 artefactos locales de demo y sus PDF no se regeneraron. Los resultados anteriores de 404 aprobaciones aisladas y 65 HTTP/Mongo son evidencia anterior; no se presentan como ejecuciones nuevas.

## P01: originales privados y copias públicas

Los cinco archivos originales tenían diez apariciones de la contraseña efectiva del Mongo sintético en `x-env.MONGODB_URI` y `x-app.environment.MONGODB_URI`. Se confirmó mediante comparación en memoria, sin imprimir valores.

| Original privado, relativo a backend | Copia pública nueva |
|---|---|
| `docs/evidencias_integracion/compose-resolved-redacted.json` | [compose-resolved-public.json](evidencias_integracion/compose-resolved-public.json) |
| `docs/evidencias_s01_s02/compose-resolved-redacted.json` | [compose-resolved-public.json](evidencias_s01_s02/compose-resolved-public.json) |
| `docs/evidencias_s01_s02/compose-at-stop-redacted.json` | [compose-at-stop-public.json](evidencias_s01_s02/compose-at-stop-public.json) |
| `docs/evidencias_g03_g06/compose-resolved-redacted.json` | [compose-resolved-public.json](evidencias_g03_g06/compose-resolved-public.json) |
| `docs/evidencias_g03_g06/compose-at-stop-redacted.json` | [compose-at-stop-public.json](evidencias_g03_g06/compose-at-stop-public.json) |

Los originales permanecen en esas mismas ubicaciones, con SHA-256 igual al inventario inicial. Cinco reglas exactas en `.gitignore` raíz impiden su inclusión ordinaria; `git check-ignore` confirmó las cinco exclusiones y su condición de archivos no tracked. No se borraron, movieron ni sobrescribieron. `git add -f` podría saltarse un ignore: por eso la selección se valida también con el escáner y una lista explícita, sin recomendar una inclusión recursiva.

Las copias son JSON válidos, mantienen claves, listas y estructura técnica, y usan `<REDACTED>` en los valores sensibles. Los campos no sensibles conservan su utilidad. También existe [compose-validation-public.json](evidencias_publicacion/compose-validation-public.json), exportación nueva de la configuración Compose actual mediante el redactor corregido.

[validation.json](evidencias_publicacion/validation.json) registra rutas, hashes de archivos originales y resultados, nunca contraseñas ni hashes de contraseñas. No contiene documentos médicos.

## P02: redactor recursivo y rechazo seguro

`integration/Common.ps1::Export-IntegrationPublicEvidence` delega el saneamiento en `integration/publication.py`, sin dependencias adicionales. `Assert-IntegrationIsolation` usa ese exportador después de sus controles existentes, sin modificar la configuración en memoria que necesitan las verificaciones de aislamiento.

El saneador recorre mapas/listas y extensiones `x-*`, sin depender de rutas concretas. Identifica nombres de contraseñas, tokens, API/access keys, credenciales, autorización, claves privadas y secretos de firma; admite camelCase y variantes con guiones. También sanea URI autenticadas/firmadas bajo nombres inesperados, asignaciones de entorno dentro de listas, opciones sensibles de comandos y material identificable de tokens/claves. Una plantilla ajena en la query no permite ocultar una contraseña literal en el userinfo.

Valores vacíos y campos públicos se conservan. Los secretos conocidos del env privado se cotejan en memoria para detectar apariciones bajo nombres imprevistos. Se conservan claves y forma de contenedores sensibles y se redactan sus hojas. Ciclos, profundidad excesiva, tipos no JSON, números no finitos, secretos en nombres de propiedad o residuos detectados hacen fallar la exportación antes de crear el archivo público. La CLI devuelve un mensaje fijo sin entrada ni excepciones internas. No se pretende reconocer cualquier secreto opaco desconocido: se combina política de nombres, formatos reconocibles y valores efectivos conocidos.

El input no se escribe en archivos temporales ni se pasa en argumentos. Los temporales de salida contienen solo datos ya saneados. Los destinos con `-redacted.json` se redirigen a `-public.json`; el reemplazo permitido se limita a nombres explícitamente públicos. La CLI rechaza usar el mismo archivo como entrada y salida. PowerShell emite escapes JSON para conservar Unicode sin depender de la página de códigos de Windows.

No se cambiaron políticas persistentes de PowerShell; las invocaciones de prueba usaron bypass limitado al proceso. No se cambió el runtime clínico ni se añadió un mecanismo de identidad.

## P03: Git y contexto Docker

Cambios de exclusión:

- `.gitignore`: cinco rutas exactas privadas; patrones para claves con sufijo `.private.pem`/`.private.key` y temporales públicos. `.runtime`, demo-output y venv siguen protegidos por las reglas previas.
- `.dockerignore`: se excluye **todo `docs/`** porque los informes y evidencias no son entradas de ninguna de las imágenes; se conserva la exclusión de `.runtime`, env, claves, venv, demo-output, tests/checks y estáticos que ya existía.

Se comprobó estáticamente que el patrón raíz `docs/` cubre todos los directorios de evidencia, incluidos S01/S02, G03–G06 y las copias públicas. Los archivos necesarios de aplicación, requirements y fuentes de integración permanecen presentes y sus fuentes previos conservan hashes. No se presenta esta comprobación como un build real ni como una simulación general de todas las reglas Dockerignore.

Se ejecutó únicamente `docker compose config --format json`, capturando su salida y exportando solo la versión pública. La configuración resolvió correctamente. No se ejecutó build, up, restart, stop, limpieza ni ninguna modificación de imagen, contenedor, red, base o volumen. No se conectó al Mongo antiguo ni se inspeccionaron sus datos/logs.

## P04: referencias públicas y artefactos locales

Se corrigió la referencia del documento 13 hacia la copia pública de Compose. Los **22 enlaces** a artefactos ignorados de los documentos 17–21 ahora apuntan a las instrucciones siguientes, marcados como artefactos locales. El contenido histórico fuera de los enlaces se comparó con el respaldo y permanece igual: no se cambiaron resultados, defectos observados ni conclusiones anteriores. El documento 18 sigue siendo una fotografía previa a S01/S02 y G03–G06.

[links.json](evidencias_publicacion/links.json) enumera las 23 modificaciones de referencia: una a copia pública y 22 a regeneración/límites. Los PDF, PNG, JSON de demo y runtime siguen locales e ignorados; no se incorporan binarios para arreglar enlaces. Los documentos 22–24 conservan sus descripciones históricas de los originales privados; esta nota explica su nueva clasificación de publicación.

<a id="regeneracion"></a>
### Regeneración de PDF, reportes JSON y páginas PNG

Las salidas de `integration/demo-output/` son sintéticas y reproducibles; un checkout limpio no las contiene. Desde backend, cuando se autorice volver a usar el proyecto de integración aislado:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File integration\Demo.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File integration\OpenDemo.ps1 -Scenario suficiente
powershell -NoProfile -ExecutionPolicy Bypass -File integration\OpenDemo.ps1 -Scenario incompleto
```

`Demo.ps1` recorre HTTP, descarga ambos PDF, escribe `resultados-demo.json`, los `reporte-http.json` y `http-redactado.json` de cada escenario, y ejecuta el renderizador local. Los PNG quedan en `suficiente/pdf-pages/` e `incompleto/pdf-pages/`, con `renderizado.json`. Para renderizar de nuevo exclusivamente PDF ya descargados, usando el venv que prepara Demo:

```powershell
.\integration\.runtime\render-venv\Scripts\python.exe -B integration\render_demo.py
```

Estas órdenes **no se ejecutaron en 4A**. Usarlas secuencialmente, sin DemoTests concurrente, verificando el aislamiento y conservando las salidas históricas antes de repetir. Los scripts pueden escribir nuevas salidas locales y arrancar servicios propios; no son acciones de esta fase. Fechas, IDs y bytes de una nueva demo pueden diferir: la regeneración no sustituye las capturas históricas ni acredita una nueva inspección visual humana.

<a id="sondas-historicas"></a>
### Sondas históricas de brechas

`sondas-brechas-http.json` es una captura local anterior a las correcciones. El script exacto que la produjo es `integration/DemoProbes.ps1`, que invoca `integration/functional_probes.py`. **No debe ejecutarse como regenerador de la misma evidencia sobre el código actual:** exige que initiate acepte el caso vulnerable con 201; S01/S02 ahora lo rechazan y esa precondición falla antes de terminar la captura.

Se conserva el original local. Reproducir exactamente ese escenario requeriría el snapshot vulnerable en otro entorno aislado, con autorización independiente; no se revirtió esta rama ni se implementó tal entorno. Esta regeneración histórica exacta permanece pendiente por diseño. Las evidencias versionables de antes/después de 22/23 y sus pruebas son la referencia actual de los cierres.

## P05: URI heredada, sin conexión ni modificación

Se confirmó la ubicación `wellq-clinical-tests-main/HANDOFF_STATE.md:105` sin mostrar su valor, y su presencia en HEAD local. El archivo conserva el hash de línea base y el contenido de HEAD, considerando normalización de finales de línea. Está fuera del backend y **no se modificó**.

No se intentó conectar al servidor ni se comprobó vigencia. No se declara inactiva la credencial ni se afirma una filtración externa. El responsable debe evaluar exposición y rotación; si el remoto ya la contiene, corresponde respuesta coordinada, revocación/rotación y saneamiento de historia según la política del repositorio. Editar el archivo actual no elimina el valor de commits anteriores. No se reescribió historial ni se rotó ninguna credencial.

### Hallazgo adicional en configuración de pruebas

El escáner detectó otra URI literal heredada en el fallback de `tests/conftest.py`. Se sustituyó solo ese destino por `mongodb://test-configuration-required.invalid/wellq_test`, sin credenciales. No se conectó al servidor previo ni se asumió que su contraseña fuera inactiva. No se modificaron los tests históricos ni su guard: se comparó el AST de `api_must_use_test_database` con el respaldo y permanece idéntico. La configuración explícita sigue mediante `WELLQ_TEST_MONGO_URI`; el guard incondicional no tiene bypass de env. El cambio evita conservar una credencial literal en un archivo tracked modificado que formaría parte de la selección.

La línea base anterior de 404/65 no se vuelve a certificar por ejecución: el código productivo y dependencias permanecen iguales; esta modificación es solo del fallback de las suites históricas bloqueadas.

## Pruebas nuevas y escáner

| Verificación nueva | Resultado |
|---|---|
| Unitarias del saneador, CLI, escáner y puente PowerShell | **35 aprobadas, 0 fallidas, 0 omitidas** |
| Cinco originales | Hashes intactos; ignorados y no tracked |
| Cinco copias públicas | JSON válido, misma estructura y cero credenciales efectivas |
| Configuración Compose actual | Resuelta sin cambiar recursos; exportación pública validada |
| Contexto Docker | Exclusión estática de `docs/`; inputs necesarios intactos; sin build |
| Referencias históricas | 23 enlaces actualizados; contenido restante igual al respaldo |
| Control negativo del escáner | Rechazo esperado al forzar originales: **10 apariciones de secretos efectivos** |
| Selección final propuesta | Ver [secret-scan.json](evidencias_publicacion/secret-scan.json); cero hallazgos bloqueantes esperados como condición de cierre |

[Resultado final unitario](evidencias_publicacion/sanitizer-tests.xml). Se conservan dos intentos previos: [30 casos, 3 fallas al detectar residuos de asignaciones](evidencias_publicacion/sanitizer-attempt1.xml) y [33 casos, 1 falla de Unicode PowerShell](evidencias_publicacion/sanitizer-attempt2.xml). Ambos contenían solo datos inventados; los defectos del saneador fueron corregidos antes de generar el cierre. No se alteraron XML históricos anteriores a 4A ni se corrigió Ruff.

El escáner `integration/scan_publication.py` toma todos los archivos tracked con diff respecto a HEAD y los untracked relevantes no ignorados. Contrasta credenciales efectivas cargadas del env privado y formatos identificables, sin valores en reportes; falla también si un candidato se llama “redacted”. Un error al leer o analizar la selección rechaza exportar una allowlist. Requiere el env privado disponible para el contraste local; no se versiona ese env.

Las excepciones son estrechas y visibles: texto de JWT/asignaciones dentro de descripciones públicas de vulnerabilidades del informe histórico de dependencias; URI inventadas de dominios reservados `.invalid` en el test del saneador y sus XML. No se ignoran archivos completos ni se eximen coincidencias de secretos efectivos, incluso dentro de esos ejemplos. Las pruebas comprueban que un dominio no aprobado y un secreto efectivo bajo nombre inesperado siguen bloqueando. Una credencial opaca desconocida exige revisión adicional; no se certifica ausencia universal ni el historial completo.

[negative-control.json](evidencias_publicacion/negative-control.json) contiene solo rutas/categorías/conteos. La reproducción local, desde backend, es:

```powershell
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m pytest integration/test_publication.py -q -p no:cacheprovider
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m integration.scan_publication
```

`--include-private-evidence` sirve únicamente como control negativo y debe devolver código 1. `--write-report` emite propuesta de selección solo si el escaneo pasa; no escribe en el índice Git. Reejecutar el escáner ante cualquier cambio posterior.

## Lista permitida y estado Git final

La lista exacta, por ruta y categoría, está en [allowlist.json](evidencias_publicacion/allowlist.json); contiene fuentes productivas, pruebas, scripts/integración, configuración pública, documentación/evidencias revisadas y las copias públicas saneadas. Incluye `.gitignore` raíz y los archivos necesarios de la consolidación acumulada. Excluye expresamente los cinco originales, runtime, claves, env, PDF/PNG/JSON locales de demo y backups. No incluye `HANDOFF_STATE.md` porque no tiene cambios en esta selección; eso no elimina su riesgo histórico.

No usar una inclusión global. Una futura operación deberá seleccionar exclusivamente rutas revisadas de esa lista, comprobar el diff staged y volver a escanearlo. Este documento no ejecuta ni autoriza staging, commit, push, merge o PR.

Estado final y archivos de esta intervención se registran en [final-state.json](evidencias_publicacion/final-state.json). Permanecen la misma rama y HEAD y el índice vacío. Los cinco originales siguen existiendo aunque desaparezcan del listado untracked ordinario por su nueva exclusión.

Archivos existentes cambiados en 4A: `.gitignore` raíz; backend `.dockerignore`, `integration/Common.ps1`, `tests/conftest.py` y exclusivamente enlaces de documentos **13, 17, 18, 19, 20 y 21**. Nuevos: `integration/publication.py`, `integration/scan_publication.py`, `integration/test_publication.py`, las cinco copias públicas, este documento y las evidencias de `docs/evidencias_publicacion/`. Los cambios acumulados de fases anteriores no deben atribuirse a 4A.

## Riesgos abiertos y recomendación

- P05: decidir vigencia/exposición/rotación y eventual saneamiento coordinado de historia; no se hizo ninguna acción externa.
- Ruff: las 454 observaciones pertenecen a la auditoría anterior; no se reejecutó ni corrigió ese gate, y no se afirma una cifra nueva después de agregar herramientas.
- Los bloqueos de plataforma/IA/GCS/catálogo/identidad/privacidad de 24 siguen abiertos; no son objeto del saneamiento.
- Regenerar exactamente las sondas vulnerables requiere su snapshot y otro encargo; no degradar la API corregida para reproducirlas.
- Un ignore puede eludirse con force y la allowlist caduca al cambiar el árbol: revisar nuevamente antes de cualquier publicación.

**Preparación:** existe una selección de backend saneada para revisión y futuro staging, comprobada por el escaneo final. La publicación global sigue condicionada por P05 y el gate de calidad que se abordará separadamente. Se detiene el trabajo en este cierre, sin consolidación Git, sin cambios clínicos y sin modificar recursos Docker.
