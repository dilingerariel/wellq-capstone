# Cierre de seguridad: asociaciones y archivos (S01–S02)

Fecha: 2026-11-05. Alcance exclusivo de la fase 1. Rama `fix/wellq-backend-hardening`, HEAD `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`, con trabajo previo y actual sin commit.

## Dictamen

**S01: corrección defensiva implementada y verificada; integración funcional con la plataforma bloqueada.** Ninguna asociación suministrada se acepta sin una decisión autorizada. No se encontró un modelo, colección operativa ni servicio de citas/casos en este repositorio; el MER conceptual no constituye una fuente de verdad. El backend productivo deja `association_verifier=None` y responde 503 cuando se suministra una asociación. Sin asociaciones, la carga sigue disponible. Las aceptaciones de asociaciones demostradas aquí usan un verificador sintético explícito y no acreditan pertenencia en una plataforma real.

**S02: corregido y verificado.** Nombre, extensión y MIME se validan antes de firmar o persistir la sesión. Se conservan tamaño, SHA-256 y validación posterior del contenido real. No se modificaron frontend, scoring, fórmulas, pesos, catálogo ni reportería.

## Requisitos y diagnóstico

Se revisaron los documentos 15 y 17–21 y las fuentes originales disponibles, cuyos nombres, versiones y SHA-256 están registrados en [documento 18](18_CUMPLIMIENTO_CINCO_ARCHIVOS_ORIGINALES.md). Las referencias P son párrafos XML de esas fuentes, no páginas Word:

- Especificación española de endpoints v1.0: P0251–0258 exige pertenencia al paciente y 403; P0291 prohíbe aceptar asociaciones a ciegas. P0057 y P0290 exigen formatos permitidos y coherencia antes de emitir URL.
- Especificaciones inglesas (4)/(5), archivos idénticos: P0038 y P0173 exigen asociación y autorización; P0067/P0172 exigen extensión, MIME, firma real, tamaño y checksum.
- Estándares transversales Alloxentric P0009: partición por `client_id`; P0013–0015: identidad y permisos. El Documento Maestro v1.0 mantiene el alcance clínico existente; no se cambiaron sus cálculos.

Antes de corregir se reprodujeron ambos fallos con TestClient y después con HTTP/Mongo reales aislados. S01 aceptaba un `case_id` sin verificador; S02 aceptaba `synthetic.exe` declarado `application/pdf`. Ambos devolvían **201 y un registro persistido**. Las dos pruebas de rechazo fallaron intencionalmente en [before.xml](evidencias_s01_s02/before.xml); las respuestas HTTP redactadas están en [http-before.json](evidencias_s01_s02/http-before.json).

Causas: `uploads.initiate` copiaba identificadores opcionales sin consultar una autoridad y solo comprobaba la lista de MIME; no cotejaba la extensión. PATCH permitía introducir asociaciones por otra vía y refresh podía volver a firmarlas.

## Corrección S01

`app/services/associations.py` define `AssociationVerifier.verify(kind, resource_id, scope)` y decisiones inmutables. El scope se obtiene de la identidad JWT ya verificada y del tenant de la fachada de base de datos; no se recibe del cuerpo del cliente. La decisión debe coincidir exactamente en tipo de recurso, ID, tenant y paciente, y declarar explícitamente `True` para existencia, autorización, estado activo y relación asistencial válida. Si esta última no aplica al recurso, el adaptador autorizado debe resolverlo según la política real y emitir una decisión explícita.

- Decisión negativa o pertenencia incompatible: 403 genérico, sin revelar si el recurso existe.
- Verificador ausente, excepción o respuesta malformada: 503, sin detalles internos.
- IDs no nulos vacíos o mayores de 200 caracteres: 422 cuando la verificación está disponible.
- Asociaciones omitidas/nulas: no requieren inventar una aprobación.

Se verifica antes de firmar/insertar en initiate, también al reproducir una sesión existente. Un replay con autorización revocada devuelve 403; una caída del verificador devuelve 503, sin otra firma ni registro. Los conflictos de cuerpo conservan 409. PATCH valida las asociaciones efectivas antes de escribir; `null` explícito permite desvincular. Refresh revalida las asociaciones persistidas antes de devolver o crear una autorización. Los permisos y la pertenencia del examen siguen siendo los existentes.

Para habilitar asociaciones reales la plataforma debe aportar fuente de verdad, semántica de caso/cita y estados, reglas de relación asistencial y autorización, identidad de servicio, errores y tiempos máximos de consulta. Debe implementar e inyectar el adaptador en el arranque y verificarlo contra ese servicio. No se creó una colección clínica paralela, un modelo ficticio ni un flag que autorice asociaciones productivas.

## Corrección S02

`upload_metadata.py` normaliza nombres a NFC y coteja extensión/MIME. El DTO normaliza MIME a minúsculas, sin cambiar campos públicos. Se admiten `.pdf`, `.jpg`, `.jpeg`, `.png`, `.heic`, incluidas extensiones mayúsculas y nombres Unicode legítimos. Se permiten puntos internos legítimos. Se rechazan rutas, separadores, ADS con dos puntos, caracteres de control, controles bidi, nombres sin base/extensión válida, punto/espacio final y extensiones ejecutables intermedias como `.exe.pdf`.

El límite configurable de tamaño y el SHA-256 hexadecimal permanecen exigidos. El nombre nunca determina la ruta del objeto. La comprobación posterior de bytes, hash, tamaño, parser y scanner permanece intacta en `file_validation.py` y el worker: metadatos aceptados no significan contenido aprobado.

## Resultados y evidencias

| Ejecución | Total | Aprobadas | Fallidas | Omitidas | Evidencia |
|---|---:|---:|---:|---:|---|
| Reproducciones unitarias previas, fallos esperados | 2 | 0 | 2 | 0 | [before.xml](evidencias_s01_s02/before.xml) |
| Primera comprobación focalizada posterior | 69 | 69 | 0 | 0 | [focused-after.xml](evidencias_s01_s02/focused-after.xml) |
| Nuevas y existentes relacionadas, incluida refresh | 137 | 137 | 0 | 0 | [related-after.xml](evidencias_s01_s02/related-after.xml) |
| Suite aislada completa final | 565 | **356** | **0** | **209** | [full-after.xml](evidencias_s01_s02/full-after.xml) |
| Primer intento HTTP/Mongo posterior | 29 | 25 | 4 | 0 | [integration-attempt1.xml](evidencias_s01_s02/integration-attempt1.xml) |
| HTTP/Mongo final focalizado | 30 | **30** | **0** | **0** | [integration-after.xml](evidencias_s01_s02/integration-after.xml) |

Los conjuntos se solapan: no sumar ejecuciones como cobertura distinta. La suite completa contiene las 286 pruebas anteriores y **70 nuevas**, sin regresiones. Las 209 omisiones históricas conservan su guard; no se habilitaron servicios antiguos para ejecutarlas. Hay advertencias de deprecación existentes (datetime, Pydantic, cliente de pruebas); no se ocultaron fallas. No se repitió la generación/revisión visual PDF ni la suite antivirus real previa.

Las cuatro fallas del primer intento Docker fueron expectativas del arnés: al cambiar JPEG/PNG/HEIC a `different.pdf` manteniendo MIME de imagen, el backend devolvía correctamente 422; la prueba esperaba 409. Se conservó el intento y se corrigió el reintento para mantener extensión compatible, comprobando entonces el conflicto de cuerpo. No requirió cambiar código productivo.

[HTTP final redactado](evidencias_s01_s02/http-after.json) registra:

| Caso | Antes | Después |
|---|---|---|
| Referencia sin verificación | 201, persistida | 503 sin adaptador productivo (unitaria); 403 para recurso inexistente con verificador test (HTTP real) |
| Caso/cita del paciente/tenant con decisión válida | Sin garantía de pertenencia | 201; replay idéntico y un registro, con doble explícito |
| Otro paciente/tenant, inexistente, no autorizado, inactivo o sin relación | Podía aceptarse | 403, cero sesiones nuevas y sin URL |
| Verificador caído | No se consultaba | 503 sin autorización nueva |
| `.exe` declarado PDF / extensión-MIME incompatible | 201, persistida | 422, cero sesiones y sin URL |
| PDF, JPEG/JPG, PNG, HEIC; mayúsculas y Unicode seguros | Sin cotejo completo | 201 para metadatos válidos |
| Bytes sintéticos inválidos declarados PDF | Verificación posterior existente | Iniciar 201, complete 200, worker rechaza; continúa en cuarentena y no habilita borrado local |
| PATCH con asociación verificada / refresh durante caída | Sin comprobación | PATCH 200; refresh 503 sin URL; desvinculación explícita 200 |

La ausencia de llamadas al firmante y de registros en rechazos se comprueba con espía en las 70 pruebas nuevas; HTTP real confirma respuestas sin URL y conteos Mongo. Las pruebas existentes comprueban contenido válido real de PDF, JPEG, PNG y HEIC y rechazos por bytes/MIME/hash/tamaño. Los tests también cubren claves/cuerpos modificados, replay revocado, respuesta de verificador malformada y nombres NFC/NFD equivalentes.

Mongo 7.0.43, API y dos workers fueron reales, con replica set autenticado y transacciones. Objetos/firma, IA, scanner y verificador de asociaciones son **dobles de integración explícitos**; no certifican GCS/IAM, un emisor productivo, malware real ni un servicio de citas/casos. Datos exclusivamente sintéticos. [Versiones locales](evidencias_s01_s02/runtime-local.json) y [Docker](evidencias_s01_s02/runtime-docker.json).

## Contrato público

[Verificación de preservación](evidencias_s01_s02/preservation.json): OpenAPI idéntico a `docs/openapi.json`; **20 operaciones clínicas** y tres operacionales. No se cambiaron DTO públicos, rutas ni respuestas exitosas. Se endurece la aceptación de entradas y se mantiene el envelope `{"detail":{"code":"...","message":"..."}}`:

- 422 `INVALID_INPUT`: validación del nombre, checksum, tamaño no positivo; `INVALID_METADATA`: MIME no soportado/incompatible; `INVALID_ASSOCIATION`: ID inválido.
- 403 `ASSOCIATION_NOT_OWNED`: asociación rechazada por la autoridad o binding incompatible.
- 503 `ASSOCIATION_VERIFIER_UNAVAILABLE`, con `Retry-After: 2`: ausente, indisponible o malformada.
- 413 `FILE_TOO_LARGE` y 409 de idempotencia conservados.

Los errores de negocio continúan con el esquema de error abierto existente; OpenAPI no enumera cada código de negocio. Los clientes deben mostrar indisponibilidad y reintentar acotadamente la misma intención; nunca quitar una asociación automáticamente para eludir 403/503. Las sesiones previas con asociaciones sin validar pueden quedar bloqueadas en refresh/PATCH hasta verificarlas o desvincularlas. Nombres previos no canónicos pueden entrar en conflicto al reintentar con el cuerpo ahora normalizado; no se migraron sesiones antiguas.

## Archivos modificados en esta fase

Existentes: `app/models/schemas.py`, `app/services/uploads.py`, exclusivamente `edit_clinical_test` en `app/routes/clinical_tests.py`, `integration/adapters.py`, `integration/bootstrap.py`, `integration/compose.yaml`.

Nuevos: `app/services/associations.py`, `app/services/upload_metadata.py`, `checks/test_security_s01_s02.py`, `integration/security_s01_s02.py`, `integration/Security.ps1`, este documento y `docs/evidencias_s01_s02/`. Los dobles solo se instalan desde el bootstrap de integración protegido por `ENVIRONMENT=test`, identidad de proyecto/DB y ownership. No existe activación equivalente en `app.main` productivo.

## Preservación, incidencias y límites

Respaldo previo verificable: `C:\Dev\wellq-security-backups\20261105-190501\`, con `baseline.json`, `baseline.diff`, `backend-before.zip` y `synthetic-demo-output.zip`. Se conservaron los 270 archivos inventariados: ninguno desapareció; solo seis existentes cambiaron en esta fase. Los 71 artefactos de demo respaldados conservan sus bytes. En rutas, la comparación AST detecta únicamente `edit_clinical_test` modificado; el generador PDF no cambió. Los documentos 01–21 y evidencias anteriores permanecen intactos.

No hubo reset, clean, stash, cambio de rama, commit, push ni merge. `git diff --check` pasó. El estado Git sigue incluyendo cambios previos sin seguimiento y modificaciones previas; no se atribuyen todos a esta fase.

Docker utilizó únicamente `wellq-int-39706292db88`, DB sintética `wellq_integration_39706292db88`, sin puertos publicados. No se consultaron datos/logs ni se reiniciaron los contenedores antiguos `wellq-api`/`wellq-mongodb`, ni se reutilizó `backend_mongodb_data` o OneDrive. No hubo purga ni limpieza global, ni eliminación de volúmenes/redes/datos.

Incidencia de ejecución: dos arranques propios coincidieron al principio y produjeron dos auxiliares en estado created con nombres conflictivos. Se serializó el arranque con mutex, se verificaron labels y se conservaron los dos intentos detenidos con nombres `*-attempt-*`. Compose recreó únicamente servicios propios API/objetos/workers para cargar código. La reproducción previa heredó `run --rm` del arnés y eliminó su runner efímero al terminar; los dos runners posteriores se conservaron y el script focalizado ya no usa autoeliminación. Estas acciones no tocaron los recursos antiguos. El inventario final registra estado y labels, sin secretos.

Se detuvieron al cierre solamente API, workers, objetos, Mongo y ClamAV del proyecto aislado; se conservaron volúmenes, red, imágenes, auxiliares y runners. [Inventario final](evidencias_s01_s02/docker-final.json).

No se declara listo para producción ni cerrado el servicio real de asociaciones. Las brechas de revisión clínica, cambio de revisor, notas y auditoría completa continúan pendientes. Próxima fase recomendada: resolverlas por alcance separado y obtener el contrato del verificador de plataforma. No se implementaron en esta intervención.

## Reproducción de pruebas

Desde backend, con el entorno Python ya preparado:

```powershell
C:\Dev\wellq-capstone\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --tb=short
powershell -NoProfile -ExecutionPolicy Bypass -File integration\Security.ps1 -Mode Test
```

El bypass es del proceso, sin cambio persistente de políticas. `Before` es solo una sonda para la versión vulnerable y ahora debe fallar al no reproducirse el defecto; no ejecutarla para sobrescribir la evidencia previa. Antes de repetir pruebas, usar un directorio de evidencia nuevo para conservar esta entrega. Los tests propios crean únicamente datos sintéticos en la DB aislada y no ejecutan migraciones de plataforma.
