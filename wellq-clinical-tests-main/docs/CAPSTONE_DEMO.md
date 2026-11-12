# Demostración Capstone: aislamiento, Android y acceso remoto

Solo datos sintéticos. No es una autorización de uso clínico ni de publicación
en Internet. No utilizar el teléfono protegido, sus cuatro operaciones ni sus PDF.

## Modelo y decisiones pendientes

`app/tenancy.py` aplica `client_id` en lecturas y escrituras; `app/database.py`
lo toma de la identidad JWT. Las relaciones de `patient_access` también quedan
acotadas al tenant y su índice es único por `(client_id, patient_id)`.
`require_clinician_access()` exige una relación dentro del ámbito actual.

Dos clínicas representadas por tenants distintos pueden tener el mismo
`patient_id`, con documentos y autorizaciones independientes. Una identidad
autenticada representa un tenant por sesión; no hay un selector autorizado de
organización implementado ni compartición automática de documentos.
Esto no demuestra aprovisionamiento real ni identidad global entre clínicas.

Si varias clínicas pertenecen al mismo tenant, el modelo contiene un solo
`clinic_id` por registro de acceso y listas de profesionales. No define una
política completa de pertenencia múltiple a clínicas. La alternativa por clínica
del helper de acceso no debe interpretarse como una nueva política aprobada.

Decidir con el cliente: organización frente a clínica como tenant, vinculación
de cuentas/fichas entre organizaciones, cambio de contexto autenticado,
consentimiento y eventual compartición explícita. No se cambió ese modelo.

Las pruebas `backend/checks/test_two_clinics.py` verifican rutas FastAPI, JWT
RS256 y filtros reales con Mongo en memoria. No usan la base persistente ni
acreditan transacciones reales de MongoDB o dos organizaciones productivas.

## Android local

Consultar [PATIENT_DEMO.md](../mobile/PATIENT_DEMO.md). El APK se compila con:

```powershell
cd C:\Dev\wellq-capstone\wellq-clinical-tests-main\mobile
C:\Dev\tools\flutter\bin\flutter.bat build apk --debug --no-pub --dart-define=WELLQ_SYNTHETIC=true
Get-FileHash build\app\outputs\flutter-apk\app-debug.apk -Algorithm SHA256
```

Instalar exclusivamente en un emulador/dispositivo de demostración limpio,
identificado explícitamente. No utilizar `adb install` sin `-s`:

```powershell
$demoDevice = 'emulator-5554' # Sustituir por el ID independiente autorizado.
$adb = 'C:\Dev\tools\android-sdk\platform-tools\adb.exe'
& $adb -s $demoDevice install build\app\outputs\flutter-apk\app-debug.apk
& $adb -s $demoDevice reverse tcp:8765 tcp:8765
& $adb -s $demoDevice shell am start -n cl.wellq.wellq_mobile/.MainActivity
```

No desinstalar ni utilizar opciones de borrado o de sustitución sobre datos
existentes. El paquete y la firma no se cambiaron para crear esta demostración.
El puente local existente debe estar saludable; usar exclusivamente
`local_web.py bridge-only`, nunca el arranque con semillas. Abrir React local
con el procedimiento existente de acceso profesional.

Recorrido: conectar paciente sintético → exámenes → importar PDF sintético →
visualizar → guardar pendiente → autorizar Enviar explícitamente → consultar
estado → revisar/corregir extracción disponible → confirmar → cerrar sesión.
En React: iniciar sesión profesional → paciente autorizado → mismo examen →
revisión/validación cuando corresponda → logout. No usar las operaciones del
teléfono protegido ni presentar el Score no aprobado como resultado clínico.

## Preparación remota, todavía cerrada

Arquitectura requerida: HTTPS ngrok → entrada de demostración independiente →
React compilado y API de demostración autenticada → red privada de Mongo/objetos.
No apuntar ningún túnel a 5178, 8765 ni al proyecto Docker protegido.

Se añadió `tools/capstone_demo/preview.py`, un servidor de recursos compilados
en `127.0.0.1:9080`. No es un servidor clínico ni un proxy: API/health/ready
responden 503; el adaptador local, claves, directorios y escrituras son rechazados.
No registra URLs ni tokens. No habilita login por sí solo.

Preparar el build sin el adaptador local, en una terminal independiente:

```powershell
cd C:\Dev\wellq-capstone\wellq-clinical-tests-main\frontend
$env:VITE_DATA_MODE = 'api'
Remove-Item Env:WELLQ_LOCAL_INTEGRATION -ErrorAction SilentlyContinue
Remove-Item Env:WELLQ_LOCAL_PROFESSIONAL_LOGIN -ErrorAction SilentlyContinue
npm run build
cd C:\Dev\wellq-capstone
.venv\Scripts\python.exe -B tools\capstone_demo\preview.py --dist wellq-clinical-tests-main\frontend\dist
```

No se debe tratar el build compilado como un login sintético remoto funcional:
`window.wellqIdentity` todavía necesita un adaptador de demostración autorizado,
aislado y probado, sin claves privadas en el navegador. Una contraseña de túnel
no reemplaza JWT, RBAC ni la relación asistencial del backend.

`tools/capstone_demo/ngrok-deny-all.yml` responde 503 a todas las peticiones.
La sintaxis se contrastó con la documentación oficial de
[custom-response](https://ngrok.com/docs/gateway/traffic-policy/actions/custom-response).
No se instaló ngrok ni se inició un túnel. Tras autorización posterior, el comando
de comprobación de cierre sería el siguiente (no abre una aplicación utilizable):

```powershell
ngrok http http://127.0.0.1:9080 --traffic-policy-file tools/capstone_demo/ngrok-deny-all.yml
```

Configurar el authtoken de ngrok por su mecanismo privado oficial, nunca en Git,
archivos públicos ni capturas. Antes de retirar la denegación por defecto:

1. Crear/verificar una API, base y almacenamiento efímeros independientes; sin
   montar volúmenes, claves o fixtures del entorno actual. Preservar JWT y RBAC.
2. Validar el emisor sintético aislado y el acceso de los participantes; limitar
   exposición, duración y frecuencia. No publicar el emisor loopback existente.
3. Usar un único origen HTTPS para React/API. Si se necesita CORS, permitir solo
   el origen público exacto, nunca `*`; verificar preflight y expiración/logout.
4. Adaptar Flutter: hoy `ApiClient.origin` es loopback y `LoopbackIdentity` usa
   `/__wellq_local`. No existe aún configuración remota verificada. Separar el
   origen HTTPS del adaptador de identidad sin permitir este último en release.
5. Revisar también las URL firmadas de objetos: deben ser HTTPS alcanzables y
   autorizadas, no una exposición pública directa del almacenamiento/Mongo.
6. Repetir pruebas anónimas, pacientes/tenants ajenos, permisos, expiración,
   logout, cargas idempotentes y ausencia de claves privadas en artefactos.
7. Solicitar autorización de activación pública con la evidencia anterior.

La política ngrok no fue ejecutada contra el servicio: la preparación estática
y los tests locales no acreditan aislamiento de una futura infraestructura.

## Resultado de esta preparación (2026-11-11)

- Doce casos multi-tenant aprobados y cuatro tests HTTP locales del servidor
  de preparación aprobados; cero fallos/omisiones en las ejecuciones finales.
  Advertencias preexistentes de deprecación Starlette/datetime/Pydantic.
- Ruff y formato Python aprobados. Sin cambios de código clínico/autorización.
- APK debug construido desde `7ad57fca194864586cc94082fe5227f663d6d576`:
  `mobile/build/app/outputs/flutter-apk/app-debug.apk`, 198376724 bytes;
  paquete `cl.wellq.wellq_mobile`, versión `0.3.0+4`, debuggable, firma verificada
  y coincidente con el APK anterior preservado. SHA-256:
  `379090411434682643e8d54b322473397088670b5b21055e947b4a0ee13a56a9`.
  Su kernel incluye la acción nueva `renewPatientSession` de la UI actual.
  El aviso de versiones XML del SDK no impidió completar la compilación.
- No se ejecutó Android: no se encontró AVD configurado y había 692 MiB libres
  de 6091 MiB. No se conectó ni inspeccionó el teléfono protegido.
- React compilado en modo API sin el plugin de identidad local, con contratos
  OpenAPI y TypeScript aprobados. Artefacto privado en
  `backend/integration/.runtime/capstone-demo/portal-dist`. La comprobación HTTP
  del artefacto real devolvió 200 para entrada/JS, 503 para API y 404 para el
  adaptador local; el servidor efímero se cerró al terminar. No fue una prueba
  visual de navegador ni de login remoto. No había PDF, PEM, KEY o SQLite en
  ese directorio compilado; esto no certifica todo el contenido de su JavaScript.
- La nueva preparación no modifica Mongo, volúmenes, Docker, WSL, el puente
  existente, Score o la instalación Android. No se inició ngrok.

Para previsualizar **el artefacto realmente construido**, desde la raíz:

```powershell
.venv\Scripts\python.exe -B tools\capstone_demo\preview.py --dist wellq-clinical-tests-main\backend\integration\.runtime\capstone-demo\portal-dist
```

El login funcional local sigue usando el procedimiento previo de React/Vite y
el puente autorizado, sin túnel. No confundirlo con esta previsualización cerrada.
