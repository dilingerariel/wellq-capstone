# WellQ móvil · fase 1

Aplicación Flutter de paciente, independiente de React. FastAPI y MongoDB son
reales; identidad RS256, almacenamiento firmado, antivirus e IA son de pruebas.
No hay login productivo, scores, portal profesional ni exportación PDF móvil.
Los builds profile/release bloquean el uso y no abren SQLite ni identidad sintética.

## Windows y Android

Flutter está en `C:\Dev\tools\flutter` (3.47.9; Dart 3.13.7). SDK Android y Temurin
17 se instalaron fuera del repositorio en `C:\Dev\tools`; el lanzador lee sus rutas
de `wellq-sdk-setup.json`. No se cambió PATH global ni Developer Mode. En otro PC,
instalar Flutter/Android/JDK y definir `JAVA_HOME`, `ANDROID_HOME`; pasar
`-FlutterSdk` si corresponde. Abrir esta carpeta en VS Code con la extensión Dart/Flutter.

Toolchain instalado: plataformas Android 35/36, build-tools 36.0.0, CMake 3.22.1 y NDK
28.2.13676358. La CLI Android 23 usa nombres de paquetes con `/`; el wrapper
`sdkmanager` heredado no instaló el NDK automáticamente. En instalaciones con esa
CLI se resolvió con `android.exe --sdk=RUTA_SDK sdk install ndk/28.2.13676358`.

Desde esta carpeta, PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Mobile.ps1 Deps
powershell -NoProfile -ExecutionPolicy Bypass -File .\Mobile.ps1 Doctor
powershell -NoProfile -ExecutionPolicy Bypass -File .\Mobile.ps1 Devices
powershell -NoProfile -ExecutionPolicy Bypass -File ..\..\WellQ.ps1 Start
```

No hay emulador/AVD Android ni dispositivo Android conectado en el equipo verificado.
Android Studio, una imagen AVD y su aceleración quedan pendientes; también puede
usarse un teléfono propio con depuración USB autorizada. Después de crear/iniciar
un AVD en Device Manager, comprobar su ID en Devices y ejecutar, sustituyendo el ID:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Mobile.ps1 Run -Device emulator-5554
```

Run exige un dispositivo y configura `adb -s ID reverse tcp:8765 tcp:8765`. No se ha
verificado ese túnel en Android sin un dispositivo. No sustituir por `10.0.2.2`:
el puente rechaza ese Host. Solo debug permite HTTP a `127.0.0.1`; release mantiene
HTTP deshabilitado y no configura firma productiva. Build genera un APK debug ARM64;
Flutter Run construye para la arquitectura del dispositivo elegido.

## Recorrido

1. Conectar paciente sintético. El adaptador debug obtiene el nonce del adaptador
   local existente y pide una sesión de paciente al host; nunca firma ni persiste JWT.
   FastAPI verifica JWT, tenant y permisos; seleccionar un ID no concede acceso.
2. Inicio → Exámenes: lista real con cursor, actualización y detalle autorizado.
   Solo se conservan ID, título, fecha y estado; no notas privadas ni scores.
3. Cargar → Usar PDF sintético incluido. Completar título/fecha y ambos consentimientos.
   También se permite seleccionar una copia idéntica de `assets/synthetic.pdf` desde
   Archivos. Se comprueba tamaño y SHA-256 antes de copiar al directorio privado.
   Otros documentos se rechazan deliberadamente hasta aprobar seguridad clínica local.
4. Guardar en pendientes funciona con una sesión válida aun sin red. No envía nada.
   Pendientes → Enviar inicia `initiate → PUT firmado → complete`. El bearer solo
   va a FastAPI; el almacenamiento recibe únicamente los headers del descriptor.
5. Consultar estados hasta «Documento verificado». `complete` no significa éxito
   durable: se exige el estado y `local_file_can_be_deleted` del servidor. En esta
   fase tampoco se borra la copia, y nunca se toca el original seleccionado.
6. Abrir examen → Consultar propuesta actual → cotejar el original, editar valor/unidad,
   marcar identidad y revisión de todos los campos, revisar el diálogo y confirmar
   o descartar. No se confirma automáticamente. Altas/bajas de marcadores y edición
   de referencias quedan para la próxima fase. Confirmar no es validar clínicamente.
   El PDF original debe consultarse por separado: esta fase no integra un visor PDF.
7. Actualizar listado para observar el estado recibido del servidor.

Los valores del PDF incluido están identificados como sintéticos y se procesan
mediante el extractor de anotaciones existente. No se sustituyen errores por datos demo.

## Offline y privacidad

Drift usa SQLite nativo, esquema 1, SQL parametrizado y separación tenant/paciente.
Guarda operación, fase, timestamp, intentos, versión local, claves inmutables,
cuerpo estable, IDs del servidor y referencia relativa validada al PDF privado.
No guarda tokens, contraseñas ni URLs firmadas. Un lease CAS local evita dos envíos
simultáneos; recuperar un lease al arrancar no reproduce mutaciones.

Para probar offline, mantener la app abierta y detener WellQ con el comando de
abajo. Preparar una carga, intentar consultar/enviar y comprobar que no aparece
éxito. Reiniciar WellQ y pulsar Consultar estados: revalida identidad y consulta el
servidor, sin enviar automáticamente documentos ni confirmaciones. Reintentar es
una acción explícita, con identidad/cuerpo/claves originales. HTTP 409/428 bloquea
la operación; 429 respeta Retry-After. Un PUT ambiguo se reintenta con precondición
de objeto inmutable; solo el hash y escaneo del backend pueden verificarlo.

Una interrupción de red mantiene vista y borradores en RAM. Si vence la sesión o
se revoca acceso, se limpian las vistas y la caché: la operación sintética queda
aislada para una nueva sesión autorizada del mismo propietario. Al reiniciar sin
red no se inventa identidad offline: hay que reconectar antes de abrir datos privados.
Cerrar sesión explícitamente limpia también las operaciones locales tras advertirlo;
las copias y documentos del servidor permanecen. No se promete trabajo en segundo plano.

No usar datos clínicos reales: faltan cifrado/claves del dispositivo, retención,
borrado, backups y políticas de revocación aprobadas. SQLite privado y allowBackup=false
no equivalen a cifrado. Los proveedores SSO, GCS, IA y antivirus productivos siguen pendientes.

## Comprobar y apagar

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Mobile.ps1 Analyze
powershell -NoProfile -ExecutionPolicy Bypass -File .\Mobile.ps1 Test
powershell -NoProfile -ExecutionPolicy Bypass -File .\Mobile.ps1 Live
powershell -NoProfile -ExecutionPolicy Bypass -File .\Mobile.ps1 Build
C:\Dev\wellq-capstone\.venv\Scripts\python.exe .\tool\contracts.py --check
powershell -NoProfile -ExecutionPolicy Bypass -File ..\..\WellQ.ps1 Stop
```

Test usa dobles HTTP explícitos para errores y widgets; omite la prueba real por
defecto. Live usa HTTP desde Dart nativo en Windows, FastAPI/MongoDB reales y el
PDF incluido; no es una ejecución de Android. Las pruebas activan semántica,
comprueban navegación, tamaños móviles/tablet/horizontal, temas y texto al 200 %;
no certifican TalkBack ni accesibilidad en un dispositivo.

Contratos: `contracts.patient.json` se genera del OpenAPI vigente; el checker
rechaza divergencias y exige revisar DTOs antes de regenerar. `lib/domain` contiene
modelos; `data` HTTP/identidad, Drift y carga; `application` estado/cancelación;
`presentation` Material 3 y navegación. Se usa ChangeNotifier del SDK para evitar
dependencias de estado innecesarias y SQL explícito de Drift sin codegen adicional.

Fuentes: [Flutter](https://docs.flutter.dev/install),
[Drift nativo](https://drift.simonbinder.eu/platforms/vm/),
[Android emulador](https://developer.android.com/studio/run/emulator-networking-address).

## Verificación de fase 1

- Flutter analyze sin incidencias y contratos OpenAPI coincidentes.
- 37 pruebas unitarias/widgets aprobadas; una integración se omite por defecto.
- Esa integración se ejecutó aparte y aprobó: HTTP real desde Dart en Windows,
  lectura de paciente, bytes/PUT/worker, estado verificado, confirmación y replay.
- Drift/SQLite probado en memoria y archivo con reinicio; aislamiento, errores,
  leases, offline, idempotencia, logout y respuesta tardía comprobados.
- Navegación real entre widgets en los siete tamaños/orientaciones definidos,
  temas claro/oscuro y texto al 200 %, sin overflow ni taps fallidos. Contraste y
  áreas táctiles automáticos comprobados en casos representativos de ambos temas.
- Android toolchain pasa doctor. No hay dispositivo/AVD; no se ejecutó Android ni
  se validó allí ADB reverse, TalkBack, selector nativo o ciclo de vida del SO.
- APK debug ARM64 compilado: `build/app/outputs/flutter-apk/app-debug.apk`.
  Los previews opcionales de `tool/preview.dart` usan dobles explícitos de widgets,
  no constituyen evidencia de ejecución Android ni de integración HTTP.
- La primera prueba HTTP falló con WellQ apagado y pasó tras Start; el primer
  build APK quedó detenido por NDK ausente antes de compilar la app. Logs y prueba
  de preservación se conservaron en `C:\Dev\wellq-sync-backups\mobile-phase1`.
