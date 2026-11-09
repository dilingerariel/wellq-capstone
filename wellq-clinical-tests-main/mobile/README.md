# WellQ móvil · fase 2.1

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

ADB identifica un teléfono Android físico conectado. El usuario ya comprobó
la fase 2: visor, edición, confirmación y persistencia de una operación pendiente
tras cierre completo sin conexión y posterior reautorización. Eso acredita
persistencia; no permite abrir la cola después de reiniciar sin autenticación.
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
   Caché sintética limitada a ID, título, fecha, tipo y estado de carga/revisión;
   no notas privadas ni scores. El dashboard cuenta solo la vista disponible:
   la lista API no entrega estados de extracción, por lo que no inventa un total
   de propuestas pendientes de confirmación.
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
   o descartar. Paneles, baja confianza, referencias y fechas de muestra/informe
   están disponibles. El diálogo muestra original → revisión; el backend mantiene
   la validación definitiva. No se modifica el catálogo ni se calculan diagnósticos.
   Altas/bajas de marcadores quedan pendientes. Confirmar no es validar clínicamente.
   Una extracción confirmada se muestra en lectura, sin pedir otra confirmación.
7. «Ver documento» aparece solo si hay una operación del propietario asociada al
   examen y una copia local con el hash sintético permitido. El visor carga bytes
   en memoria, ofrece zoom/desplazamiento y libera recursos al salir. No descarga
   documentos ni exporta PDFs. «Ver documento seleccionado» permite cotejar el
   PDF de prueba antes de guardarlo. Un archivo inexistente o alterado se rechaza.
8. Actualizar listado para observar el estado recibido del servidor.

Los valores del PDF incluido están identificados como sintéticos y se procesan
mediante el extractor de anotaciones existente. No se sustituyen errores por datos demo.
Se eligió [pdfrx 2.12](https://pub.dev/packages/pdfrx/versions/2.12.0) por su visor
con carga desde memoria, zoom y desplazamiento. PDFium es nativo; el visor queda
restringido al fixture revisado, no habilita documentos clínicos productivos.

## Offline y privacidad

Drift usa SQLite nativo, esquema 1, SQL parametrizado y separación tenant/paciente.
Guarda operación, fase, timestamp, intentos, versión local, claves inmutables,
cuerpo estable, IDs del servidor y referencia relativa validada al PDF privado.
No guarda tokens, contraseñas ni URLs firmadas. Un lease CAS local evita dos envíos
simultáneos; recuperar un lease al arrancar no reproduce mutaciones.
El esquema sigue siendo 1: los nuevos metadatos opcionales de la caché admiten
registros de fase 1 sin migración destructiva. Cambiar de paciente limpia la vista
y caché anterior, conserva su cola aislada y nunca la envía con otra identidad.

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

En 2.1 las pestañas conservan el formulario en memoria mientras la sesión sea
vigente. Un error de red o 502 no elimina por sí mismo la identidad; «Comprobar
conexión» revalida y consulta, sin enviar. El cierre completo pierde el token en
RAM; la expiración y 401/403 bloquean el acceso. No hay autenticación local segura,
por lo que se mantiene ese bloqueo y no se guarda un JWT para aparentar acceso offline.

La barra usa «Docs.» y «Cola», con nombres completos para accesibilidad. Mide las
etiquetas con el escalado real y mantiene iconos y acciones cuando no caben.
Los títulos largos se limitan en tarjetas y aparecen completos en el detalle.
Las etiquetas de formularios están fuera del borde y pueden ocupar varias líneas.

Las fechas de examen y de muestra son independientes: no se igualan ni se copian
automáticamente. Las fechas sin hora se muestran como DD/MM/AAAA sin desplazarlas.
`confirmation.confirmed_at` se escribe con `datetime.utcnow()` en FastAPI; si no
trae zona se interpreta como UTC, y si trae offset se respeta. Se presenta en hora
local del dispositivo con offset visible, usando sus reglas de zona/DST, sin
modificar el valor del backend.

Para comprobar persistencia, guarda sin conexión y cierra la app **sin pulsar
Cerrar sesión**. Con FastAPI aún apagado, vuelve a abrir: la pantalla exige
reautorización y no debe mostrar información privada de una identidad recordada.
Arranca WellQ, restablece `Mobile.ps1 Reverse -Device ID`, conecta el mismo perfil
y comprueba los pendientes antes de pulsar Enviar. No confundas un examen leído
desde FastAPI con una operación restaurada desde Drift. La prueba automatizada
reabre el archivo SQLite y compara intención, bytes y claves; el cierre completo
y reapertura offline se verificaron también en el teléfono con el APK 2.1.

En una propuesta, un 409 recupera el estado actual para informar, bloquea nuevos
envíos y exige consultar/revisar explícitamente antes de editar otra vez. Un 422
permite corregir el borrador y volver a previsualizar. Si la respuesta fue incierta,
el reintento conserva exactamente cuerpo y clave. No se reenvía al reconectar.

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

Test usa dobles HTTP explícitos para errores y widgets; omite las dos pruebas reales por
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

## Verificación

- Flutter analyze sin incidencias y contratos OpenAPI coincidentes.
- Fase 2.1: 75 pruebas aprobadas, incluidas las 55 anteriores; las dos integraciones
  HTTP se omiten por defecto y no se contabilizan como aprobadas en esa suite.
- En la fase 2 se ejecutaron aparte dos integraciones HTTP: lectura, PUT/worker, edición
  autorizada, confirmación y replay; además corte HTTP simulado en el cliente, reapertura SQLite,
  pérdida de respuesta tras PUT y recuperación real sin confirmar clínicamente.
- Drift/SQLite probado en memoria y archivo con reinicio; aislamiento, errores,
  leases, offline, idempotencia, logout y respuesta tardía comprobados.
- Navegación real entre widgets en los siete tamaños/orientaciones definidos,
  temas claro/oscuro y texto al 200 %, sin overflow ni taps fallidos. Contraste y
  áreas táctiles automáticos comprobados en casos representativos de ambos temas.
- PDFium abrió/renderizó la página completa y el widget real pasó zoom, errores
  de integridad y regreso sin perder el formulario. Se valida el PDF sintético.
- Las comprobaciones físicas del APK 2.1 se registran por separado: no confundir
  los widgets/HTTP en Windows con ejecución Android ni certificar TalkBack.
- Android 16 físico, texto del sistema al 145 %: actualización con `install -r`
  y SQLite/WAL/SHM idénticos antes del primer arranque; navegación sin etiquetas
  partidas, borrador conservado entre pestañas y durante un corte del túnel USB.
  El nuevo PDF sintético quedó en Drift con cero intentos, sobrevivió al cierre
  completo y se recuperó tras reautorizar. El arranque sin conexión mantuvo el
  bloqueo y reconectar no envió nada automáticamente. El pendiente anterior del
  usuario permaneció con cero intentos; solo se envió la operación de esta prueba.
- En ese Android se verificaron PDFium, zoom, vuelta al formulario, etiquetas de
  referencia/fechas completas y confirmación explícita del nuevo PDF sintético.
  La confirmación se mostró con fecha/hora local y `UTC-03:00`; muestra y examen
  conservaron sus fechas independientes. Quedan pendientes TalkBack, teclado
  externo, otros dispositivos y cortes prolongados hasta expiración en Android;
  los controles de expiración/aislamiento se cubren con pruebas automatizadas.
- APK debug ARM64 compilado: `build/app/outputs/flutter-apk/app-debug.apk`.
  Los previews opcionales de `tool/preview.dart` usan dobles explícitos de widgets,
  no constituyen evidencia de ejecución Android ni de integración HTTP.
- Logs y comprobaciones del cierre: `C:\Dev\wellq-sync-backups\mobile-phase2-polish`.
  La primera prueba HTTP encontró el estado transitorio `EXTRACTION_NOT_READY`;
  ahora espera esa respuesta concreta mediante lecturas, sin repetir mutaciones.
- El puente persistente respondió 200 en ocho lecturas consecutivas de `/ready`.
  No se reprodujo `LOCAL_TRANSPORT_ERROR` ni se acreditó su causa raíz. No se
  modificó el puente ni se detuvieron servicios de integración o tareas concurrentes.

Actualizar el APK 0.1.1 (build 2) con `adb install --no-streaming -r` y el mismo
paquete/firma. No desinstalar, no usar `pm clear` y no borrar datos: Drift debe
conservarse. Si Android pide confirmar la instalación, aceptarla en el teléfono;
no desactivar protecciones generales. Conservar el respaldo privado de la entrega.
