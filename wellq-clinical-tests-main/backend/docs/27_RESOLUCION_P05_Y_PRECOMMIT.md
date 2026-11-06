# Resolución documental de P05 y preparación para consolidación Git

Fecha: 2026-11-05. Fase 5, análisis local y preparación. **Diagnóstico terminado; P05 no remediado.** No se verificó la vigencia de ninguna credencial ni se usó para conectar. No se publica ningún valor, fragmento, usuario, host o huella de las credenciales investigadas.

## 1. Estado Git y alcance de esta fase

Repositorio: `C:\Dev\wellq-capstone`. Rama: `fix/wellq-backend-hardening`. HEAD: `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`.

| Medida | Entrada de fase 5 | Cierre con este documento |
|---|---:|---:|
| Archivos tracked | 151 | 151 |
| Tracked modificados | 22 | 22 |
| Archivos nuevos no ignorados | 214 | 215 |
| Candidatos modificados/nuevos | 236 | 237 |
| Archivos staged / eliminados | 0 / 0 | 0 / 0 |

Los 22 modificados y 214 nuevos iniciales pertenecen al trabajo acumulado. Esta fase agrega solamente este documento y actualiza dos registros de preparación ya existentes: `evidencias_publicacion/allowlist.json` y `evidencias_publicacion/secret-scan.json`. La actualización mediante el escáner existente no escribe el índice ni crea un commit. Se conserva la política, baseline y evidencia histórica de Ruff.

Se inventariaron mediante SHA-256 los 365 archivos tracked/untracked no ignorados iniciales en un registro privado fuera del repositorio. Se coteja al cierre que las únicas diferencias sean los dos registros de selección y este documento nuevo. No se cambia HANDOFF_STATE, código, frontend, dependencias, ignores ni capturas anteriores. No se ejecutan fetch, conexiones externas, rotaciones, comandos Docker, staging, commits, push, merge, cambio de rama o reescritura de historia.

## 2. Diagnóstico P05: inventario de rutas

Las rutas siguientes son relativas a la raíz del repositorio. El análisis se limita a los dos hallazgos heredados conocidos; no certifica todos los secretos posibles de toda la historia.

| Ruta | árbol actual | HEAD | Historia local |
|---|---|---|---|
| `wellq-clinical-tests-main/HANDOFF_STATE.md` | Una URI con credencial literal, línea 105; sin modificación local | Una aparición, línea 105 | Presente en dos versiones de commits alcanzables |
| `wellq-clinical-tests-main/backend/tests/conftest.py` | Cero URI con credencial literal; fallback saneado en fase 4A, pendiente de commit | Una aparición, línea 29 | Presente en catorce versiones de commits alcanzables |

En tests permanece la lectura de `WELLQ_TEST_MONGO_URI` y un fallback sin credenciales en un dominio reservado `.invalid`. El guard histórico que omite pruebas permanece intacto. **El saneamiento existe únicamente en el árbol de trabajo:** HEAD y sus antecedentes siguen conteniendo el dato anterior. Corregir el archivo actual y crear un commit posterior tampoco borraría los antecedentes.

Las dos URI completas de HEAD son distintas, según comparación exclusivamente en memoria. Esto no permite concluir que correspondan a dos cuentas distintas o que no compartan contraseña; el responsable debe identificar las identidades y cualquier reutilización por un canal privado. No se supone que ninguna cuenta sea activa, inactiva, productiva o de pruebas.

## 3. Inventario histórico local

Se enumeraron las ocho referencias locales disponibles y los **21 commits alcanzables** desde las referencias a commits. El repositorio no es shallow. Se leyeron en memoria ambas rutas en cada commit, sin ejecutar ese código ni imprimir sus contenidos; las URI se identificaron por el detector existente. Se cotejaron padres para localizar la primera aparición observable en esta historia disponible.

| Ruta abreviada | Primera aparición observable local | Padre inmediato sin esa aparición |
|---|---|---|
| `HANDOFF_STATE.md` | `f3152478396ad4f90e47586103511d0eb03481e7` | `c184019abb6f90ece909455057e5320b86e57f2a` |
| `backend/tests/conftest.py` | `5db2bbd7648d5e8be6b87feccf063e5da035978a` | `5b2c2b9afa9f5e7c7436c6f12d1d7f64be739f8f` |

HANDOFF contiene la aparición en `f3152478396ad4f90e47586103511d0eb03481e7` y en HEAD. Las catorce versiones de tests que la contienen son:

```text
5db2bbd7648d5e8be6b87feccf063e5da035978a
6ab894804a0ee4c199c019d7de7c871520915a58
2d23f442598637926be6118ab93974d5d33530ca
633abc255f66ea7a2e75b8ed8fa5e4c59e96d6f6
fd22c0b42cfac9d1e5bd219d823778cd0cf2c63f
ae01e20feea500cf63e772108a78b6bd3b6fae79
cedda27423e3776584a269849e446e50793fbf9c
16703793df7bfa5b3104d4ce27fe3c6ce410dca6
108efe4457ef83747a1e92f7f3f80bb835dacd9d
5284ceee0b519b39ca0d2e84509478dcf360aad2
b22c8628aa4f1381db8e953d91cf4cb59948e107
c184019abb6f90ece909455057e5320b86e57f2a
f3152478396ad4f90e47586103511d0eb03481e7
fb8746cd42fe107bbda82dd92d3a4d11d545fd3e
```

Son versiones que contienen el literal, no catorce introducciones diferentes ni catorce credenciales distintas. La enumeración no abarca objetos inalcanzables, reflogs, clones ajenos, forks, copias externas o referencias no descargadas.

| Referencia disponible | Punta | HANDOFF en punta | Tests en punta | Historia alcanzable con literal, HANDOFF / tests |
|---|---|---:|---:|---:|
| `refs/heads/fix/wellq-backend-hardening` | `fb8746c` | Sí | Sí | 2 / 14 |
| `refs/heads/main` | `fb8746c` | Sí | Sí | 2 / 14 |
| `refs/heads/feature/juan-frontend` | `fb8746c` | Sí | Sí | 2 / 14 |
| `refs/remotes/origin/main` | `fb8746c` | Sí | Sí | 2 / 14 |
| `refs/remotes/origin/feature/juan-frontend` | `fb8746c` | Sí | Sí | 2 / 14 |
| `refs/remotes/origin/HEAD` | `fb8746c` | Sí | Sí | 2 / 14 |
| `refs/remotes/origin/ariel-componente-f` | `f315247` | Sí | Sí | 1 / 13 |
| Checkpoint local de Codex, objeto tree | `d5486fa` | Sí | No | No aplica: no es un commit |

Referencia exacta del checkpoint: `refs/codex/turn-diffs/checkpoints/cf50cc963c5dfbb3d3897fb857e7ea71/1c514caec127ecbbf5f4597af2faa967/1793924714629/91b67efb-2f16-4d55-b742-38895bf59d65`; objeto `d5486fafcb2ee71efde54802739591b9d84b747f`. Retiene HANDOFF en un snapshot local y requiere considerarse al planificar la retención privada y un eventual saneamiento. No aporta evidencia de publicación remota. No hay tags entre las referencias enumeradas.

## 4. Riesgo y exposición: conocido frente a desconocido

**Conocido:** hay credenciales literales en HEAD, antecedentes locales y puntas de referencias remotas previamente descargadas. Por ello el hallazgo no está limitado a modificaciones locales nuevas. Las referencias `origin/*` constituyen evidencia local de presencia en la historia asociada al remoto conocido; no se actualizaron durante esta fase.

**No verificable con este alcance:** estado actual del servidor remoto, visibilidad pública/privada del repositorio, quién lo descargó, permisos de las cuentas, vigencia o reutilización, accesos realizados, forks, PR, cachés, artefactos y copias ajenas. Una referencia remota local puede estar desactualizada o haber sido alterada localmente; no prueba acceso por terceros ni el estado remoto actual. No se consultaron URLs de remotos ni sistemas externos para resolver estas incógnitas.

El riesgo requiere tratamiento por el propietario aunque el escáner de candidatos apruebe: dicho escáner no recorre HEAD completo ni la historia. Excluir HANDOFF de la allowlist evita incorporarlo como cambio nuevo, pero **todo commit descendiente conserva su contenido heredado y sus antecedentes**. Una publicación de la rama completa seguiría transportando el problema.

## 5. Decisiones y plan de revocación/rotación para el responsable

Las siguientes acciones se proponen; ninguna se ejecutó ni se envió comunicación al equipo.

1. **Asignar responsable del repositorio y del servicio de credenciales.** Abrir un registro privado P05 con rutas y commits, identificar mediante inventarios administrativos autorizados las cuentas, entornos, permisos y posibles reutilizaciones. No copiar secretos en tickets, correos, chats o argumentos de consola.
2. **Aprobar revocación o rotación de cada identidad afectada.** Tratar las credenciales versionadas como comprometidas para decidir su reemplazo; no asumir que borrar Git invalida una contraseña. Si ya fueron revocadas, solicitar al dueño evidencia administrativa de fecha, alcance y ausencia de reutilización; esa evidencia no existe en esta fase.
3. **Preparar una ventana y contingencia.** Identificar consumidores legítimos y responsables, dependencias y variables/gestores de secretos. Si el servicio lo permite, emitir una credencial nueva de mínimo privilegio, distribuirla por el gestor privado, actualizar consumidores autorizados y comprobarlos con la credencial nueva. Si el riesgo exige revocación inmediata, el responsable debe decidir y aceptar su impacto de disponibilidad.
4. **Revocar explícitamente la anterior**, retirar accesos derivados cuando corresponda y revisar registros administrativos/de acceso mediante personal autorizado. No probar la credencial antigua mediante conexiones para acreditar su invalidez. La reversión debe usar otra credencial segura y no reactivar el secreto expuesto.
5. **Registrar el resultado sin valores:** responsable, cuentas identificadas de forma privada, momento, consumidores migrados, confirmación administrativa de revocación y pendientes. Comunicar al equipo el cambio y el canal seguro para resolver fallos. Ningún secreto nuevo debe entrar a Git, capturas o evidencias públicas.

La rotación afecta al servicio externo y requiere aprobación de su responsable y acceso autorizado. Esta fase no tiene evidencia para dar esa acción por realizada.

## 6. Plan de corrección de documentación y ejemplos

Solicitar autorización para reemplazar la línea afectada de HANDOFF por instrucciones que usen variables de entorno o un ejemplo sin autenticación en dominio reservado `.invalid`. Evitar identificar el servidor, usuario o fragmentos del secreto anterior en la explicación del cambio. Conservar en tests el fallback ya saneado y el guard; no habilitar las pruebas históricas contra otro servidor.

Después del cambio autorizado: revisar el diff de forma privada porque la línea eliminada puede contener el valor antiguo; no volcar ese diff en informes. Escanear los archivos nuevos/modificados y la selección exacta, comprobar que no se exportaron secretos en mensajes de commit, tickets o logs. Registrar que la corrección del árbol no borra versiones anteriores. No editar retrospectivamente las evidencias 24–26 para presentar P05 como inexistente.

Esta corrección documental está **propuesta y no aplicada**: HANDOFF queda deliberadamente igual en esta fase de diagnóstico.

## 7. Evaluación del saneamiento de historial compartido

La presencia en `origin/main`, `origin/feature/juan-frontend` y `origin/ariel-componente-f` descargadas justifica evaluar un saneamiento coordinado. La decisión debe tomarla el responsable junto con propietarios de ramas y administradores del alojamiento, después de priorizar la revocación. Reescribir historia no sustituye revocar y no puede garantizar eliminar copias ajenas.

Plan sujeto a autorización expresa:

1. Inventariar de forma autorizada ramas, tags, PR, forks, mirrors, CI, artefactos y clones, sin publicar valores. Congelar temporalmente escrituras y acordar ventana, alcance, responsables y comunicación.
2. Preparar un respaldo privado con acceso restringido y política de retención, y trabajar sobre una copia aislada. Buscar todas las apariciones de los secretos identificados, incluidas otras rutas, antes de fijar las reglas; esta fase no constituye ese escaneo exhaustivo.
3. Revisar y aprobar un procedimiento de sustitución selectiva de las credenciales en las referencias afectadas, sin borrar indiscriminadamente documentos/tests. Verificar en la copia saneada ausencia de esos valores y conservación de producto y evidencias. No se proporciona ni se ejecuta aquí un comando de reescritura.
4. Acordar con el alojamiento tratamiento de referencias/cachés retenidas y protecciones de ramas; cualquier actualización forzada requiere autorización específica. Coordinar al mismo tiempo las ramas afectadas para que una rama antigua no reintroduzca los objetos.
5. Comunicar que cambiarán identificadores de commits y posiblemente firmas, enlaces, PR, bases de ramas y trazabilidad de CI. Guiar a los colaboradores a clonar de nuevo o migrar su trabajo privado siguiendo un procedimiento revisado; no fusionar historias contaminadas de vuelta. Preservar por separado el trabajo acumulado aún sin commit antes de cualquier migración.
6. Revisar los snapshots locales de herramientas, incluido el checkpoint tree identificado, respaldos y retenciones. Cualquier eliminación de referencias o copias requiere autorización y tratamiento específico; no se limpia nada en esta fase.

Puede aceptarse conservar historia después de revocar solo si el propietario documenta expresamente el riesgo residual y la política del repositorio lo permite. Aquí no se presume esa aceptación ni se recomienda publicar mientras se decide.

## 8. Gate Ruff: comprobación nueva

Desde backend se ejecutó el intérprete existente del venv:

```powershell
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m integration.quality_gate
```

Resultado de esta fase: **exit 0, aprobado; 414 observaciones, 0 infracciones obligatorias, 0 deuda nueva, 414 pendientes y 0 resueltas**. Ruff estricto sigue teniendo deuda; no equivale a cero advertencias.

La política coincide con fase 4B: versión de política 1, Ruff 0.17.3 y objetivo Python 3.11. El hash de configuración normalizada registrado y validado por el gate es `64033889ff354db3f63e6e69d24a5fd324caee6c7770b3fbabfd7872d7d251ad`. No se cambia `ruff.toml`, `integration/quality_gate.py`, `checks/test_quality_gate.py` ni `evidencias_ruff/debt-baseline.json`, ni se autoactualizan las 414 observaciones. [Política y evidencia de 4B](26_CALIDAD_RUFF_Y_GATE_CI.md).

## 9. Escáner y allowlist: comprobación nueva

Se ejecutó `python -m integration.scan_publication`: **236 candidatos iniciales, 0 coincidencias de credenciales efectivas y 0 hallazgos bloqueantes, exit 0**. Tras agregar este documento se vuelve a ejecutar el escáner existente con `--write-report` para actualizar solo la propuesta de selección y su reporte; se verifica después sin escritura: **237 candidatos, 0 credenciales efectivas detectadas y 0 bloqueos, exit 0**.

Los ejemplos revisados siguen siendo el JWT/asignación en el aviso público de dependencias y fixtures deliberadamente inventadas en dominio reservado `.invalid`. No se agregan excepciones al detector. El escaneo no certifica la historia ni la totalidad del árbol heredado.

[Allowlist](evidencias_publicacion/allowlist.json): 237 rutas propuestas, existentes, únicas y coincidentes con los candidatos actuales; ninguna staged. [Reporte actualizado](evidencias_publicacion/secret-scan.json). Clasificación automática del selector:

| Categoría | Rutas |
|---|---:|
| Configuración pública | 10 |
| Producción | 27 |
| Pruebas | 11 |
| Documentación y evidencias revisadas | 135 |
| Copias públicas JSON | 8 |
| Scripts e integración | 46 |
| Total | 237 |

Están seleccionados Ruff/configuración, gate, baseline, regresiones del gate, conftest de integración, requirements-dev, escáner, saneador y Common.ps1. HANDOFF_STATE **no está seleccionado**. No hay `.pem`, `.key`, `.env`, PDF, DB, ZIP o logs nuevos seleccionados. El ejemplo `.env.example` se mantiene como configuración revisada sin credenciales efectivas detectadas.

Los cinco originales privados siguientes existen, conservan sus hashes registrados en [validación 4A](evidencias_publicacion/validation.json), siguen efectivamente ignorados y no están en la allowlist:

- `docs/evidencias_integracion/compose-resolved-redacted.json`.
- `docs/evidencias_s01_s02/compose-resolved-redacted.json`.
- `docs/evidencias_s01_s02/compose-at-stop-redacted.json`.
- `docs/evidencias_g03_g06/compose-resolved-redacted.json`.
- `docs/evidencias_g03_g06/compose-at-stop-redacted.json`.

Sus cinco copias `*-public.json` existen y se escanearon nuevamente contra credenciales locales conocidas y patrones: cero hallazgos. Las exclusiones de la allowlist coinciden con los cinco originales. No se modifican los originales, copias, XML privados, runtime, claves o PDF ignorados. No se realiza otra demostración ni control Docker.

## 10. Integridad productiva y evidencia histórica reutilizada

Se cotejaron **40 archivos** de aplicación, scripts, requirements runtime/dev, Dockerfiles/Compose productivos y snapshot OpenAPI con los hashes del respaldo al inicio de 4B: `C:\Dev\wellq-quality-backups\20261105-210314\baseline.json`. Cero diferencias y cero faltantes. El [cierre 4B](evidencias_ruff/preservation.json) ya confirmó su preservación durante esa fase; la comparación actual contra el mismo respaldo mantiene esa continuidad. No se afirma que todo el backend coincida con HEAD: contiene cambios acumulados aún sin commit.

Se releen, sin ejecutar las suites:

| Evidencia de 4B | Resultado histórico conservado |
|---|---|
| [full-final-public.xml](evidencias_ruff/full-final-public.xml) | 657 casos: 448 aprobados, 209 omitidos, 0 fallos/errores |
| [integration-after.xml](evidencias_ruff/integration-after.xml) | 65 aprobados, 0 fallos/errores, HTTP/Mongo Docker aislado |

Los resultados son **históricos de 4B**, no ejecuciones de fase 5. Los 209 omitidos no se cuentan como aprobados. La evidencia Docker mantiene los dobles externos y límites descritos en el documento 26. No se repiten suites, Docker, PDF ni generación de OpenAPI porque no cambiaron fuentes productivos/dependencias ni herramientas de pruebas en esta fase. Los límites de S01, proveedores, identidad y validación clínica del catálogo siguen según cierres previos.

## 11. Condiciones para el commit y recomendación

**Preparación técnica local:** la selección explícita está revisada, pasa el escáner y cuenta con gate aprobado y evidencia histórica coherente. Puede servir para un futuro commit local de consolidación **previa autorización expresa**, revisión final del diff y aceptación explícita de la política de deuda 4B. No se ha realizado staging ni commit; no se debe usar una inclusión recursiva indiscriminada.

**Condiciones pendientes de decisión:** aprobar responsables y alcance de revocación/rotación, corrección de HANDOFF y tratamiento de historia compartida; registrar riesgo residual y restricciones de publicación. Si se incorpora la corrección de HANDOFF al futuro commit, debe autorizarse esa edición, ampliar la selección de forma explícita y repetir su revisión/escaneo. La allowlist actual no la incluye.

**Publicación de rama/repositorio: bloqueada por P05.** Ni un commit local seguro ni un escáner verde eliminan los secretos del árbol heredado o de sus ancestros. Antes de publicar debe existir evidencia de revocación/tratamiento de credenciales, corrección autorizada de la documentación y una decisión documentada sobre saneamiento de historia o aceptación del riesgo residual por el propietario. No se declara el backend autorizado para producción.

Acciones concretas que requieren aprobación posterior: intervención administrativa en credenciales/consumidores; edición de HANDOFF; comunicaciones externas al equipo; eventual reescritura y actualización forzada de referencias compartidas; tratamiento de checkpoints/copias privadas; staging/commit y cualquier publicación. No se ejecuta ninguna de ellas en esta fase.

Se recomienda entregar este plan al responsable, priorizar las credenciales y mantener detenida la publicación. La fase de diagnóstico queda cerrada; **P05 permanece abierto hasta acreditar la remediación y las decisiones del propietario**. No se avanza automáticamente a otra fase.
