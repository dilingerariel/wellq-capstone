# Commit local del backend WellQ — fase 7

Fecha: 2026-11-05. Alcance: consolidación local autorizada, sin push, PR, merge, rebase o cambios a main. P05 y los bloqueos remotos continúan abiertos.

## Estado inicial y protección

Repositorio `C:\Dev\wellq-capstone`, rama `fix/wellq-backend-hardening`, HEAD inicial `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`. Estado inicial: 151 tracked, 22 modificados, 216 nuevos no ignorados, 238 candidatos y cero staged/eliminados. Main local conserva ese mismo hash. Origin/main conserva la punta descargada en fase 6: `339b8cfc4748ee61f178fa57d46cf6eb29a7f78d`; no se ejecuta fetch en esta fase.

Se verificaron el SHA-256 del ZIP de fase 6 y los hashes de sus **10.524 entradas**, sin diferencias: `C:\Dev\wellq-sync-backups\20261105-221029\workspace-private.zip`. Incluye las modificaciones, archivos nuevos y archivos ignorados enumerados entonces, además de metadatos Git. Se mantiene la salvedad de la caché inaccesible descrita en el documento 28.

También se guardó y verificó una copia privada actual de los **367 archivos tracked/nuevos no ignorados** y su manifiesto en `C:\Dev\wellq-sync-backups\phase7-20261105-222406\`, incorporando el informe 28 y los registros de selección actualizados después del respaldo anterior. Estos respaldos pueden contener material privado y permanecen fuera del repositorio.

## Dos correcciones mínimas autorizadas

Se quitó exclusivamente **una línea vacía excedente al final** de cada archivo siguiente. Se conservaron los bytes anteriores a esa línea, la codificación y los finales de línea restantes.

| Archivo relativo a backend | SHA-256 antes | SHA-256 despues |
|---|---|---|
| `docs/24_CONSOLIDACION_GIT_Y_HANDOFF.md` | `9ff8eb8c70c35a113d7456738bf76cc262c26d21c7161b2854086232c020f7c6` | `783a71ea31a4c4dd023359f5833c07d890efd789c5755057025a347998ccf5dd` |
| `integration/Review.ps1` | `a4381f5ba1006c23b9f0468acc69a57b38b4af0c3a8aef17ac1aeff6e6d9d9e6` | `60644a13bbb6f1d0e88e8c9bf28c7471c0c9fcac5bb2313107b3e71ce15b662a` |

Para Review.ps1 se usó el parser de PowerShell antes y después: cero errores en ambos; el texto del AST sin espacios finales permanece igual. Los tokens del cuerpo son idénticos, incluidos sus separadores internos. El total pasa de 403 a 402 tokens exclusivamente por la eliminación del token NewLine final excedente. No se ejecutó el script ni se alteraron sus instrucciones, lógica, parámetros o comportamiento.

No se modificaron frontend, fuentes clínicos, scoring, seguridad, dependencias, contratos API, política Ruff o baseline. Las otras únicas modificaciones propias de esta fase son este documento y los dos registros de selección/escaneo.

## Aceptación explícita de los diez avisos históricos

La autorización de fase 7 permite conservar exclusivamente los diez espacios finales previamente documentados en siete XML históricos. No se aplica una desactivación global de Git ni se ignoran avisos por directorio o extensión.

Los avisos autorizados son exactamente:

| Ruta relativa a backend | Linea | Categoria |
|---|---:|---|
| `docs/evidencias_f01_f07/02_siete_reproducciones_antes.xml` | 8 | trailing whitespace |
| `docs/evidencias_f01_f07/03_primer_intento_tests_nuevos.xml` | 4 | trailing whitespace |
| `docs/evidencias_integracion/clamav-first.xml` | 4 | trailing whitespace |
| `docs/evidencias_integracion/clamav-second.xml` | 4 | trailing whitespace |
| `docs/evidencias_integracion/integration-first.xml` | 5 | trailing whitespace |
| `docs/evidencias_integracion/integration-first.xml` | 10 | trailing whitespace |
| `docs/evidencias_publicacion/sanitizer-attempt2.xml` | 4 | trailing whitespace |
| `docs/evidencias_ruff/integration-attempt1.xml` | 7 | trailing whitespace |
| `docs/evidencias_ruff/integration-attempt1.xml` | 15 | trailing whitespace |
| `docs/evidencias_ruff/integration-attempt1.xml` | 23 | trailing whitespace |

Se parsearon nuevamente los siete XML sin errores y se compararon sus hashes con el manifiesto de fase 6 y el inventario inicial de fase 7. Todos coinciden:

| XML relativo a backend | SHA-256 conservado |
|---|---|
| `docs/evidencias_f01_f07/02_siete_reproducciones_antes.xml` | `9165a801e93e9e06dabad484adceda5bec26e1c4af2fafdea22ad3213fa17583` |
| `docs/evidencias_f01_f07/03_primer_intento_tests_nuevos.xml` | `046c8a3f9a4901f538aa068afff41c2a3eec74797b36ebd5ecf697b2c60b920c` |
| `docs/evidencias_integracion/clamav-first.xml` | `cb9226f52ca196c88cf69739439acf77e7ae66fd13181fc9af905fe9f5c3a49f` |
| `docs/evidencias_integracion/clamav-second.xml` | `a6b48ce6ae2db36732e01b5b7e6e3516297eef9b1271e9a7bedc941aee3bf3d4` |
| `docs/evidencias_integracion/integration-first.xml` | `8d38bed97697e48cb087a4837a1aaaa9906c13eb279db3aab5a64b04346b9467` |
| `docs/evidencias_publicacion/sanitizer-attempt2.xml` | `b320b3fc5941b4a94acda9113cc1afeedd133deb0f2bd4863d5829a6b698901f` |
| `docs/evidencias_ruff/integration-attempt1.xml` | `845219e26f0eb79b0d489e9d7de9c7af75d8b4f1af44984b1a54c54ab42dc69c` |

No se normalizaron los XML, no se alteraron resultados y no se sustituyeron evidencias históricas. Los diez avisos pertenecen a texto de evidencia, no a código ejecutable. Los dos avisos de líneas vacías finales desaparecen por las correcciones autorizadas.

El criterio de aceptación del staging exige igualdad exacta del conjunto ruta/línea/categoría con esos diez avisos, sin ninguna salida no clasificada. `git diff --cached --check` conserva su exit 2 por estos espacios: **no se declara que ese comando pase ni se modifica core.whitespace para forzarlo**. Lo aceptado es la comparación explícita y limitada autorizada por el usuario. Cualquier diferencia adicional impide el commit.

## Comprobaciones anteriores al commit

| Control | Resultado |
|---|---|
| Respaldo de fase 6 y copia actual | Verificados por hashes |
| Correcciones de formato | Solo una línea vacía final eliminada en cada archivo autorizado |
| Sintaxis/AST PowerShell | Cero errores; cuerpo idéntico |
| Evidencias históricas | Siete XML válidos con hashes intactos |
| Fuentes, scripts de aplicación, requirements y snapshot API | 37 archivos contrastados sin cambios desde el inicio |
| OpenAPI | Snapshot idéntico byte a byte; 20 operaciones clínicas y tres operativas |
| Gate Ruff | Aprobado; 414 observaciones, 0 infracciones obligatorias, 0 deuda nueva |
| Política y baseline Ruff | Sin cambios |
| Publicación | Escaneo repetido después de incluir este informe |
| Selección y avisos staged | Véase registro de comprobación siguiente |

La comparación OpenAPI es de integridad del snapshot, coherente con fuentes y dependencias intactos; no se regeneró el esquema. El test del contrato 422 pasó en fase 6. No se declara una validación clínica productiva.

Se reutilizan como **evidencia histórica**, sin presentarlas como nuevas ejecuciones: 448 aprobadas y 209 omitidas de la suite aislada de 4B; 65 aprobadas en Docker de 4B; 32 aprobadas de seguridad/OpenAPI de fase 6. No se repiten suites, Docker ni PDF porque el cambio se limita a formato final, documentación y selección. No hay árbol integrado nuevo.

Comandos principales, desde backend con el intérprete existente:

```powershell
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m integration.quality_gate
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m integration.scan_publication --write-report
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m integration.scan_publication
```

## Selección final y protección de secretos

La [allowlist](evidencias_publicacion/allowlist.json) se regenera después de incorporar este documento: **239 candidatos**, todos existentes, únicos y revisados. Debe coincidir exactamente con las rutas staged. El [reporte de publicación](evidencias_publicacion/secret-scan.json) registra el resultado del escáner existente, sin exportar secretos.

Se incluyen configuración, fuentes runtime, pruebas, herramientas de integración/publicación, Ruff, baseline y documentos/evidencias revisados. Se comprueba que los cinco JSON originales privados permanecen ignorados y con sus hashes de fase 4A, y sus cinco copias públicas pasan el detector de credenciales efectivas y patrones. Runtime, claves, PDF, backups y XML privados ignorados quedan excluidos.

HANDOFF_STATE no se incorpora como modificación nueva. Tampoco se selecciona ninguna de las 11 rutas problemáticas de origin/main ni documentos remotos ajenos. Excluir HANDOFF de los cambios **no elimina su contenido heredado del árbol ni las credenciales de los antecedentes**.

El escáner distingue las fixtures inventadas en dominio reservado .invalid y los ejemplos del aviso público de dependencias mediante las excepciones existentes. No se añaden excepciones de secretos ni se debilita el detector.

Comprobación previa realizada: **239 rutas staged, coincidencia exacta con la allowlist y con el árbol de trabajo; escáner aprobado sin credenciales efectivas ni bloqueos.** Se observaron exactamente los diez avisos históricos autorizados, con las mismas rutas/líneas/categorías y cero avisos adicionales. Los archivos privados quedaron excluidos. Se repite el escaneo y la comprobación del staging tras incorporar este registro, antes de crear el commit.

## Commit autorizado e identificación

Mensaje único autorizado:

```text
fix(backend): consolidate validated clinical backend hardening
```

Este documento se incorpora a la selección **antes del commit**, junto con el reporte y la allowlist. La creación se condiciona a las comprobaciones anteriores y a la igualdad exacta de los diez avisos aceptados.

**Identificador del commit que contiene este informe:** se obtiene mediante:

```powershell
git log -1 --format=%H -- wellq-clinical-tests-main/backend/docs/29_COMMIT_LOCAL_BACKEND.md
```

El hash literal resultante se informa en la respuesta final de ejecución. No se inserta un hash propio dentro del archivo versionado: cambiar ese contenido cambiaría a su vez el identificador del commit. Así se mantiene un solo commit autocontenido, sin amend, commits adicionales o edición posterior de este informe.

## Verificación posterior y estado final

Después de crear el commit se debe verificar su hash, mensaje, padre y lista de cambios contra la selección; rama actual; índice vacío; ausencia de modificaciones/untracked inesperados; hashes del árbol de trabajo; fuentes y evidencias preservados; gate Ruff y escaneo de los **239 archivos exactos incorporados**.

El escáner habitual recorre cambios pendientes: con el árbol limpio puede informar cero candidatos. Eso no equivale a haber escaneado el commit. Por ello la verificación posterior también invoca el detector existente sobre las 239 rutas de la allowlist versionada y contrasta el contenido versionado con el árbol de trabajo mediante Git, incluidos sus filtros de finales de línea.

**Estado final exigido para declarar esta fase completada:** un commit local en fix/wellq-backend-hardening, árbol e índice limpios, 239 archivos incorporados, controles aprobados bajo la excepción documental exacta y main/origin/main intactos. El resultado efectivamente observado y el hash se entregan en la respuesta final; este apartado es el protocolo de comprobación, no evidencia de una operación aún no ejecutada al escribir el informe.

## Bloqueos que permanecen fuera del alcance

- **P05 abierto:** credenciales heredadas en HEAD inicial y antecedentes, además de HANDOFF en el árbol heredado. No se probaron, rotaron o revocaron. Antes de publicar deben intervenir el responsable del repositorio y el de las credenciales según el [plan 27](27_RESOLUCION_P05_Y_PRECOMMIT.md).
- **Origin/main sin integrar:** 11 rutas con espacios finales incompatibles con Windows y un documento de épicas sustituido por un archivo de dos bytes. El equipo debe coordinar nombres válidos y restaurar/verificar el DOCX correcto, preservando el trabajo original. Detalle en el [informe 28](28_SINCRONIZACION_GITHUB_Y_CONSOLIDACION_LOCAL.md).
- Proveedores externos, despliegue, identidad y validación clínica productiva conservan sus límites anteriores.

Un commit local aprobado no habilita push ni PR. No se resuelven estos bloqueos cambiando el backend ni se modifica main. El trabajo se detiene tras la consolidación local y su verificación.
