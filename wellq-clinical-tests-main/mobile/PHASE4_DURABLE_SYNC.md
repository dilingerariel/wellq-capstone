# Fase Móvil 4: recuperación de cargas en primer plano

Alcance: paciente sintético, PDF de referencia y puente local existente. Esta fase no habilita cargas reales, inicio de sesión productivo, descarga remota, nuevos formatos ni un ejecutor en segundo plano. La recepción verificada no significa confirmación del paciente ni validación profesional.

## Persistencia y recuperación

Drift v2 añade `lease_owner` a `operations` mediante `ALTER TABLE` dentro de una transacción. No reserializa ni elimina filas, no mueve los PDF existentes y no toca la caché en la migración. El arranque toma un bloqueo de archivo para el proceso antes de abrir la base y libera únicamente las marcas de ejecución abandonadas. Cada intento toma su propia marca SQL; las escrituras y la liberación exigen la misma marca. No se recuperan marcas por volver a conectar o cambiar de sesión.

Una nueva operación guarda primero su fila, identificador, hash, claves y marca `copy_pending`. Los bytes se escriben a una ruta privada `.pdf.part` nueva. Se verifica tamaño y SHA-256 antes de promover al nombre definitivo. Al reabrir con la identidad correcta:

- Si el PDF definitivo es íntegro, se conserva; si la copia provisional está íntegra y está vinculada a una fila con `copy_pending`, se completa la promoción.
- Si el PDF falta, está incompleto, no se puede leer o su hash no coincide, se conserva la fila y se registra la incidencia. No se vuelve a copiar desde un proveedor externo ni se envía el archivo.
- Los nombres reconocibles sin una fila se cuentan como incidencias internas, sin registrar rutas o IDs ni mostrar el inventario a otro paciente. No se adoptan, sobrescriben ni purgan.

## Coordinador y estados

`PatientController` admite un intento explícito en primer plano y revalida la sesión con el adaptador existente. `UploadRepository` verifica la fila actual, ámbito, permiso y contenido; conserva la exclusión por operación y controla las transiciones. El permiso para intentar un envío queda solo en memoria, vinculado a los campos inmutables de esa operación. No se persisten tokens, URLs firmadas ni una autorización que otro proceso pueda reutilizar. Después de reiniciar, verificar identidad y consultar estados no envía nada; se requiere pulsar Enviar o Reintentar otra vez.

| Punto guardado | Recuperación |
| --- | --- |
| `initiate` sin ID remoto | Repetir la misma solicitud con el mismo `client_upload_id` e `Idempotency-Key`. |
| `status` / `renew` | Consultar el estado antes de escribir. Si la renovación quedó incierta, usar su clave persistida; si la URL devuelta venció, guardar una clave nueva antes de solicitar otra. |
| `put` | El resultado puede ser incierto. Repetir solo con creación condicional del objeto (`x-goog-if-generation-match: 0`), sin Bearer. `412` no verifica bytes ni da permiso para borrar. |
| `complete` | Preservar el checkpoint incluso si `status` sigue en `initiated`. Si ya está procesando o verificado, no repetir la mutación; de otro modo, reutilizar la clave de cierre. |
| `verify` / `settled` | Solo consultar; avanzar a recepción verificada si coinciden IDs y el servidor confirma verificación durable, MIME y escaneo. Conservar el PDF. |

Los fallos recuperables persisten el próximo instante permitido con backoff exponencial, jitter y un máximo local de cinco minutos, respetando un `Retry-After` mayor. El reloj no inicia solicitudes: cada intento sigue requiriendo acción explícita. Los conflictos no recuperables y los rechazos detienen escrituras. Salir del primer plano, pausar o cerrar sesión aborta el transporte cuando es posible y evita iniciar el paso siguiente. Un servidor puede haber aplicado una solicitud antes de recibir la cancelación; por eso la reanudación reconcilia y conserva sus claves.

Cerrar sesión elimina la sesión en RAM y su caché de lecturas. Conserva filas y PDF privados y los oculta hasta verificar el mismo tenant y paciente. No hay eliminación permanente en esta fase. Para uso real aún se necesita política aprobada de retención, claves, cifrado de aplicación, respaldo y eliminación. El almacenamiento privado no equivale a esa política.

## Procedimiento de validación

Usar una copia que contenga solo fuentes y fixtures versionables, Flutter Linux 3.47.9, Dart 3.13.7 y PDFium de Linux previamente verificado. No copiar bases del usuario ni directorios `.runtime`. Preparar dependencias, ejecutar `flutter gen-l10n`, `flutter analyze` y `flutter test --concurrency=1`. `phase4_durable_test.dart` construye una base v1 desde SQL y prueba fallos con archivos temporales y dobles HTTP. `phase4_http_test.dart` crea un receptor efímero en loopback para verificar HTTP y pérdida del acuse; no usa FastAPI, MongoDB ni un puente real. `phase4_queue_widget_test.dart` cubre ambos idiomas y temas a 200 %.

Las pruebas `WELLQ_LIVE` requieren una instancia sintética separada con datos descartables. Para pruebas físicas, preparar un dispositivo o instalación independiente con autorización antes de instalar o escribir. No usar la base ni las operaciones del teléfono existente. Un ejecutor de segundo plano queda pendiente: requeriría autorización e identidad renovables, exclusión entre procesos, políticas de energía/conectividad, protección de claves y pruebas propias en Android e iOS.

## Estado de validación del desarrollo

Se ejecutaron en Ubuntu WSL2 las 18 pruebas nuevas: 13 de persistencia/coordinación, una de HTTP real contra el receptor efímero propio y cuatro de widgets ES/EN y temas al 200 %; aprobaron. La migración v1 se probó en una base temporal construida desde SQL, sin usar la base del teléfono. El análisis Flutter del snapshot inicial aprobó y las 25 comprobaciones puras Dart heredadas también aprobaron.

La regresión completa no está cerrada. El registro parcial contiene 169 casos aprobados (incluye los 18 nuevos), dos errores y tres omisiones `WELLQ_LIVE`. Un widget heredado necesita `runAsync` para la nueva E/S de archivos; ese ajuste conserva sus aserciones y aún requiere repetición. Otro caso de reflow falló buscando un widget y requiere reproducción antes de atribuir una causa. Las nuevas sesiones WSL fallan con `WSAETIMEDOUT`; no se reinició WSL ni Docker para eludir el problema. No declarar esta fase lista para publicación ni confundir el receptor HTTP con una integración FastAPI/MongoDB.
