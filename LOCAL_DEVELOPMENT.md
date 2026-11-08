# WellQ local en Windows

Este lanzador usa el checkout `C:\Dev\wellq-capstone`, el FastAPI real y el MongoDB
replica set sintético existente. No utiliza `wellq-api` histórico ni publica
puertos de Docker. No ejecutar `Prepare.ps1` sobre esta instalación ya preparada:
se reutilizan su estado, claves RSA y credenciales privadas.

## Encender y abrir

Desde la raíz, en la terminal PowerShell de VS Code:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WellQ.ps1 Start
```

Inicia Docker Desktop si hace falta, verifica propiedad/aislamiento y arranca
**solo** `mongo-int`, `objects-int`, `api-int` y las dos réplicas `worker-int`.
No ejecuta setup/provision, migra datos ni reconstruye contenedores históricos.
Si la imagen contiene código backend diferente al checkout, se niega a arrancar;
no sustituye silenciosamente el backend. Requiere `.venv`, Node/npm, dependencias
frontend instaladas y el `integration/.runtime` privado ya preparado.

Abrir **http://127.0.0.1:5178**. El puente separado escucha exclusivamente en
`127.0.0.1:8765`. Vite redirige `/api`, `/health` y `/ready` al puente, que transmite
HTTP al API de integración sin publicar puertos ni cambiar las comprobaciones de
`Common.ps1`. El puente acepta una lista explícita de orígenes locales; no hay CORS
comodín. MongoDB nunca queda accesible desde Windows ni desde la red local.

La barra amarilla identifica las pruebas y ofrece **Paciente sintético**,
**Profesional sintético** y **Cerrar sesión**. Muestra el ID del paciente autorizado
para introducirlo en el portal profesional. El perfil inicial y el perfil después
de recargar son paciente. Cambiar de perfil limpia el contexto privado de React.
No hay login productivo ni firma JWT en el navegador: Python firma RS256 con la
clave de pruebas existente; FastAPI verifica firma, issuer, audience, tenant,
roles y permisos. Tokens de diez minutos permanecen en RAM, sin imprimirlos.

Las dos muestras iniciales se crean una sola vez mediante el flujo real de carga,
workers y confirmación. Los IDs y datos sintéticos se conservan al detener/reabrir;
no se recrea la autoridad ni se cambia ninguna contraseña. El archivo para nuevas
cargas está en `wellq-clinical-tests-main/backend/integration/.runtime/local-web/synthetic-example.pdf`.

## Qué comprobar en el navegador

- Paciente: dashboard, `/exams`, detalle, `/upload`, estado y revisión de extracción.
  Cargar el PDF sintético, aceptar consentimiento, esperar procesamiento, comprobar
  identidad del documento, revisar cambios y confirmar. El PUT firmado no envía
  bearer al almacenamiento. No usar archivos de pacientes reales.
- Profesional: seleccionar el perfil, escribir el ID mostrado y consultar sus
  exámenes. Abrir revisión clínica, revisar/validar o rechazar según el estado actual.
  Una operación terminal no permite sobrescribir la historia; para repetir un flujo,
  cargar otro documento sintético. Las notas privadas no aparecen al paciente.
- `/history` y `/reports`: mediciones y reportes recibidos de FastAPI, sin fallback
  demo ante errores. Los scores numéricos no aprobados se ocultan. PDF está permitido
  exclusivamente para pruebas en Vite DEV, con versión, CAS, hash e idempotencia.
  **El build productivo continúa bloqueando la exportación PDF.**

IA por PDF anotado, antivirus y almacenamiento firmado de filesystem son **dobles
explícitos**. FastAPI, autorización y MongoDB/transacciones son reales. Esto no
certifica SSO, GCS, antivirus ni interpretación clínica productivos.

## Estado, errores y apagar

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WellQ.ps1 Status
powershell -NoProfile -ExecutionPolicy Bypass -File .\WellQ.ps1 Logs
powershell -NoProfile -ExecutionPolicy Bypass -File .\WellQ.ps1 Stop
```

Status muestra salud y memoria de los cinco servicios, no secretos. Logs indica
las rutas privadas de diagnóstico; no compartir logs sin revisarlos. Stop apaga
Vite, el puente y únicamente esos cinco servicios, conservando bases y archivos.
Rechaza Stop/Start si detecta otro runner del mismo proyecto activo: terminar su
tarea primero. Guardar o terminar los borradores en RAM antes de apagar.

Si 5178/8765 están ocupados, no mata procesos ajenos: resolver el conflicto.
El puerto 8000 del contenedor histórico no se utiliza. Ejecutar uvicorn directamente
sin autoridad confiable seguirá fallando correctamente; no retirar `validate_identity()`.
El bypass de ejecución del comando afecta solo a ese proceso, no a la política global.

## Pruebas reproducibles

Cerrar la sesión manual antes de la suite Docker, para no mezclar sus fallos
controlados con trabajo en el navegador:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WellQ.ps1 Stop
powershell -NoProfile -ExecutionPolicy Bypass -File .\WellQ.ps1 Test
```

Test comprueba propiedad, arranca los cinco servicios necesarios, construye la
imagen de tests con caché y ejecuta la suite vigente. No recrea el API ni las claves.
Conserva el runner y JUnit en `backend/integration/.runtime/test-*/`, sin sobrescribir
evidencias versionadas anteriores. Para apagar sus servicios, usar Stop.

Pruebas del acceso **manual** (sin interceptar respuestas ni inyectar sesiones):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WellQ.ps1 Start
Set-Location .\wellq-clinical-tests-main\frontend
npx.cmd playwright test --config playwright.local.config.ts
```

La suite automatizada `npm.cmd run test:live` requiere primero Stop y todos sus
servicios aislados detenidos; conserva sus propias comprobaciones y no sustituye
el acceso manual. Vitest, Playwright general y `test:release` siguen disponibles.
Si Docker ya no conserva el SHA de la imagen antigua tras reconstruir, el runner
solo admite la imagen disponible del mismo proyecto: verifica etiquetas, usuario,
entrypoint, dependencias y código de integración, y fija su SHA antes de arrancar
la API temporal. No descarga imágenes ni reemplaza el API original.

## Contenedores que no deben encenderse para visualizar WellQ

`wellq-api` y `wellq-mongodb` son históricos (puertos 8000/27017); no los utiliza el
lanzador. `wellq-p05-recovery-193855` es recuperación administrativa sin auth,
aislada con `network=none`: **no arrancarla**. Tampoco se necesitan los contenedores
P05 rotados, antiguos `clinical-api-*`, quality/review/security, setup/provision o
ClamAV. Se conservaron todos; ClamAV tiene un límite de 1800 MiB y no forma parte
del modo visual. Los límites del stack visual suman 1408 MiB; Status informa el uso
real, que debe distinguirse de ese límite y de la memoria global de Docker Desktop.

Base móvil: [FLUTTER_READINESS.md](wellq-clinical-tests-main/frontend/FLUTTER_READINESS.md).

## Verificación de esta entrega (2026-11-08)

- Backend: 430 pruebas; integración Docker: 60, conservando 409/428.
- Frontend: 130 Vitest, 82 Playwright generales, 5 con HTTP/MongoDB reales y
  3 del acceso manual; prueba adicional del bloqueo PDF productivo aprobada.
- 21 comprobaciones de PDF atómico con MongoDB real; snapshots preservados.
- Typecheck, OpenAPI, ESLint, formato y build aprobados. Gate Ruff: cero deuda
  nueva, 408 observaciones históricas revisadas; no equivale a Ruff global limpio.
- Diez anchos, accesibilidad automatizada, temas/idiomas, teclado/táctil, reflow
  equivalente al 200 % y continuidad offline comprobados; no certificación WCAG.
- npm y pip-audit: cero vulnerabilidades conocidas; selección de cambios sin
  secretos detectados. No es una validación de todo el historial Git.
- 101 archivos académicos y todo `backend/app` idénticos por SHA-256. `main`
  intacto; cinco evidencias previas del usuario conservadas fuera del commit.
- Arranque repetido y parada/reinicio comprobados; claves/configuración e IDs
  sintéticos preservados. Cinco servicios, sin puertos Docker publicados: muestra
  aproximada de 470 MiB frente a 1408 MiB de límite. La muestra de procesos Windows
  se conserva privada; `vmmemWSL` no permite atribuir toda su memoria a WellQ.

JUnit y evidencia privada de esta intervención permanecen fuera de la selección
Git, bajo `.runtime/test-*` y `C:\Dev\wellq-sync-backups\local-readiness-20261108-174906`.
SSO, GCS, antivirus e IA productivos siguen pendientes; exportación PDF productiva
bloqueada. La preparación Flutter es documental, no una aplicación móvil validada.
