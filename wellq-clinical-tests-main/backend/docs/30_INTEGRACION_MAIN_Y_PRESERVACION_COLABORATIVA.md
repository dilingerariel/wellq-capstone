# Integración de main y preservación colaborativa — fase 8

Fecha: 2026-11-05. **Integración detenida antes de ejecutar merge: persisten los dos bloqueos técnicos comprobados en fase 6.** La organización académica aprobada por el equipo se respeta íntegramente. No se reorganizan carpetas, renombran documentos, sustituyen entregas ni revierten commits.

## 1. Estado inicial de Git

Repositorio: `C:\Dev\wellq-capstone`. Rama: `fix/wellq-backend-hardening`. HEAD inicial y final: **`1684c743574594da417091cf6a266d6f02ac43cf`**.

El commit local de consolidación existe, conserva sus 239 archivos incorporados y el árbol estaba limpio al iniciar: cero modificaciones tracked, cero nuevos no ignorados y cero staged. Se inventariaron los hashes de los 368 archivos tracked disponibles en disco. Git verifica los archivos guardados; esta comprobación no inspecciona posibles buffers sin guardar del editor.

Main local sigue en `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`. No se modificó esa rama ni se cambió de rama de trabajo.

## 2. Respaldos disponibles y verificados

Se verificaron otra vez los respaldos privados anteriores:

| Respaldo externo | Comprobación nueva |
|---|---|
| `C:\Dev\wellq-sync-backups\20261105-221029\workspace-private.zip` | Hash del ZIP y hashes de sus 10.524 entradas coincidentes con el manifiesto de fase 6 |
| `C:\Dev\wellq-sync-backups\phase7-20261105-222406\current-worktree-private.zip` | Las 367 entradas coinciden con el manifiesto inicial de fase 7 |

Los registros privados de inspección de esta fase quedan en `C:\Dev\wellq-sync-backups\phase8-inspection\`. Los respaldos contienen material que debe permanecer privado y no se agregan al repositorio. No se descartó trabajo ni se ejecutaron reset, clean, stash o rebase.

## 3. Resultado del fetch

Se ejecutó **git fetch origin**, con exit 0, sin pull, merge ni actualización del checkout. La salida del transporte no se volcó al informe para evitar divulgar URLs o autenticación.

| Referencia | Antes de este fetch | Después |
|---|---|---|
| origin/main | `339b8cfc4748ee61f178fa57d46cf6eb29a7f78d` | Sin cambio |
| origin/HEAD | `339b8cfc4748ee61f178fa57d46cf6eb29a7f78d` | Sin cambio |
| origin/ariel-componente-f | `f3152478396ad4f90e47586103511d0eb03481e7` | Sin cambio |
| origin/feature/juan-frontend | `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e` | Sin cambio |

**No hay commits nuevos en las referencias descargadas desde la revisión de fase 6.** La afirmación se limita a esas referencias disponibles al terminar este fetch; no describe cambios privados, buffers, ramas no anunciadas o trabajo aún sin publicar.

## 4. Commits y archivos remotos afectados

Respecto a la base común `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`, origin/main mantiene los **30 commits ya revisados**, sin añadidos posteriores. El historial registra autor Benjamin y committer GitHub, con fechas del 2026-11-05 entre 15:13:49 y 16:08:22, zona -03:00. Son metadatos Git, no una atribución de quién operó físicamente la cuenta.

La rama local tiene un commit exclusivo —la consolidación del backend— y origin/main tiene 30 exclusivos. La comparación de avances remotos se hace desde la base común para no interpretar los cambios propios del backend como eliminaciones realizadas por compañeros.

Efecto neto remoto: **10 renombres R100 de contenido idéntico y una eliminación/adición del documento de épicas con contenido distinto**. El inventario completo de los 30 commits y rutas está en el [informe 28](28_SINCRONIZACION_GITHUB_Y_CONSOLIDACION_LOCAL.md). Se volvió a contrastar el diff neto del árbol remoto en esta fase.

| Estado | Origen | Destino |
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

Los avances remotos siguen limitados a documentación académica y el MER. No cambian fuentes de FastAPI/Mongo, JWT, modelos, endpoints, React, Flutter, Docker, dependencias, scoring, PDF, pruebas o configuración del backend. El cambio académico no se trata como una modificación de código.

## 5. Compatibilidad técnica con Windows

**Las 11 rutas problemáticas siguen presentes.** Se enumeró el árbol Git remoto directamente, sin escribir esos documentos en el checkout:

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

Las rutas conservan segmentos con un espacio al final, antes de la barra. Los tres segmentos afectados son:

| Segmento actual, usando [espacio] para hacerlo visible | Corrección técnica mínima a coordinar |
|---|---|
| `Evidencia Grupales[espacio]` | Quitar únicamente el espacio final invisible |
| `Evidencia Individual[espacio]` | Quitar únicamente el espacio final invisible |
| `Evidencias Proyecto[espacio]` | Quitar únicamente el espacio final invisible |

Esta es una propuesta técnica para el equipo, **no un renombre aplicado ni una nueva organización académica**. Deben mantenerse jerarquía, agrupaciones, nombres visibles y contenidos aprobados. El responsable debe acordar y realizar la corrección compatible con Windows; no se cambia el singular/plural ni se mueven entregas por criterio del agente.

Una prueba en un índice privado separado, con `git -c core.protectNTFS=true read-tree --index-output=<índice privado> origin/main`, terminó con **exit 128, invalid path**. No se modificó el índice real. No se desactivó core.protectNTFS ni se intentó forzar el checkout.

## 6. Documento remoto de épicas

Ruta actual: `FASE 2/EVIDENCIAS PROYECTO/Evidencias Proyecto /02_Documento_de_Epicas_e_Historias_de_Usuario_WellQ.docx`.

| Versión inspeccionada en memoria | Tamaño | ZIP válido | Paquete DOCX |
|---|---:|---|---|
| Origin/main actual | **2 bytes** | No | No |
| Archivo de la base común, en su ruta anterior | **3.297.793 bytes** | Sí | Sí: contiene las partes esperadas |

El archivo actual tampoco es un puntero Git LFS. La extensión .docx no acredita que el contenido sea un documento válido. No se imprimió contenido privado, se extrajeron documentos al checkout ni se ejecutaron instrucciones de documentos.

La organización académica puede estar terminada según el equipo y este problema técnico seguir existiendo en el árbol descargado. **No se elige automáticamente la versión antigua como entrega correcta.** El responsable debe identificar el DOCX completo y aprobado por el equipo y cargarlo en el destino académico acordado, conservando su ubicación lógica y el contenido final aprobado. El archivo anterior solo se usa para demostrar la diferencia detectable y permanece disponible como referencia privada.

## 7. Preservación del trabajo colaborativo

No se modificó ningún archivo académico, ni su nombre, orden, contenido o ubicación. No se eliminó ninguna entrega local ni se revirtieron commits remotos. Los objetos y referencias descargados conservan exactamente el resultado publicado por el compañero.

El checkout local conserva los documentos que tenía antes de esta fase; **no se afirma que ya refleje la organización de origin/main**, porque la integración se ha detenido. Los diez renombres idénticos y la sustitución anómala siguen en el historial remoto descargado, disponibles para revisión por el equipo.

## 8. Resultado del merge local

**No se ejecutó merge.** La sección 6 del encargo exige detener la integración si persiste cualquiera de los dos problemas. Ambos continúan y requieren coordinación humana.

No existe MERGE_HEAD ni archivos unmerged. El backend consolidado sigue en HEAD. No se crea un commit adicional, se hace rebase, se modifica main o se fuerza una resolución. El estado es recuperable sin operaciones de deshacer una fusión: nunca se inició.

## 9. Integridad del backend y contratos

Se compararon los hashes de los **368 archivos tracked iniciales** antes y después del fetch y al cierre: cero cambios o faltantes. Esto abarca backend, dependencias, configuración, frontend y los documentos académicos locales.

OpenAPI conserva sus bytes y declara **20 operaciones clínicas y tres operativas**. No se regeneró. Scoring, PDF, permisos, seguridad, aislamiento entre tenants y contratos no cambiaron en esta fase. Esta comprobación de integridad no reemplaza una validación clínica productiva ni afirma que se ejecutó nuevamente toda la aplicación.

## 10. Gate Ruff

Ejecución nueva de `python -m integration.quality_gate` desde backend, con el intérprete del venv existente:

- Exit 0, aprobado.
- 414 observaciones existentes.
- Cero infracciones obligatorias y cero deuda nueva.
- Política, configuración y baseline intactos.

No equivale a Ruff estricto sin advertencias. Se conserva la [política documentada en fase 4B](26_CALIDAD_RUFF_Y_GATE_CI.md).

## 11. Escaneo de publicación

Se ejecutó el detector existente sobre las **239 rutas de la allowlist versionada**: cero credenciales efectivas detectadas y cero bloqueos. Se comprueba también este informe mediante el comando habitual `python -m integration.scan_publication`, cuyo alcance final es el único archivo nuevo de esta fase: cero hallazgos bloqueantes.

La allowlist y el reporte versionados no se reescriben: documentan la selección de consolidación del commit anterior. El informe 30 queda nuevo, sin seguimiento ni staging; una futura selección deberá incorporarlo explícitamente si se decide versionarlo. No se modifican reglas ignore, excepciones de secretos, claves, runtime o evidencias privadas.

Este escaneo de archivos seleccionados no certifica la historia completa, el árbol heredado entero o los documentos binarios remotos. No se trasladaron esos documentos a una selección de publicación.

## 12. Pruebas y evidencia histórica

No se ejecutaron suites ni Docker: no hubo integración ni cambios productivos, de dependencias o configuración. Se reutilizan, identificadas como **históricas**:

| Evidencia | Resultado anterior |
|---|---|
| Suite aislada final de 4B | 448 aprobadas, 209 omitidas |
| HTTP/Mongo Docker aislado de 4B | 65 aprobadas |
| Seguridad y contrato OpenAPI de fase 6 | 32 aprobadas |

Su aplicabilidad se sustenta en fuentes y dependencias intactos, no en una ejecución nueva. No se atribuyen resultados a un árbol integrado que no existe. Tampoco se regeneran PDF o artefactos visuales.

## 13. Bloqueos y P05

Bloqueos de integración: **11 rutas incompatibles con Windows y un DOCX inválido dentro de ese conjunto**. Son dos clases de problema; no doce rutas distintas. Cero conflictos Git abiertos, porque no se inició merge.

**P05 sigue abierto.** Un fetch, un escáner de candidatos aprobado o un futuro merge local no revocan credenciales ni eliminan los datos históricos. No se probaron credenciales antiguas, modificaron servidores ni se reescribió historia. Se mantienen las decisiones pendientes del [plan 27](27_RESOLUCION_P05_Y_PRECOMMIT.md): propietarios de cuentas/repositorio, revocación o rotación acreditada, corrección autorizada de referencias actuales y decisión sobre historia compartida.

## 14. Próximos pasos para integrar y preparar un PR

1. Coordinar con el compañero únicamente la compatibilidad de los tres segmentos de directorio con espacios finales, conservando el esquema académico aprobado.
2. Pedir al responsable que verifique y publique el DOCX completo aprobado en ese mismo esquema. No sustituirlo de oficio por una entrega anterior.
3. Tras esos cambios, ejecutar fetch y volver a inspeccionar rutas, formato del DOCX y diferencias de código. Integrar origin/main localmente solo si se cumplen las condiciones del encargo.
4. Verificar el árbol resultante. Si cambia únicamente documentación, conservar la distinción entre pruebas históricas y controles nuevos; si cambia producto/dependencias/configuración, ejecutar las suites pertinentes.
5. Resolver P05 con los responsables y obtener autorización de publicación antes de push o PR. El informe nuevo deberá seleccionarse/revisarse explícitamente si se incorpora a un commit futuro.

No se envían mensajes al equipo ni se modifica su trabajo automáticamente.

## 15. Estado final

- Rama: `fix/wellq-backend-hardening`.
- HEAD: `1684c743574594da417091cf6a266d6f02ac43cf`; consolidación preservada.
- Origin/main tras fetch: `339b8cfc4748ee61f178fa57d46cf6eb29a7f78d`.
- Cero archivos tracked modificados, cero staged y un único archivo nuevo: este informe.
- Main local intacto; sin merge, commit nuevo, push o PR.
- Backend y documentos locales intactos; organización remota preservada en sus objetos/ref descargados.
- Integración detenida por los bloqueos técnicos; publicación bloqueada por P05.

La fase termina con diagnóstico actualizado y sin intervenir en la organización académica del equipo.
