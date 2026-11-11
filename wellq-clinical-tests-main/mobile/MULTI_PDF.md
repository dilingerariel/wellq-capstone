# PDF sintéticos múltiples — desarrollo

La selección local reutiliza FilePicker. Se comprueban extensión `.pdf`, tamaño
no vacío hasta 20 MiB, cabecera `%PDF-1.x`/`%PDF-2.0` y cierre `%%EOF`.
FilePicker no proporciona MIME en su interfaz común: el tipo se comprueba por
contenido y la cola conserva `mime_type=application/pdf`; la bóveda rechaza otro
MIME persistido. Esto no es un análisis completo del PDF ni un escaneo antivirus.

Al seleccionar se copia el contenido en memoria y se obtiene su hash para la
vista previa. Cambiar de archivo reinicia las confirmaciones de documento
sintético y consentimiento. El ejemplo incluido sigue disponible y conserva su
comprobación contra el hash histórico. Seleccionar o guardar no envía el archivo.

Al guardar se reutilizan el UUID, ruta privada `uploads/<UUID>.pdf`, copia
`.part`, recuperación y metadatos existentes. El hash SHA-256 y tamaño se guardan
en `payload.initiate.sha256` y `size_bytes`, ya persistidos como JSON por Drift.
No cambia el esquema v2 ni sus migraciones. Los nombres originales no se envían:
se conserva el nombre técnico `synthetic.pdf` del contrato actual.

Abrir, recuperar y preparar bytes para reanudación compara el archivo con el
hash **persistido de esa operación**, no con un hash calculado al abrir como nueva
referencia. Un archivo distinto, incompleto o sin hash se rechaza y conserva para
diagnóstico; no se elimina ni se recalcula el hash esperado. Las operaciones
anteriores que ya guardaban el hash del ejemplo siguen siendo compatibles.

`FileVault` se separó en un archivo Dart puro para probar archivos reales sin
Flutter tester. `uploads.dart` lo reexporta para conservar sus importaciones.
No cambia el coordinador, autorización de envíos, leases, idempotencia ni
aislamiento por identidad. El bloqueo productivo de la app sigue activo.

## Comprobación aislada

Desde `mobile`, con el Dart del SDK existente y sin servicios:

```powershell
& 'C:/Dev/tools/flutter/bin/cache/dart-sdk/bin/dart.exe' --enable-asserts test/multi_pdf_check.dart
```

La comprobación utiliza dos variantes del PDF sintético, archivos privados y
metadatos serializados en un directorio temporal nuevo. No abre SQLite, no
ejecuta widgets ni HTTP, y no toca el Android. Conserva los fixtures temporales.
Comprueba hashes distintos, copia interrumpida recuperable, reapertura con los
mismos metadatos, compatibilidad histórica, cero intentos pendientes, rechazo de
modificación, tipo/extensión/firma/tamaño inválidos y ausencia de hash esperado.

## Límites pendientes

Solo documentos sintéticos declarados por el usuario: el formato y el hash no
demuestran que el contenido no sea clínico real. No hay nuevas identidades ni
envíos automáticos. La protección de hashes presupone el aislamiento del almacén
privado; no autentica metadatos frente a quien controle también la base local.
Quedan pendientes la validación del selector/visor en un dispositivo aislado,
regresión Flutter/Drift y E2E autorizadas, y acreditación productiva de identidad,
escaneo, procesamiento, cifrado y privacidad. Un PDF admitido localmente puede
ser rechazado por el backend o no disponer de extracción; no se fabrican datos.
