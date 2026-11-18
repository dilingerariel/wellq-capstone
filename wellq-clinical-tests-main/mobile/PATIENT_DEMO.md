# Recorrido del paciente para la demostración

Solo desarrollo debug e información sintética. El profesional usa React; la
app del paciente no ofrece Score ni interpretación médica. La cuenta demo del
paciente inicia sesión con `POST /api/v1/auth/login` o se registra con
`POST /api/v1/auth/patient/register`. El servidor genera su `patient_id` y
vincula la cuenta a una clínica y un clínico activo. Los clínicos no se pueden
registrar desde la app; solo el administrador los crea en el portal.
El backend debe ser una instancia demo aislada, con `ENVIRONMENT=test`,
`WELLQ_DEMO_AUTH_ENABLED=true`, MongoDB solo sintético y una única instancia
API. Esta autoridad demo no sustituye el proveedor productivo de identidad.

## Abrir en una instalación independiente

No usar el teléfono protegido ni sus cuatro operaciones. Preparar un emulador
vacío autorizado únicamente cuando haya memoria suficiente. Conservar el
entorno de integración y recuperar solo el puente con `local_web.py bridge-only`
si hace falta; no usar el arranque habitual que ejecuta semillas.

Desde `wellq-clinical-tests-main/mobile`, con el SDK local:

```powershell
# Sustituir dominio e ID por los del backend demo y el emulador independiente.
$patientEmulator = 'emulator-5554'
C:\Dev\tools\flutter\bin\flutter.bat run --debug -d $patientEmulator `
  --dart-define=WELLQ_SYNTHETIC=true `
  --dart-define=WELLQ_DEMO_IDENTITY=true `
  --dart-define=WELLQ_DEMO_ORIGIN=https://api-demo.example.com `
  --dart-define=WELLQ_DEMO_HOST=api-demo.example.com
```

Reemplazar el dominio de ejemplo por el dominio HTTPS del backend demo. El
botón inicia sesión directamente; los tokens se mantienen en RAM y no se
incluyen en el APK ni en SQLite. No compilar este modo para profile/release.

No se ejecutaron esos comandos contra Android durante esta validación.
Release y profile conservan el bloqueo de la identidad sintética.

## Demostrar el recorrido

1. Iniciar sesión o registrar paciente, seleccionando una clínica y un clínico activo.
   El correo debe ser único y la contraseña debe tener al menos 12 caracteres.
2. Comprobar Inicio y Mis exámenes. En **Cargar**, elegir exclusivamente el PDF sintético.
   Abrir su visor, volver y completar título, fecha y ambos consentimientos.
3. **Guardar como pendiente** conserva el PDF privado y su SHA-256. No envía.
   Mientras se selecciona/lee un archivo no se permite guardar ni abrir otro
   selector; cancelar conserva el borrador y la selección anterior.
4. En **Pendientes**, pulsar explícitamente Enviar o Reintentar. Consultar
   estados cuando el servidor procese el archivo. Recepción verificada no es
   confirmación del paciente ni validación profesional.
5. Abrir el examen y su extracción. Corregir únicamente cuando el servidor lo
   permita, cotejar los valores, revisar el resumen y confirmar explícitamente.
6. En **Ajustes**, renovar sesión/consultar estados no reenvía documentos.
   Cerrar sesión requiere confirmación, oculta datos y conserva filas/PDF.
   La cuenta siguiente no obtiene la cola ni las copias privadas de la anterior.

## Pruebas de interfaz

`patient_journey_widget_test.dart` usa widgets, controlador, SQLite y archivos
temporales reales, con dobles HTTP y del selector nativo expresamente definidos.
Incluye login, renovación, PDFium, cola, envío explícito, confirmación, logout,
expiración y cambio de identidad. `patient_navigation_widget_test.dart` comprueba
la navegación ES/EN, temas, texto al 200 %, etiquetas y objetivos táctiles.

Ejecutar secuencialmente con Flutter Linux 3.47.9, dependencias ya disponibles y
`PDFIUM_PATH` apuntando a su biblioteca Linux verificada:

```bash
flutter test --concurrency=1 test/patient_navigation_widget_test.dart
flutter test --concurrency=1 test/patient_journey_widget_test.dart
```

Los widgets con dobles no sustituyen la integración HTTP real ya realizada ni
una ejecución Android. Los resultados finales y las limitaciones se registran
en la entrega; no considerar aprobados los intentos interrumpidos por memoria.

Validación de este bloque (2026-11-11): diez casos únicos aprobados, cero
fallidos y cero omitidos pendientes: cuatro de navegación y seis del recorrido.
Se ejecutaron secuencialmente en una copia Linux aislada, con SQLite temporal y
PDFium. Cinco casos del recorrido aprobaron juntos; el caso del visor y
confirmación aprobó en una repetición individual después de corregir el helper
de regreso en español. Los intentos anteriores con falta de memoria, timeout o
limpieza incorrecta del temporizador no se contabilizan como aprobaciones.
No se repitió la regresión móvil completa ni el E2E clínico. Android, selector
nativo real y aceptación visual en dispositivo siguen pendientes; el equipo no
dispuso de margen suficiente para ejecutar un emulador de forma segura.
