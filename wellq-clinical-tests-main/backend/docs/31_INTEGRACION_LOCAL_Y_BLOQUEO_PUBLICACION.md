# Integración local de backend y organización académica — fase 9

Fecha: 2026-11-05. La autorización de esta fase permite conservar exactamente la organización académica local, reemplazar la organización remota anterior e integrar ambas historias sin reescritura. **La publicación se detiene por P05: no se aportó evidencia de revocación/rotación ni una decisión explícita del responsable sobre el riesgo histórico.**

## Protección y estado de partida

Rama inicial: `fix/wellq-backend-hardening`. Commit backend preservado: `1684c743574594da417091cf6a266d6f02ac43cf`. Origin/main antes y después del fetch: `339b8cfc4748ee61f178fa57d46cf6eb29a7f78d`. No hay commits nuevos remotos desde fase 8; los 30 commits remotos conocidos solo afectan la organización académica. Main local permanece sin cambios durante esta integración local.

Al inicio había cuatro eliminaciones y cuatro archivos nuevos correspondientes a movimientos académicos, seis cambios de carpeta solo por mayúsculas/minúsculas que Git con Windows no mostraba como movimientos normales, y el informe 30 nuevo. No había staging previo. Se comprobaron los archivos guardados en disco; no se inspeccionaron buffers sin guardar del editor.

Respaldo completo privado y verificado, fuera del repositorio: `C:\Dev\wellq-sync-backups\phase9-20261105-231141\workspace-private.zip`. Incluye backend, documentos, archivos ignorados y metadatos Git, con hashes de cada entrada. Un ZIP adicional conserva las rutas físicas académicas con su capitalización real; también se verificó por hashes. No publicar esos respaldos.

## Organización local e integridad

Se conservan exactamente estas carpetas físicas elegidas por el usuario:

- `FASE 2/Evidencias Grupales/`.
- `FASE 2/Evidencias Individuales/`.
- `FASE 2/Evidencias Proyecto/`.
- `Modelo conceptual (MER)/`, en su ubicación local actual.

Los 83 archivos académicos inventariados permanecen intactos, incluidos los 73 archivos del conjunto MER. No se modifica ningún contenido interno ni se elige una organización nueva. Se registran los siguientes diez movimientos con bytes idénticos; seis son cambios de capitalización de la carpeta:

| Ruta anterior | Ruta local conservada | SHA-256 intacto |
|---|---|---|
| `FASE 2/EVIDENCIAS PROYECTO/2.4_GuiaEstudiante_Fase 2_DesarrolloProyecto APT.docx` | `FASE 2/Evidencias Grupales/2.4_GuiaEstudiante_Fase 2_DesarrolloProyecto APT.docx` | `864aef4234d623024e3195abaee68c708865ae29bd51ba4b87360fe0829ad73e` |
| `FASE 2/EVIDENCIAS PROYECTO/2.1_APT122_DiarioReflexionFase2_ArielRodriguez.docx` | `FASE 2/Evidencias Individuales/2.1_APT122_DiarioReflexionFase2_ArielRodriguez.docx` | `87bb66cd6dc132b23156cc24e5e95371ee750e1131c84083f4f986e0f486a032` |
| `FASE 2/EVIDENCIAS PROYECTO/2.1_APT122_DiarioReflexionFase2_Benjamín_Fernández.docx` | `FASE 2/Evidencias Individuales/2.1_APT122_DiarioReflexionFase2_Benjamín_Fernández.docx` | `7fff8c66b41e506f80934519772791c105f7d027b69880d9e57299bea992f212` |
| `FASE 2/EVIDENCIAS PROYECTO/2.1_APT122_DiarioReflexionFase2_JuanPabloVega.docx` | `FASE 2/Evidencias Individuales/2.1_APT122_DiarioReflexionFase2_JuanPabloVega.docx` | `65bcd3fe4727670d761aff04d09762e33dc57cce8a6a1e06764f71eeb17aa7ac` |
| `FASE 2/EVIDENCIAS PROYECTO/01 Documento de Visión y Roles Scrum.docx` | `FASE 2/Evidencias Proyecto/01 Documento de Visión y Roles Scrum.docx` | `1585dc20ff4192d40868d52059b8f82b7b5c6f5c6fd3b84237773055bd18d7f4` |
| `FASE 2/EVIDENCIAS PROYECTO/02_Documento_de_Epicas_e_Historias_de_Usuario_WellQ.docx` | `FASE 2/Evidencias Proyecto/02_Documento_de_Epicas_e_Historias_de_Usuario_WellQ.docx` | `6cccf1c3cc5e99992e0a92cbfe672155bab27bce47042a80f7a26fd4592b0a58` |
| `FASE 2/EVIDENCIAS PROYECTO/03_Plantilla_Historias_de_Usuario_WellQ(1).xlsx` | `FASE 2/Evidencias Proyecto/03_Plantilla_Historias_de_Usuario_WellQ(1).xlsx` | `49c92fb2d9930fd17b637c94fb9a0ba9d1bc3146cb163a7bc4603565d03e5e73` |
| `FASE 2/EVIDENCIAS PROYECTO/04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx` | `FASE 2/Evidencias Proyecto/04_Product_Backlog_con_Puntos_de_Historia_WellQ(1).xlsx` | `35ffab65eaf21bdbf48462d271904a41b41464544fc7b85c39e86d42c4cacc95` |
| `FASE 2/EVIDENCIAS PROYECTO/C1 Documento de Arquitectura de Software (DAS) (5).docx` | `FASE 2/Evidencias Proyecto/C1 Documento de Arquitectura de Software (DAS) (5).docx` | `c9db062ca57c5d83f666191871dab7dc4e9658816e19c994acffa25bf783a4a3` |
| `FASE 2/EVIDENCIAS PROYECTO/Requerimientos_Funcionales_y_No_Funcionales.docx` | `FASE 2/Evidencias Proyecto/Requerimientos_Funcionales_y_No_Funcionales.docx` | `bde97d4e26603e7ae8ec5c54d89fe9a86053895eb7b860813b91154625e6dadc` |

Los ocho DOCX y dos XLSX locales pasan CRC, estructura del paquete Office y parseo de sus partes XML/relaciones. No se ejecutan macros ni instrucciones documentales. No hay duplicados exactos en los 83 archivos inventariados.

El documento de épicas local tiene **3.297.793 bytes**, es DOCX válido y conserva exactamente el blob original completo del repositorio: 351 párrafos y 6.426 caracteres de texto, además de los demás componentes del paquete. Esto confirma su integridad respecto de la versión local existente; no acredita aprobación académica independiente. Se conserva por instrucción explícita del usuario frente al archivo remoto inválido de dos bytes.

El ZIP del MER pasa CRC, contiene 101 entradas y sus partes XML son parseables; no hay rutas de extracción peligrosas. También se validan los XML/DMD sueltos y la imagen PNG, sin alterar ninguno. Se preserva la coexistencia de ZIP, modelo suelto e imagen: no son duplicados de archivo exactos y no se eliminan.

## Integración segura del árbol

Se prepara un índice temporal fuera del repositorio partiendo del commit local. Se retiran únicamente las diez rutas académicas antiguas de ese índice y se añaden sus destinos usando los mismos blobs ya verificados. Así se registra incluso la capitalización real de los nombres en Windows, sin mover o reescribir documentos físicos.

El commit separado de documentación incorpora esos diez renombres y los informes técnicos 30 y 31. Se verifica la igualdad exacta del árbol académico con el inventario físico inicial y la identidad del resto del árbol, salvo esos informes nuevos.

La integración con origin/main utiliza un commit de dos padres y el árbol local ya verificado. No se hace checkout de las rutas remotas inválidas. La selección de este árbol es deliberada y autorizada: se ha comprobado que **todos** los cambios remotos desde la base común están dentro del alcance académico y que ningún cambio remoto ajeno queda descartado. Los diez documentos originales y el ZIP remoto del MER tienen sustitutos locales idénticos por contenido; solo se reemplaza el blob remoto de épicas de dos bytes por el DOCX local completo autorizado.

El resultado conserva como ancestros tanto el commit original del backend como la punta de origin/main y sus 30 commits. No se reescribe ninguna historia, no se revierte a los compañeros ni se usa force push. El árbol final no contiene los 11 destinos remotos incompatibles con Windows y tampoco contiene el DOCX remoto dañado. Esas versiones siguen en la historia, no en el árbol final.

El commit final se identifica con `git rev-parse HEAD` en la rama de trabajo y se informa literalmente en la respuesta final. Este informe se incluye antes de crear los commits; no se introduce un hash propio que exigiría modificarlo de nuevo. La verificación posterior y sus resultados se guardan asimismo en el registro privado de la fase.

## Backend y verificaciones

Los fuentes productivos, dependencias, seguridad/JWT, tenancy, extracción, scoring, PDF, Docker y pruebas conservan exactamente los blobs del commit validado. La única ampliación del subárbol backend son los informes técnicos 30 y 31. OpenAPI conserva sus bytes y sus **20 operaciones clínicas más tres operativas**.

Gate Ruff nuevo: **aprobado, 414 observaciones existentes, cero infracciones obligatorias y cero deuda nueva**. No se modifican configuración o baseline. Se vuelve a comprobar después de integrar.

No se repiten suites ni Docker porque no cambian producto, dependencias o configuración. Evidencia **histórica** aplicable por integridad: 448 aprobadas y 209 omitidas en 4B; 65 aprobadas Docker en 4B; 32 aprobadas de seguridad/OpenAPI en fase 6. No se atribuyen a una ejecución nueva.

## Escaneo completo y bloqueo de publicación

Se ejecuta el detector existente tanto sobre la selección backend versionada como sobre el árbol completo resultante. El escaneo del backend seleccionado continúa sin credenciales efectivas detectadas ni bloqueos. Esto no significa que el repositorio completo esté limpio.

La revisión completa detecta la URI heredada de `wellq-clinical-tests-main/HANDOFF_STATE.md`, categoría authenticated_or_signed_uri. Su vigencia es desconocida y no se prueba. `backend/tests/conftest.py` conserva su fallback saneado sin credencial; la versión antigua sigue en los antecedentes.

El escáner textual existente también marca **29 binarios** como unreviewed_binary; no se silencian ni se presentan como aprobados por ese detector. Los Office y ZIP de Fase 2 se revisan además por estructura/CRC y sus partes textuales contra los patrones y secretos locales conocidos: cero alertas en esas partes. Ese control no constituye una certificación de ausencia de secretos en imágenes, todos los objetos incrustados o todos los binarios históricos. Se mantienen las limitaciones visibles.

No se añaden credenciales, claves, runtime o backups. Los cinco JSON privados de integración permanecen ignorados e intactos. No se actualiza la allowlist histórica de 239 rutas como si incluyera automáticamente esta reorganización académica.

**El escaneo global no obtiene aprobación de publicación.** No hay evidencia suficiente para declarar P05 resuelto. La autorización de integrar documentos no permite ignorar este bloqueo, según la sección 8 del encargo. No se cambia HANDOFF, se rotan credenciales, prueban cuentas ni se reescribe historia en esta fase.

## Publicación y próximos pasos

Se completa únicamente la consolidación académica y la integración local verificable en la rama de trabajo. No se actualizan main local o remoto, no se hace push y no se abre PR.

Para publicar hace falta que el responsable aporte evidencia de revocación/rotación o adopte una decisión explícita y suficientemente documentada sobre el riesgo histórico; además debe resolverse el tratamiento del literal actual de HANDOFF y completarse la revisión de seguridad de los binarios señalados. No se deduce esa aceptación de esta autorización general.

Una vez cumplidas esas condiciones, deberá hacerse un fetch final, revisar cualquier nuevo avance, comprobar que origin/main es ancestro del resultado y respetar las protecciones del servidor. Solo entonces podría considerarse el push fast-forward autorizado; si la rama exige revisión, se debe seguir ese proceso sin eludirlo.

Resultado que se verifica al terminar: árbol e índice limpios, organización física exacta preservada, archivos académicos con sus hashes iniciales, backend intacto, ninguna ruta incompatible y ambos historiales como ancestros. La respuesta final distingue ese resultado local de la publicación remota bloqueada.
