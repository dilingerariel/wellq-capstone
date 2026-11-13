# WellQ — demostración integral del Capstone

Solo datos sintéticos. No es un despliegue sanitario ni una aprobación clínica.
No utilizar el teléfono protegido, sus cuatro operaciones ni sus PDF.
No ejecutar ngrok sin autorización posterior expresa.

## Estado real de esta entrega

- Score v1.1 implementado y probado en memoria. Cobertura ponderada real,
  umbrales sin redondeo, agregado sin redondeo intermedio y exclusión de unidades
  incompatibles. Catálogo parcial: no publicable clínicamente ni siquiera por
  activar un flag aislado. Ejemplo documental: base 78.5, penalización 5,
  lab_index 73.5. Detalles: SCORE_TECHNICAL_VERSION.md.
- API/PDF: verificaciones de ciclo de vida y exportación atómica con Mongo en
  memoria/dobles. No se recalculó ni migró la base histórica.
- React: contratos OpenAPI, TypeScript, build API y pruebas focalizadas de
  sesión/reportes ejecutados. Se conserva el bloqueo de PDF productivo y la
  ocultación de Score no aprobado. No se eludieron esos controles para la demo.
  El artefacto capstone-demo es una compilación explícita de desarrollo, en modo
  API, servida como archivos (sin Vite público). Permite probar la exportación
  existente en el entorno test; no altera el build productivo ni su bloqueo.
- Flutter: endpoint HTTPS restringido a un host de compilación; adaptador
  DemoIdentity separado de LoopbackIdentity. Pases temporales introducidos por
  el usuario, JWT solo en RAM, renovación y logout. Español/inglés.
  Pruebas Dart con dobles y análisis estático ejecutados; no son pruebas TLS
  reales, widgets ni Android. Los dos widgets nuevos están en
  mobile/test/demo_identity_dialog_test.dart y requieren runner Flutter.
- Las diez pruebas de widgets anteriores son antecedentes; no se repitieron.
  El runner Windows sigue bloqueado y no se arrancó otro entorno pesado.
- APK anterior conservado: mobile/build/app/outputs/flutter-apk/app-debug.apk,
  cl.wellq.wellq_mobile, 0.3.0+4, SHA-256
  379090411434682643e8d54b322473397088670b5b21055e947b4a0ee13a56a9.
  Corresponde a 7ad57fc: NO incluye la nueva configuración HTTPS/dialogo.
  No se recompiló ni ejecutó Android/iOS en esta misión.
- Composición nueva generada y validada por Docker Compose. Su arranque fue
  rechazado por el control de recursos (576 MiB libres, mínimo 4096 MiB).
  No se creó ningún contenedor de demostración ni se detuvo el histórico.
- Ngrok continúa desactivado. Falta ejecutar el stack independiente y validar
  TLS/E2E real antes de pedir autorización para una URL pública. No basta con
  aprobar una política estática.

## Modelo de aislamiento

El tenant proviene del JWT. TenantDatabase acota consultas/escrituras y
patient_access contiene relaciones por (client_id, patient_id). Las pruebas
cubren paciente compartido entre clínicas, clínicos autorizados/no relacionados,
lecturas, mutaciones, reportes, Score y emisión de URL privada.

La demostración NO comparte automáticamente datos entre clínicas. La política
definitiva de pertenencia múltiple, vinculación de fichas, creación de cuentas
y compartición requiere decisión del cliente; no se agregaron colecciones para
resolverla artificialmente.

## Arquitectura nueva, sin reutilizar la integración histórica

HTTPS futuro → gateway dedicado → React compilado / FastAPI / objetos privados.
Mongo y objetos no publican puertos. Solo el gateway publica 127.0.0.1:9080.
Cada preparación genera proyecto wellq-int-capstone-..., volúmenes y claves
propios. No monta volúmenes, claves ni datos de wellq-int-39706292db88.

Se reutilizan FastAPI, workers, provisión de índices y adaptadores sintéticos
existentes. El extractor anotado y almacenamiento local son dobles explícitos;
no certifican IA, GCS o IAM. ClamAV nuevo tiene volumen propio y red de salida
exclusiva para actualizar firmas. Ningún dato se elimina automáticamente.

capstone_gateway.py es exclusivamente test: pases aleatorios por participante,
rol y tenant fijados en servidor, duración máxima de dos horas, JWT RS256 de
cinco minutos, límite de intentos, origen exacto, revocación RAM y época de
arranque. Reiniciar el gateway invalida sus tokens anteriores. Las URLs firmadas
se reescriben al mismo origen público y la firma se verifica antes del proxy.

React usa window.wellqIdentity sin otro gestor de sesión. Flutter usa
DemoIdentity únicamente con debug + WELLQ_SYNTHETIC. No es OTP, no hay contraseña
maestra ni registro productivo. Logout Flutter borra inmediatamente su RAM y
solicita revocación sin reintentar; estando offline la revocación remota es
best-effort hasta el vencimiento corto del JWT.

Las claves/pases quedan en .runtime, ignorados por Git y fuera del portal y del
contexto Docker por .dockerignore. No se certificaron ACL de Windows, protección
del host ni seguridad productiva. No publicar esa carpeta ni sus logs.

## Preparar y compilar el portal (comandos ejecutables)

Desde C:\Dev\wellq-capstone, preparar una ejecución NUEVA antes de cada sesión;
las invitaciones vencen. La salida solo contiene rutas/ID, nunca claves o pases.

    $demo = (.venv/Scripts/python.exe -B tools/capstone_demo/manage.py prepare | ConvertFrom-Json)
    $demoRun = $demo.run
    $demoDir = $demo.private_directory

La preparación final es capstone-4fa8c797810b. Ese directorio tiene una
composición aislada y un portal capstone-demo compilado; sus invitaciones pueden expirar.
Los ensayos previos capstone-5bbff16e7882 y capstone-51780ce01238 se conservaron
como preparaciones privadas, sin iniciar sus contenedores.
No editar ownership.json ni compose.json para saltar las comprobaciones.

Compilar para ese directorio (sin Vite público ni adaptador loopback):

    .venv/Scripts/python.exe -B tools/capstone_demo/manage.py build-portal --run $demoRun

Esta operación usa NODE_ENV=development solo en el proceso hijo, modo
capstone-demo y VITE_DATA_MODE=api. No modifica las variables del padre ni el
comando normal de producción. Rechaza sobrescribir un portal previo y genera
.artifact.json con identidad del proyecto y hashes de todos los archivos.
El gateway rechaza artefactos sin esa marca o cuyos hashes no coincidan.

No copiar datos clínicos, claves o .runtime al portal. Para iniciar, con Mongo y
ClamAV oficiales ya disponibles en la caché Docker y suficiente memoria:

    .venv/Scripts/python.exe -B tools/capstone_demo/manage.py check --run $demoRun
    .venv/Scripts/python.exe -B tools/capstone_demo/manage.py start --run $demoRun

start construye la imagen nueva y provisiona solo su base vacía/propia. Si el
proyecto ya existe, exige inspección; no recrea contenedores automáticamente.
Si no hay RAM suficiente, devuelve código 2 sin ejecutar el stack.
Nunca detener el histórico sin permiso para liberar recursos.

Para cerrar exclusivamente la demostración, conservando datos y volúmenes:

    .venv/Scripts/python.exe -B tools/capstone_demo/manage.py stop --run $demoRun

No utiliza down -v, prune, borrados ni el proyecto histórico.
La eliminación futura de volúmenes requiere autorización independiente.

## Activación HTTPS/ngrok posterior (NO ejecutada)

Primero escoger dominio HTTPS y CIDRs IPv4/IPv6 de los participantes.
Preparar una ejecución nueva con el origen exacto; no cambiar el loopback
global ni el puente 8765:

    $demo = (.venv/Scripts/python.exe -B tools/capstone_demo/manage.py prepare --origin https://DOMINIO-AUTORIZADO | ConvertFrom-Json)
    $demoRun = $demo.run
    $demoDir = $demo.private_directory

Compilar e iniciar el nuevo run como arriba y verificar sus servicios. Abrir el
archivo participant-passes.private.json solo en el host para entregar a cada
participante SU pase (patient-a, clinician-a, patient-b, clinician-b); no mostrar
el archivo en pantallas compartidas ni enviar pases a este asistente.

Preparar una política separada de IPs explícitas; no reemplaza la deny-all:

    .venv/Scripts/python.exe -B tools/capstone_demo/manage.py policy --run $demoRun --allow-cidr IP-V4/32 --allow-cidr IP-V6/128

La política se aplica antes de las sesiones de la aplicación. No usa
redirecciones OAuth que una app nativa no pueda completar; ambos clientes
usan pases/JWT dentro del entorno sintético. No es un contrato productivo.

Solo DESPUÉS de validar el entorno y recibir autorización pública:

    ngrok http http://127.0.0.1:9080 --url https://DOMINIO-AUTORIZADO --traffic-policy-file "$demoDir/ngrok-restricted.json"

El authtoken ngrok debe configurarse privadamente; nunca incluirlo en Git,
bundle, comandos compartidos ni capturas. No se instaló ni inició ngrok.
Verificar rechazo de IP no permitida, sesión ausente/expirada, tenant/paciente
ajenos, rol incorrecto, logout, URLs firmadas y ausencia de claves en artefactos.

Documentación oficial contrastada:
- https://ngrok.com/docs/gateway/traffic-policy/getting-started/agent-endpoints
- https://ngrok.com/docs/gateway/traffic-policy/examples/add-authentication
- https://ngrok.com/docs/gateway/traffic-policy/actions/restrict-ips
- https://ngrok.com/docs/gateway/traffic-policy/actions/custom-response

## Flutter hacia ese origen (pendiente de construir/ejecutar)

No hay secretos de compilación. El hostname debe coincidir exactamente con el
origen HTTPS; certificados normales, sin callbacks que ignoren TLS.

    cd wellq-clinical-tests-main/mobile
    C:\Dev\tools\flutter\bin\flutter.bat build apk --debug --dart-define=WELLQ_SYNTHETIC=true --dart-define=WELLQ_DEMO_IDENTITY=true --dart-define=WELLQ_DEMO_ORIGIN=https://DOMINIO-AUTORIZADO --dart-define=WELLQ_DEMO_HOST=DOMINIO-AUTORIZADO

Preservar el APK local anterior antes de esta compilación. Instalar solo en un
emulador/dispositivo limpio expresamente autorizado, identificándolo con -s.
Nunca instalar en el teléfono protegido ni utilizar opciones de borrado.
Sin esos defines se conserva el loopback anterior y LoopbackIdentity.
Release/profile mantienen bloqueada la identidad sintética.
CORS solo protege navegadores; Flutter requiere igualmente JWT y autorización.

Antes de ngrok puede probarse el MISMO stack local desde un dispositivo limpio
con ADB reverse. La única excepción HTTP nueva es el loopback explícito 9080;
no habilita LoopbackIdentity ni hosts remotos sin TLS:

    C:\Dev\tools\flutter\bin\flutter.bat build apk --debug --dart-define=WELLQ_SYNTHETIC=true --dart-define=WELLQ_DEMO_IDENTITY=true --dart-define=WELLQ_DEMO_ORIGIN=http://127.0.0.1:9080 --dart-define=WELLQ_DEMO_HOST=127.0.0.1

En un emulador limpio autorizado (ejemplo, NO usar el teléfono protegido):

    $demoDevice='emulator-5554'
    $adb='C:\Dev\tools\android-sdk\platform-tools\adb.exe'
    & $adb -s $demoDevice install build/app/outputs/flutter-apk/app-debug.apk
    & $adb -s $demoDevice reverse tcp:9080 tcp:9080
    & $adb -s $demoDevice shell am start -n cl.wellq.wellq_mobile/.MainActivity

El portal profesional del mismo stack es http://127.0.0.1:9080/clinical.
Estos comandos Android no se ejecutaron en esta entrega.

## Recorrido para la defensa, una vez validado el stack

Paciente: conectar con SU pase sintético → exámenes → seleccionar PDF sintético
anotado → visualizar → guardar pendiente → autorizar envío → consultar estado →
corregir/confirmar extracción cuando proceda. Guardar/iniciar sesión no envía.

Profesional: iniciar sesión con SU pase → paciente autorizado → mismo
clinical_test_id → revisión/validación → marcadores y reporte → logout.
 El Score no aprobado se mantiene oculto como resultado clínico y la exportación
productiva permanece bloqueada. La exactitud matemática se demuestra con las
pruebas técnicas y el ejemplo documental, no fingiendo aprobación médica.
Cambiar a clínica B debe negar acceso al documento de A.

OTP real, identidad institucional, alta/vinculación de cuentas, validación
médica, catálogo completo aprobado, retención/cifrado productivos y despliegue
sanitario siguen pendientes. El stack nuevo aún requiere prueba real con Mongo,
ClamAV, navegador, Flutter/Android y TLS; no está listo únicamente por autorizar
ngrok. El histórico se conserva en su imagen anterior, sin Score v1.1 desplegado.
Una nueva recuperación bridge-only puede rechazar correctamente ese desfase
de fuente: no eliminar esa protección ni recalcular datos históricos para evitarlo.

## Evidencia y pendientes de validación

- Backend: 277 casos distintos aprobados en ejecuciones focalizadas y
  seguimientos de los cambios (no sumar las repeticiones). La regresión combinada
  inicial aprobó 272; se añadieron los dos pacientes exclusivos, dos tipos de peso
  inválido y la protección productiva. Incluye 23 casos nuevos de Score, 21 de
  dos clínicas y 16 de gateway. Los siete subcasos del guard productivo también
  aprobaron. Pruebas con Mongo en memoria, rutas ASGI reales o dobles explícitos.
- Herramientas: siete unittest de preparación/build/preview aprobados.
- React: 47 casos de sesión/login/reportes; los 31 de reportes se repitieron
  tras cambiar la presentación provisional. TypeScript, ESLint y formato aprobados.
- Dart: 31 comprobaciones debug y 20 con constante productiva, con HTTP doble;
  análisis y formato aprobados. No son pruebas de APK release, widgets ni TLS.
- Ruff de las fuentes nuevas aprobado. No se declara limpio el lint global de
  los servicios heredados: conservan avisos de imports/tipos/deprecaciones previos.
- Cero fallos pendientes en esas verificaciones finales. Pendientes: dos widgets
  nuevos, regresión de widgets recientes no repetida, Android limpio, prueba del
  stack con Mongo/ClamAV reales, navegador visual/responsive de los nuevos textos
  y E2E HTTPS. Ngrok no se activó y su política solo se contrastó estáticamente.
- Preservación: 2.296 archivos históricos con hashes coincidentes, 2.300 archivos
  actuales en el almacén, registros históricos intactos, imagen/env/montajes de API
  conservados. No se intervinieron las operaciones ni PDF del Android.
