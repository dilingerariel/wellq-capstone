# Sincronización GitHub y consolidación local — fase 6

Fecha: 2026-11-05. **Avances remotos revisados; consolidación local detenida y publicación prohibida.** Se completaron respaldo, fetch, análisis y verificaciones. No se creó commit porque falló la comprobación de espacios del contenido staged. Tampoco se integró origin/main: contiene rutas rechazadas por Git en Windows y un documento DOCX sustituido por un archivo de dos bytes.

## 1. Estado inicial, respaldo y preservación

Rama: `fix/wellq-backend-hardening`. HEAD inicial y final: `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`. La rama local `main` conserva ese mismo hash; no se modificó.

Estado inicial: 151 archivos tracked, 22 modificados, 215 nuevos no ignorados, 237 candidatos y cero staged/eliminados. Respaldo privado: `C:\Dev\wellq-sync-backups\20261105-221029\`.

El ZIP privado incluye los **366 archivos tracked/nuevos, 9.730 ignorados y los archivos regulares de .git: 10.524 entradas**. Se verificó cada entrada mediante SHA-256 contra los bytes leídos; cero fallos de lectura y cero diferencias. Tamaño del ZIP: 120.811.753 bytes. El manifiesto privado registra hashes, rama, HEAD, estado y referencias anteriores. Contiene secretos heredados, runtime y claves: conservar fuera de Git, con acceso restringido; no adjuntarlo a un PR.

Git avisó que no puede enumerar un directorio .pytest_cache por permisos. No hubo errores de lectura en los archivos efectivamente enumerados y respaldados; no se afirma haber copiado posibles entradas inaccesibles de esa caché. No se alteraron sus permisos. La verificación cubre todos los archivos fuente nuevos y modificaciones sin commit inventariados.

Se conservaron fuentes, dependencias, frontend, evidencias, originales privados y PDF. Solo se agrega este informe y se actualizan allowlist/reporte de publicación para incluirlo. Los cambios de .git corresponden al fetch y al staging temporal autorizado, posteriormente deshecho únicamente en el índice. No se ejecutaron reset, clean, stash, pull, rebase, cambios de rama ni comandos Docker.

## 2. Fetch y ramas remotas

Se ejecutó exclusivamente `git fetch origin` para descargar referencias, sin pull ni fusión automática. Terminó con exit 0. La salida del transporte se mantuvo privada para evitar divulgar URLs o material de autenticación.

| Referencia | Antes | Después | Cambios nuevos y relevancia |
|---|---|---|---|
| origin/main | fb8746c | 339b8cf | 30 commits de organización documental académica |
| origin/HEAD | fb8746c | 339b8cf | Alias de la punta principal; mismo avance |
| origin/ariel-componente-f | f315247 | f315247 | Sin novedades; no se propone fusionar otra vez |
| origin/feature/juan-frontend | fb8746c | fb8746c | Sin novedades; no hay un avance frontend nuevo que integrar |

Hash completo actual de origin/main: `339b8cfc4748ee61f178fa57d46cf6eb29a7f78d`. La diferencia de commits entre HEAD y origin/main es **0 exclusivos locales / 30 exclusivos remotos**. Los cambios locales aún sin commit no se cuentan como commits exclusivos. Las novedades están en main, no solamente en una rama secundaria.

Los 30 commits nuevos registran autor **Benjamin** y committer **GitHub**, todos con fecha 2026-11-05 entre 15:13:49 y 16:08:22, zona -03:00. Se informa el metadato del historial: no permite atribuir la subida a una persona distinta ni confirmar quién operó una cuenta. Las puntas sin cambios registran autor dilingerariel: ariel-componente-f, 2026-10-29 21:50:26 -03:00; feature/juan-frontend, 2026-10-29 21:52:46 -03:00, committer GitHub. El nombre de una rama no acredita por sí solo autoría.

| Commit nuevo | Autor | Fecha (-03:00) | Archivos del commit (inventario de rutas) |
|---|---|---|---|
| `252d7d5cbbabe879df65e01059c8ba6411bbebb2` | Benjamin | 2026-11-05T15:13:49-03:00 | `A -> FASE 2/EVIDENCIAS PROYECTO/Entrega Individual/a.txt` |
| `07ee707e617dd2ca4641090301faa3a1aac75165` | Benjamin | 2026-11-05T15:17:56-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/2.1_APT122_DiarioReflexionFase2_Benjamín_Fernández.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Individual /2.1_APT122_DiarioReflexionFase2_Benjamín_Fernández.docx` |
| `2f2ebf1c4ba679908fc925cc3a248a0bc055ffce` | Benjamin | 2026-11-05T15:19:36-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/2.1_APT122_DiarioReflexionFase2_ArielRodriguez.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Individual /2.1_APT122_DiarioReflexionFase2_ArielRodriguez.docx` |
| `bc2f9b34401aa6acd73b5a301e8f0fcee8e09ed8` | Benjamin | 2026-11-05T15:20:04-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/2.1_APT122_DiarioReflexionFase2_JuanPabloVega.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Individual /2.1_APT122_DiarioReflexionFase2_JuanPabloVega.docx` |
| `54b2f3faee4e562aec227fa1bee3dec45761766c` | Benjamin | 2026-11-05T15:20:47-03:00 | `D -> FASE 2/EVIDENCIAS PROYECTO/Entrega Individual/a.txt` |
| `84216fe73be58dcdea7f661c4452b4e4de06b429` | Benjamin | 2026-11-05T15:21:58-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/2.4_GuiaEstudiante_Fase 2_DesarrolloProyecto APT.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /2.4_GuiaEstudiante_Fase 2_DesarrolloProyecto APT.docx` |
| `6a25cf89a5144ef4b18af2e421323aab9f8d4318` | Benjamin | 2026-11-05T15:27:54-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/01 Documento de Visión y Roles Scrum.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales/01 Documento de Visión y Roles Scrum.docx` |
| `8afe6a46f338497c6420fda0baf7aefb4a6ce68d` | Benjamin | 2026-11-05T15:28:30-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /2.4_GuiaEstudiante_Fase 2_DesarrolloProyecto APT.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales  /2.4_GuiaEstudiante_Fase 2_DesarrolloProyecto APT.docx` |
| `b8c948d40c78ea7845fc449aaff9a81ec21428ca` | Benjamin | 2026-11-05T15:29:18-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales  /2.4_GuiaEstudiante_Fase 2_DesarrolloProyecto APT.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /2.4_GuiaEstudiante_Fase 2_DesarrolloProyecto APT.docx` |
| `8cda81ef9f805c91db20f7340adae6d7dea1bd60` | Benjamin | 2026-11-05T15:29:51-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales/01 Documento de Visión y Roles Scrum.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /01 Documento de Visión y Roles Scrum.docx` |
| `e0441ecec78f5133210eddbd298e222966576c08` | Benjamin | 2026-11-05T15:30:15-03:00 | `D -> FASE 2/EVIDENCIAS PROYECTO/02_Documento_de_Epicas_e_Historias_de_Usuario_WellQ.docx`; `A -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /02_Documento_de_Epicas_e_Historias_de_Usuario_WellQ.docx` |
| `35e32681f62d8dd1dd326532511ac9cf2ad7f0da` | Benjamin | 2026-11-05T15:32:13-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/03_Plantilla_Historias_de_Usuario_WellQ(1).xlsx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /03_Plantilla_Historias_de_Usuario_WellQ(1).xlsx` |
| `7b332b72b830d51580027244ca7e380ac8a6ad7e` | Benjamin | 2026-11-05T15:32:30-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx` |
| `86e1699a60da4de6a878e56199a624a8730e5076` | Benjamin | 2026-11-05T15:32:56-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/C1 Documento de Arquitectura de Software (DAS) (5).docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /C1 Documento de Arquitectura de Software (DAS) (5).docx` |
| `0e6777c8a2ef7695fa2dffaea1518c53372bf435` | Benjamin | 2026-11-05T15:33:23-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Requerimientos_Funcionales_y_No_Funcionales.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /Requerimientos_Funcionales_y_No_Funcionales.docx` |
| `dc990cca95e7c7edec7407c411936beb7fb289f8` | Benjamin | 2026-11-05T15:34:39-03:00 | `R100 -> Modelo conceptual (MER)/Modelo conceptual (MER).zip -> FASE 2/EVIDENCIAS PROYECTO /MER` |
| `e52867f65dfb1f8d3a951171123877406f8c4adf` | Benjamin | 2026-11-05T15:35:44-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO /MER -> FASE 2/EVIDENCIAS PROYECTO/MER` |
| `656cfd89eb9281c050fa882cbd2519f3740bd8fc` | Benjamin | 2026-11-05T15:36:42-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/MER -> FASE 2/EVIDENCIAS PROYECTO/Modelo/MER` |
| `a8d3df7afd73ea549d021a08227beb8badaf117f` | Benjamin | 2026-11-05T15:38:41-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Modelo/MER -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales/MER` |
| `5742849ed739d8b16a5b7f9f414c6878f2309ecb` | Benjamin | 2026-11-05T15:39:22-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales/MER -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /MER` |
| `c5d92a1adf98d9c5fcbed880c1b28d505a67850c` | Benjamin | 2026-11-05T15:45:52-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /MER -> FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto/MER` |
| `21c00c53d53fd0cfafc02de227bd3c88e44b31ab` | Benjamin | 2026-11-05T16:04:05-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /Requerimientos_Funcionales_y_No_Funcionales.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /Requerimientos_Funcionales_y_No_Funcionales.docx` |
| `5111064216ca48b546e8527b861b63d396a9f020` | Benjamin | 2026-11-05T16:04:35-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /C1 Documento de Arquitectura de Software (DAS) (5).docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /C1 Documento de Arquitectura de Software (DAS) (5).docx` |
| `4137eb406abfbb7a4135d140a4ead4f7f1bdead6` | Benjamin | 2026-11-05T16:05:04-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx -> FASE 2/EVIDENCIAS PROYECTO/Evidencias ProyectEvidencias Proyecto /04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx` |
| `7a9798c5e4d3c5623d6ed4f44787001744f9bb05` | Benjamin | 2026-11-05T16:06:19-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencias ProyectEvidencias Proyecto /04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx -> FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto/04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx` |
| `0b89d7c5d51464d852eb4c3dda49e151ecdf813a` | Benjamin | 2026-11-05T16:06:50-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto/04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx -> FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx` |
| `790847520e9b3a44ba5b991a1c4948e11ac1a41e` | Benjamin | 2026-11-05T16:07:11-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto/MER -> FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /MER` |
| `9c8d4dda6a711e3986ac04d1ae2926dd8e66344f` | Benjamin | 2026-11-05T16:07:35-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /03_Plantilla_Historias_de_Usuario_WellQ(1).xlsx -> FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /03_Plantilla_Historias_de_Usuario_WellQ(1).xlsx` |
| `99f1e0feff315de9c86d0af0a1f14b86a1693053` | Benjamin | 2026-11-05T16:07:56-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /02_Documento_de_Epicas_e_Historias_de_Usuario_WellQ.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /02_Documento_de_Epicas_e_Historias_de_Usuario_WellQ.docx` |
| `339b8cfc4748ee61f178fa57d46cf6eb29a7f78d` | Benjamin | 2026-11-05T16:08:22-03:00 | `R100 -> FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /01 Documento de Visión y Roles Scrum.docx -> FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /01 Documento de Visión y Roles Scrum.docx` |

## 3. Archivos afectados y diferencias con el trabajo local

El efecto neto son **10 renombres R100 con bytes idénticos y un par eliminación/adición con contenido distinto**. El archivo temporal Entrega Individual/a.txt fue creado y eliminado dentro de los 30 commits y no queda en el diff neto. Hubo varios movimientos intermedios de las mismas evidencias.

| Estado neto | Origen | Destino |
|---|---|---|
| D | `FASE 2/EVIDENCIAS PROYECTO/02_Documento_de_Epicas_e_Historias_de_Usuario_WellQ.docx` | `-` |
| R100 | `FASE 2/EVIDENCIAS PROYECTO/2.4_GuiaEstudiante_Fase 2_DesarrolloProyecto APT.docx` | `FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /2.4_GuiaEstudiante_Fase 2_DesarrolloProyecto APT.docx` |
| R100 | `FASE 2/EVIDENCIAS PROYECTO/2.1_APT122_DiarioReflexionFase2_ArielRodriguez.docx` | `FASE 2/EVIDENCIAS PROYECTO/Evidencia Individual /2.1_APT122_DiarioReflexionFase2_ArielRodriguez.docx` |
| R100 | `FASE 2/EVIDENCIAS PROYECTO/2.1_APT122_DiarioReflexionFase2_Benjamín_Fernández.docx` | `FASE 2/EVIDENCIAS PROYECTO/Evidencia Individual /2.1_APT122_DiarioReflexionFase2_Benjamín_Fernández.docx` |
| R100 | `FASE 2/EVIDENCIAS PROYECTO/2.1_APT122_DiarioReflexionFase2_JuanPabloVega.docx` | `FASE 2/EVIDENCIAS PROYECTO/Evidencia Individual /2.1_APT122_DiarioReflexionFase2_JuanPabloVega.docx` |
| R100 | `FASE 2/EVIDENCIAS PROYECTO/01 Documento de Visión y Roles Scrum.docx` | `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /01 Documento de Visión y Roles Scrum.docx` |
| A | `-` | `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /02_Documento_de_Epicas_e_Historias_de_Usuario_WellQ.docx` |
| R100 | `FASE 2/EVIDENCIAS PROYECTO/03_Plantilla_Historias_de_Usuario_WellQ(1).xlsx` | `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /03_Plantilla_Historias_de_Usuario_WellQ(1).xlsx` |
| R100 | `FASE 2/EVIDENCIAS PROYECTO/04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx` | `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx` |
| R100 | `FASE 2/EVIDENCIAS PROYECTO/C1 Documento de Arquitectura de Software (DAS) (5).docx` | `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /C1 Documento de Arquitectura de Software (DAS) (5).docx` |
| R100 | `Modelo conceptual (MER)/Modelo conceptual (MER).zip` | `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /MER` |
| R100 | `FASE 2/EVIDENCIAS PROYECTO/Requerimientos_Funcionales_y_No_Funcionales.docx` | `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /Requerimientos_Funcionales_y_No_Funcionales.docx` |

Las carpetas `Evidencia Grupales `, `Evidencia Individual ` y `Evidencias Proyecto ` tienen un espacio al final de su nombre antes de la barra. No se normalizan silenciosamente ni se sustituyen documentos de colaboradores por copias locales.

| Área | Resultado del contraste remoto |
|---|---|
| Autenticación y JWT | Sin cambios remotos de código/configuración |
| FastAPI, MongoDB y persistencia | Sin cambios remotos |
| Modelos, esquemas y endpoints | Sin cambios remotos |
| React y Flutter | Sin cambios remotos de fuentes |
| Docker y dependencias | Sin cambios remotos |
| Scoring y PDF | Sin cambios remotos |
| Pruebas y configuración | Sin cambios remotos |
| Documentación académica, backlog, arquitectura y MER | Renombres y sustitución anómala de épicas; requiere decisión del equipo |

Cero intersecciones entre las rutas modificadas/nuevas locales y las rutas remotas afectadas. No se detectaron modificaciones concurrentes de lógica clínica, seguridad o persistencia. Esto acredita ausencia de cambios remotos en esos fuentes, no una revisión clínica del contenido académico. Los diez renombres conservan contenido por comparación Git R100. El único reemplazo diferente se analizó por formato y tamaño, sin interpretar sus contenidos como instrucciones para el agente.

## 4. Conflictos y decisión de no integrar main

**Bloqueo técnico: 11 rutas no compatibles con el checkout Windows.** Una prueba separada con `git -c core.protectNTFS=true read-tree --index-output=<índice privado> origin/main` terminó con exit 128 e invalid path. La prueba escribió únicamente un índice de diagnóstico fuera del repositorio; no modificó el índice real ni el árbol de trabajo.

- `FASE 2/EVIDENCIAS PROYECTO/Evidencia Grupales /2.4_GuiaEstudiante_Fase 2_DesarrolloProyecto APT.docx`.
- `FASE 2/EVIDENCIAS PROYECTO/Evidencia Individual /2.1_APT122_DiarioReflexionFase2_ArielRodriguez.docx`.
- `FASE 2/EVIDENCIAS PROYECTO/Evidencia Individual /2.1_APT122_DiarioReflexionFase2_Benjamín_Fernández.docx`.
- `FASE 2/EVIDENCIAS PROYECTO/Evidencia Individual /2.1_APT122_DiarioReflexionFase2_JuanPabloVega.docx`.
- `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /01 Documento de Visión y Roles Scrum.docx`.
- `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /02_Documento_de_Epicas_e_Historias_de_Usuario_WellQ.docx`.
- `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /03_Plantilla_Historias_de_Usuario_WellQ(1).xlsx`.
- `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx`.
- `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /C1 Documento de Arquitectura de Software (DAS) (5).docx`.
- `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /MER`.
- `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /Requerimientos_Funcionales_y_No_Funcionales.docx`.

**Bloqueo documental: un reemplazo que pierde contenido.** El documento de épicas original es un DOCX ZIP válido de **3.297.793 bytes**; la nueva ruta tiene **2 bytes**, no es ZIP/DOCX válido ni un puntero Git LFS. No se atribuye intención ni se inventa contenido perdido. El original está intacto en el árbol local y en el respaldo; el blob remoto sigue disponible para revisión.

No se ejecutó merge, por lo que hay **cero archivos unmerged** y no existe una fusión en curso. Se identifican preventivamente dos clases de bloqueo: 11 rutas incompatibles y una sustitución documental anómala, que afecta una de esas mismas 11 rutas. No son doce archivos distintos.

Alternativas a decidir con el equipo:

1. Recomendada: que el responsable de esos cambios prepare un commit correctivo coordinado, sin espacios finales en directorios y restaurando el DOCX correcto tras confirmar la intención de la sustitución. Después volver a hacer fetch, analizar e integrar main en esta rama si queda compatible.
2. Evaluar una integración en un entorno compatible y una normalización explícita mediante un commit nuevo en una rama de integración, después de acordar nombres y resolver el documento. No desactivar protectNTFS ni aplicar el checkout sobre este árbol para forzarlo.
3. Mantener ambas líneas separadas mientras se decide; no cherry-pick ni fusionar una rama secundaria suponiendo que resuelve estos problemas.

No se modifica main ni se corrigen nombres/documentos ajenos automáticamente.

## 5. Selección, staging revisado y commit detenido

Se regeneró la allowlist con el escáner existente. La propuesta previa al intento contenía exactamente **237 rutas**, coincidentes con los candidatos y sin duplicados/faltantes. Escáner aprobado, cero credenciales efectivas detectadas y cero hallazgos bloqueantes. Se verificó que incluía fuentes, configuración, tests, gate/baseline y herramientas de publicación necesarias, excluyendo HANDOFF_STATE, runtime, claves, PDF y originales privados.

Se preparó staging exclusivamente mediante un archivo NUL de esas rutas y pathspecs literales. No se usaron git add ., -A o -f. Las 237 rutas staged coincidían exactamente con la allowlist; `git diff --quiet` confirmó correspondencia entre índice y árbol aplicando filtros Git, sin volcar líneas del diff.

**La comprobación adicional git diff --cached --check falló con exit 2: 12 avisos en nueve archivos.** Antes del staging, git diff --check pasaba porque no abarcaba el contenido de los archivos nuevos. No se presenta aquella comprobación como verificación de todos los candidatos.

| Ruta relativa a backend | Linea | Aviso |
|---|---:|---|
| `docs/24_CONSOLIDACION_GIT_Y_HANDOFF.md` | 415 | new blank line at EOF |
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
| `integration/Review.ps1` | 43 | new blank line at EOF |

Son diez avisos de espacios finales en XML históricos y dos líneas vacías finales en un documento/script. No son fallos de Ruff ni detecciones de secretos. No se sobrescriben esas evidencias para ocultarlos.

La sección 4 del encargo exige: **“Si alguna comprobación falla, detén el commit y documenta el bloqueo.”** Se aplicó esa instrucción: **no se creó commit y no hay un hash nuevo que reportar**. El staging temporal se retiró mediante git restore --staged con las mismas rutas explícitas, sin tocar el árbol. El índice vuelve a quedar vacío, igual que al comenzar.

Para reintentar la consolidación se debe acordar cómo tratar esos espacios: corrección mínima de documento/script y, para las evidencias históricas, conservación de originales y copias públicas normalizadas con procedencia y comparación de resultados, o una aceptación explícita de esos avisos documentales como no bloqueantes. No se cambia la política ni se presume esa aceptación en esta fase.

## 6. Calidad, pruebas y contratos: resultados nuevos

| Control | Resultado de fase 6 |
|---|---|
| Gate integration.quality_gate | Exit 0; 414 observaciones existentes, 0 obligatorias y 0 deuda nueva |
| Escáner antes del staging | Exit 0; 237 candidatos, 0 secretos efectivos y 0 bloqueos |
| Selección staged | 237 rutas exactas; sin evidencias privadas ni cambios ajenos |
| git diff --cached --check | Exit 2; 12 avisos, nueve archivos; commit detenido |
| Seguridad y contrato OpenAPI focalizados | **32 aprobadas, 0 fallos**, 11 advertencias de deprecación |
| Escáner final incluyendo este informe | Exit 0; **238 candidatos**, 0 secretos efectivos y 0 bloqueos |
| Preservación | Fuentes y dependencias sin cambios; originales privados intactos |

Se ejecutó desde backend:

```powershell
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m integration.quality_gate
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m integration.scan_publication --write-report
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m pytest checks/test_security.py checks/test_final_defects.py::test_openapi_error_envelope_matches_actual_422 -q -p no:cacheprovider --junitxml <respaldo-privado>\security-openapi.xml
```

Las 32 pruebas verifican claims/JWT, firma ajena y HMAC rechazados, configuración ausente, aislamiento de lecturas/escrituras por tenant, permisos por paciente/rol, accesos anónimos, mensajes de validación, rate limit, auditoría append-only, CORS/cache privado y contrato del error 422. Son pruebas aisladas con dobles; no acreditan integración nueva con Mongo o proveedores reales. El XML y los inventarios de diagnóstico se conservan en el respaldo privado indicado.

El snapshot OpenAPI no se modificó y declara **20 operaciones clínicas y tres operativas**. El test focalizado consulta además el OpenAPI de la aplicación para validar el contrato de errores; no se presenta como una nueva comparación exhaustiva de todo OpenAPI. La política Ruff, baseline y sus 414 observaciones conservan sus bytes.

Las evidencias de **448 aprobadas y 209 omitidas** y **65 aprobadas en Docker** siguen siendo históricas de 4B. No se repitieron ni se atribuyen a un árbol integrado: **no hubo integración** y no cambiaron fuentes/dependencias. No se regeneraron PDF ni OpenAPI, no se tocó Docker ni se accedió a bases de producción.

## 7. Allowlist final y evidencias privadas

[Allowlist](evidencias_publicacion/allowlist.json) y [escaneo](evidencias_publicacion/secret-scan.json) se actualizan para los **238 candidatos finales**, incluido este documento. Son una propuesta de futura selección, no staging ni autorización de publicación.

Los cinco JSON originales privados permanecen ignorados, fuera de la selección y con los hashes de [fase 4A](evidencias_publicacion/validation.json). Sus cinco copias públicas se vuelven a contrastar con el escáner; no hay hallazgos. Las reglas ignore, saneador y escáner permanecen intactos. No entran claves, runtime, PDF, backups ni HANDOFF_STATE como cambios nuevos. El escaneo se limita a los candidatos; no certifica HEAD completo ni la historia.

## 8. P05 y condiciones para un futuro PR

**P05 continúa abierto.** Los archivos afectados no cambiaron en los commits remotos nuevos; fetch no sanea la historia. Las credenciales heredadas siguen en HEAD y antecedentes, y en la historia descargada de origin/main. No se probaron, rotaron ni se consultaron servicios con ellas.

Se mantienen [las recomendaciones del documento 27](27_RESOLUCION_P05_Y_PRECOMMIT.md): identificar responsables/cuentas por canales privados; aprobar y acreditar revocación o rotación; corregir HANDOFF con ejemplos sin secretos; decidir un saneamiento coordinado de ramas/copias o una aceptación explícita del riesgo residual. No se reescribe historia ni se envían comunicaciones al equipo automáticamente.

Antes de un PR: resolver el bloqueo de espacios de la selección, revalidar y autorizar el commit local; resolver con el equipo las rutas Windows y el DOCX, volver a fetch e integrar main solo tras revisar la corrección; ejecutar los controles afectados por el árbol que resulte; resolver P05 con evidencia del propietario; obtener autorización para publicación. No se hace push, PR ni merge hacia main.

## 9. Dictamen

- **Rama local consolidada: no.** Commit detenido por comprobación fallida; código preservado.
- **Avances remotos revisados: sí.** Treinta commits nuevos en main; otras ramas sin novedades.
- **Avances de main integrados: no.** Bloqueos técnicos/documentales identificados antes de fusionar.
- **Conflictos pendientes:** cero conflictos Git unmerged; 11 rutas Windows y una sustitución documental anómala en ese conjunto. Adicionalmente, 12 avisos de espacios en nueve archivos locales impiden continuar el commit bajo la instrucción recibida.
- **Estado final:** misma rama y HEAD; 22 tracked modificados, 216 nuevos no ignorados, 238 candidatos y cero staged/eliminados. Ningún commit nuevo.
- **Publicación permitida: no.** P05 sigue pendiente; tampoco se autoriza publicar los cambios remotos problemáticos.
- **Próximo paso recomendado:** acordar el tratamiento de los avisos locales y solicitar al responsable del avance remoto una corrección de nombres y del DOCX, mientras los dueños de credenciales ejecutan el plan P05 autorizado.

La fase termina documentando los bloqueos, sin forzar la integración ni avanzar a otra fase.
