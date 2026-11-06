# Guía del desarrollador: Docker y PDF demostrable

Usar el checkout **C:\Dev\wellq-capstone**, rama `fix/wellq-backend-hardening`. Todo el contenido generado es ficticio y el entorno se restringe a test. No emplear documentos de pacientes, credenciales cloud ni servicios antiguos.

## Generar y ver el reporte

Desde PowerShell/terminal VS Code:

```powershell
Set-Location C:\Dev\wellq-capstone\wellq-clinical-tests-main\backend
powershell -NoProfile -ExecutionPolicy Bypass -File integration/Demo.ps1
```

Un solo comando valida Docker/Compose y el aislamiento, construye desde el código actual de C:\Dev, inicia los servicios propios, espera readiness, prepara identidades ficticias, sube PDFs reales por HTTP, espera workers, confirma/corrige/valida/revisa, consulta JSON, exporta y descarga los PDFs, verifica contenido/privacidad/idempotencia y renderiza todas las páginas.

Resultados locales:

```text
integration/demo-output/
  wellq-reporte-clinico-demo.pdf       # copia del escenario suficiente
  reporte-http.json                   # cuerpo exacto de GET lab-report
  resultados-demo.json                # resultado HTTP, hashes, tamaños y render
  pdf-pages/pagina-01.png ...          # todas las páginas del principal
  suficiente/                        # PDF, entradas, respuestas redactadas, auditoría
  incompleto/                        # variante sin rangos ni puntajes justificables
```

Para abrir únicamente el PDF local con la aplicación de Windows asociada, ejecutar explícitamente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File integration/OpenDemo.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File integration/OpenDemo.ps1 -Scenario incompleto
```

No abre una URL firmada ni transporta tokens. También se pueden abrir los archivos desde el explorador/IDE. [PDF principal (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion), [incompleto (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) y [PNG principal](../integration/demo-output/pdf-pages/).

Una repetición crea tenants/IDs nuevos y mantiene la DB sintética anterior. Sobrescribe las salidas demo de nombres fijos; si se quiere conservar una corrida, copiar su carpeta antes. No ejecuta borrado de volúmenes. El directorio está ignorado por Git y excluido de Docker; no borrar la identidad `.runtime` para “reiniciar” una DB existente, porque contiene sus contraseñas/authority de prueba.

## Requisitos y dependencias

Docker Desktop operativo, contexto Linux y Compose disponibles. Se comprobaron Engine 29.8.2/Desktop 4.94.0/Compose v5.5.1. La imagen usa Python 3.11; el Python host de `.venv\Scripts\python.exe` en la raíz del repositorio se utiliza para tooling y tests aislados (3.12.10 en esta corrida).

El script prepara `integration/.runtime/render-venv` si no existe e instala **pypdfium2==5.14.0 y Pillow==13.0.0**, exclusivamente para convertir PDFs descargados a PNG con PDFium. Puede requerir red para imágenes y wheels. No se cambian requirements del backend ni su venv global. Si no se puede instalar, el script falla en la fase de renderizado; un PDF legible por pypdf no se presenta como visualmente revisado.

`ExecutionPolicy Bypass` aplica solo al proceso invocado; no cambia la política persistente. No necesita alterar ACL del pipe Docker ni ejecutar comandos de limpieza. Si no accede al motor, comprobar Docker/contexto desde la terminal y resolver esa dependencia; no asumir que Docker está detenido ni cambiar permisos automáticamente.

## Servicios y seguridad

Proyecto exclusivo **wellq-int-39706292db88**, red y cuatro volúmenes con ese prefijo. Servicios persistentes de demo: `api-int`, `mongo-int`, `objects-int`, `worker-int` con dos réplicas; preparación `setup-int`/`provision-int` y runner temporal. `clamav-int` existe del trabajo previo pero no se inicia en Demo; scanner principal test explícito. Mongo replica set y autenticación son reales, sin exponer puerto al host.

El guard de PowerShell rechaza recursos antiguos, OneDrive, puertos publicados y montajes fuera de runtime/evidencias/demo-output permitidos. La marca de DB verifica proyecto/run antes de escribir. Provisionamiento sobre una DB propia ya preparada no aplica migración. El endpoint de objetos exige firma incluso en la red interna; las URLs de prueba no se guardan en los logs redactados. La clave privada RS256 se monta únicamente en el runner.

No tocar `wellq-api`, `wellq-mongodb`, volumen `backend_mongodb_data`, carpeta OneDrive ni puertos host 8000/27017. No usar Compose por autodetección desde otra carpeta; los scripts pasan archivo, env-file y proyecto exactos. No ejecutar `down -v` ni limpiezas globales.

## Estado, pruebas y parada

Los scripts previos Inspect/Start/Test/Stop siguen disponibles. Para conservar congelada la evidencia anterior, esta demo permite enviar la configuración resuelta a una salida nueva y usa un script específico de pruebas:

```powershell
# Inspección de servicios propios; el script original también guarda config resuelta.
powershell -NoProfile -ExecutionPolicy Bypass -File integration/Inspect.ps1

# Reconstruye/inicia el proyecto propio y ejecuta la suite Docker.
# Sobrescribe únicamente el XML/runtime de docs/evidencias_demo.
powershell -NoProfile -ExecutionPolicy Bypass -File integration/DemoTests.ps1

# Regresión de aplicación y PDF, con red prohibida por su fixture.
& ..\..\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --junitxml=docs/evidencias_demo/application-regressions.xml

# Parada exclusiva sin borrar volúmenes ni reescribir evidencia de la fase anterior.
powershell -NoProfile -ExecutionPolicy Bypass -File integration/Stop.ps1 -ConfigEvidenceFile integration/demo-output/compose-resolved-redacted.json
```

No ejecutar Demo y DemoTests a la vez: la suite inyecta fallos en su DB propia y arranca/recrea contenedores de ese proyecto. `Demo.ps1` deja los servicios en marcha para desarrollo; al terminar, Stop los detiene conservando todo. `DemoTests` no genera los PDFs de demostración: para ver un nuevo PDF usar Demo.

`DemoProbes.ps1`, con la API propia healthy, permite repetir las seis observaciones de brechas documentales del documento 18. Prepara datos sintéticos independientes y guarda `sondas-brechas-http.json`; su salida significa que la sonda se ejecutó, **no que el requisito esté cumplido**. No modifica el escenario PDF. No ejecutarlo al mismo tiempo que DemoTests.

`Demo.ps1 -SkipBuild` reutiliza la imagen ya construida. Usarlo solo si no cambió código de aplicación/integración; el modo normal reconstruye para evitar probar un backend antiguo. Para regenerar solo PNG de los PDFs existentes:

```powershell
& integration/.runtime/render-venv/Scripts/python.exe -B integration/render_demo.py
```

El renderizador no invoca exportación ni crea un reporte independiente: solo abre el PDF descargado. Una nueva corrida marca la revisión visual como pendiente; revisar cada PNG antes de declararla completa. El script no afirma que sus diagnósticos geométricos sustituyan la inspección humana.

## Diagnóstico por etapa

| Etapa informada | Acción necesaria |
|---|---|
| preconditions | Comprobar motor/contexto y `.runtime/state.json`; no reutilizar DB de otro proyecto ni modificar ACL automáticamente. |
| start isolated services | Revisar únicamente metadatos/logs de servicios con el prefijo propio. No tocar los contenedores antiguos. |
| API readiness | Esperar primary/autenticación/esquema propio y autoridad pública test; health no acredita GCS/IA/scanner. |
| HTTP upload/confirm/validate/report/export/download | Revisar operación y status seguros. Conservar misma clave en replay. Si download_pending persiste, resolver firmante local; no aceptar ready sin enlace válido. |
| local PDF renderer | Comprobar Python host/venv, conexión para wheels y versiones de tooling. No instalar un motor clínico nuevo. |
| render all downloaded PDF pages | Comprobar PDF, SHA y archivo; revisar cada PNG, páginas vacías/cortes/pie y comparación con JSON. |

Cada error devuelve fallo y no declara éxito de etapas posteriores. El script no elimina recursos para recuperarse. El archivo `resultados-demo.json` se genera solo tras completar ambos escenarios HTTP; consultar fecha/hashes para distinguirlo de una corrida anterior cuando una nueva ejecución falla antes de terminar.

## Qué falta para navegador o dispositivo

No hay API publicada a Windows: `api-int` y `objects-int` son DNS de la red Docker. Para React o Flutter fuera de esa red hay que elegir un puerto libre, enlazar deliberadamente la API a **127.0.0.1**, revisar CORS y hacer accesible el flujo de objetos de desarrollo. No basta con abrir el enlace interno del JSON en Chrome. Para un dispositivo físico, definir también la ruta segura hacia el host/emulador; no abrir Mongo ni trasladar claves privadas al cliente.

Los clientes deben consumir los permisos/grants de una autoridad confiable, mantener Idempotency-Key/client_upload_id y tratar nulos y estados pendientes según OpenAPI. No mostrar puntajes al paciente. Flutter debe implementar Drift, copia privada, backoff, scheduler y borrado del path exacto tras autorización. React debe implementar las vistas y sus temas/i18n; esta tarea no escribió esas interfaces.

GCS e IA reales requieren autorización de infraestructura/proveedor y datos de prueba. El segundo escenario de esta demo no convierte la excepción test en una puerta productiva. Catálogo, pesos y rangos se mantienen intactos y sin aprobación clínica. Consultar [matriz](18_CUMPLIMIENTO_CINCO_ARCHIVOS_ORIGINALES.md) y [roadmap](20_ESTADO_REAL_BACKEND_Y_ROADMAP.md) antes de usar datos reales.
