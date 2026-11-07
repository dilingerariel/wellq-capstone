# Carga de documentos desde React

Ruta `/upload`, disponible para pacientes. El modo demo permite revisar el formulario y validar una selección, pero no envía archivos. El modo API necesita una sesión del host aprobado con `clinical:read` y `clinical:write`; el backend vuelve a verificar cada permiso y propietario. El profesional no puede iniciar este flujo de paciente.

## Contrato implementado

1. Selección accesible de PDF/JPG/JPEG/PNG/HEIC, extensión y MIME compatibles, nombre seguro, tamaño positivo de hasta 20 MiB (límite predeterminado actual del servidor). Si el navegador no declara MIME, se toma el declarado por la extensión permitida; el worker siempre comprueba los bytes. Un límite servidor más estricto produce 413 y nunca se elude.
2. Título, fecha, tipo, notas opcionales y consentimiento IA explícito, desactivado por defecto. SHA-256 calculado sobre los bytes reales en memoria.
3. POST `/api/v1/clinical-tests/uploads/initiate` con `InitiateUploadRequest` y `Idempotency-Key`. No se envía un paciente/tenant elegido por el formulario: provienen de la identidad verificada en FastAPI.
4. PUT directo del `File` a `upload.signed_url`, con método y `required_headers` del servidor. Transporte XHR independiente, sin bearer del backend, sin credenciales cross-origin, con timeout de 120 s y progreso real solo cuando `lengthComputable` lo permite. 100 % indica bytes enviados por el navegador; no acredita verificación del servidor. Se rechazan destinos del mismo origen que el portal, URL con userinfo, HTTP remoto y headers de autenticación/forzados por el navegador. GCS debe utilizar su origen de almacenamiento, no un proxy autenticado de la aplicación.
5. POST `/uploads/{upload_id}/complete` con `client_upload_id`, `sha256`, `size_bytes` y otra clave idempotente estable. No se declara disponibilidad por un initiate, un PUT o un complete aislados. No se sigue un `status_url` arbitrario: se construye la ruta tipada.
6. GET `/uploads/{upload_id}/status`. Los estados `initiated`, `object_uploaded`, `processing`, `ready_for_review`, `rejected`, `failed` y `deleted` se distinguen de las fases locales. El servidor no distingue en esta respuesta un job pendiente de uno ejecutándose: no se inventa esa distinción. Se muestran los controles MIME/seguridad informados.
7. Con consentimiento IA y archivo listo, GET `/clinical-tests/{id}/extraction`. Solo se muestra «esperando confirmación humana» cuando la respuesta lo declara. `409 EXTRACTION_NOT_READY` mantiene la consulta limitada; no equivale a rechazo ni confirma un resultado. Los demás errores no se interpretan como ese código. No se ejecutan confirmaciones, interpretaciones o validaciones clínicas desde este módulo.

Las peticiones API tienen timeout de 15 s. El sondeo hace como máximo 20 consultas de estado por activación, con pausas crecientes de 3 a 15 s; al alcanzar el límite se detiene y ofrece una consulta explícita posterior. No hay reintentos automáticos de escrituras. `Retry-After` impide reenviar anticipadamente. Una operación tiene un único propietario de ejecución; el doble clic no crea otro upload.

## Interrupciones e idempotencia

El controlador vive fuera de la ruta y conserva `File`, formulario, checksum, IDs y claves en RAM al navegar por el portal. Una desconexión/identidad temporalmente sin verificar aborta el trabajo local activo y conserva el contexto vigente. Reconectar primero revalida la sesión y **no envía escrituras automáticamente**: requiere «Continuar o reintentar». Una cancelación local no revoca peticiones ya recibidas ni detiene el worker del servidor.

- Si se perdió la respuesta de initiate, se repite el mismo cuerpo y la misma clave.
- Un primer initiate rechazado definitivamente por validación permite corregir los datos sin perder el `File`. Si hubo alguna respuesta previa incierta, el cuerpo permanece bloqueado para no convertir el reintento en otra carga.
- Si existe `upload_id`, se consulta primero el estado antes de decidir cualquier escritura. Si el servidor ya procesa o terminó, no se vuelve a transferir ni completar.
- Antes de reintentar un PUT se obtiene una autorización vigente por POST `/uploads/{id}/refresh-url`, con checksum/client ID originales. Una respuesta perdida conserva su clave de renovación; una URL ya reconocida pero caducada, o rechazada por 403, requiere una nueva renovación.
- Un PUT confirmado no se repite tras un fallo de complete. Se reusa su clave y se consulta el estado para reconciliar una respuesta perdida.
- La precondición `x-goog-if-generation-match: 0` evita sobrescritura. Si una transferencia con respuesta perdida dejó el objeto creado, un 412 no se presenta como éxito: se solicita la verificación normal del servidor. Solo el worker puede aprobar checksum, tamaño y formato del objeto existente.

No hay reanudación por bloques: un PUT interrumpido puede empezar de nuevo. No se usa IndexedDB, localStorage, CacheStorage ni cola durable para archivos o metadatos clínicos. El shell PWA sigue cacheando exclusivamente sus recursos públicos. Al cerrar/recargar quizá haya que seleccionar el archivo otra vez; se avisa y se registra `beforeunload` mientras aún se necesita conservar el original, sujeto al comportamiento del navegador. Cerrar sesión, expirar, cambiar cuenta/tenant/permisos limpia el contexto privado y cancela resultados obsoletos. «Nuevo documento» pide confirmación y no borra nada del servidor.

La indicación de prescindir de la copia original aparece **solo** si una respuesta de estado devuelve `local_file_can_be_deleted=true`. El navegador nunca elimina archivos del dispositivo. Verificación del archivo, extracción y revisión clínica son procesos independientes.

La deduplicación cubre reintentos de la misma operación conservada en RAM. Tras cerrar/recargar se pierden sus claves; revisar el listado antes de iniciar otra carga evita crear una segunda operación por desconocer el resultado anterior. No se promete deduplicación por contenido entre sesiones independientes.

## Verificación disponible

`npm.cmd run test:live` usa el proyecto de integración ya aprovisionado y protegido por sus comprobaciones de propiedad. Arranca únicamente Mongo/API/objects, sin puertos Docker publicados. La autoridad RS256 es sintética; no se emiten JWT en React. Un relay loopback transporta HTTP real y traduce únicamente el origen de la URL del gateway de pruebas, conservando ruta, firma, método y headers. El navegador ejecuta initiate, PUT de bytes, complete y status sin interceptaciones Playwright.

El worker **de producto sin modificar** se invoca dentro del contenedor con su adaptador de almacenamiento de integración. Sus operaciones iniciales de lease se restringen al tenant sintético recién creado, sin consumir jobs de otros tenants. Se comprueban SHA-256/tamaño del objeto promovido, estado `ready_for_review`, generación, auditoría y existencia de un solo documento tras doble clic. Se conservan registros/objetos sintéticos y se detienen todos los contenedores iniciados. No se aprovisiona ni reinicializa MongoDB, no se eliminan datos y no se modifican los fuentes del backend.

El almacenamiento de esta prueba es el **doble HTTP firmado respaldado por archivos** existente. El análisis antivirus también es un doble explícito. No se pidió IA en la prueba de carga. Esto no acredita firmas V4/IAM/CORS de GCS, antivirus productivo ni un proveedor SSO. Las interrupciones, expiración, errores PUT/complete, cambios de identidad y fallos de red se inyectan en Vitest/Playwright y se identifican como tales.

Resultado local: 51 pruebas Vitest, 29 escenarios Playwright de regresión y tres escenarios de navegador contra HTTP real aprobados, además de 15 comprobaciones API directas. Se verificaron los diez anchos, horizontal/tacto, teclado, reflow equivalente al 200 %, Axe, tema oscuro, ES/EN y PWA offline. El PDF sintético de 1.386 bytes llegó por un solo PUT, sin Authorization, y el worker verificó el objeto promovido y un único documento. Typecheck, lint, formato, contratos, build, escáner de la selección y `npm audit` aprobaron. Backend y documentos académicos conservaron sus bytes; no hubo push ni merge.

## Conectar producción

1. Completar el host externo y configuración JWT de [INTEGRATION.md](INTEGRATION.md), sesión real de paciente con permisos y backend/Mongo autenticados ya aprovisionados. No se cambió esa configuración en esta entrega.
2. Configurar en el servidor `GCS_PROJECT_ID`, `GCS_BUCKET_NAME` y credenciales de firma autorizadas (ADC o `GCS_CREDENTIALS_PATH` privado). El backend exige bucket privado con uniform bucket-level access y public access prevention enforced. Las claves y el acceso a Mongo nunca van al bundle ni a `VITE_*`.
3. Autorizar el origen HTTPS exacto del portal en el CORS del bucket para PUT y sus headers `Content-Type` y `x-goog-if-generation-match`; probar el preflight desde ese origen y las respuestas de éxito/error. No hacer público el bucket ni usar comodines por comodidad. La política del bucket es independiente de FastAPI. Véanse [CORS de Cloud Storage](https://docs.cloud.google.com/storage/docs/cross-origin) y [configuraciones de carga directa](https://docs.cloud.google.com/storage/docs/cors-configurations).
4. Ejecutar el worker existente con acceso privado al almacenamiento, Mongo y un escáner real configurado en `CLAMAV_HOST`/`CLAMAV_PORT`. Un PUT exitoso sin worker/verificación no habilita borrar el original. Para consentimiento IA, configurar y aprobar además el proveedor del backend; no se aprobó ni habilitó uno productivo aquí.
5. Servir API por proxy/TLS, mantener secretos fuera de Git y limitar logs/telemetría: no capturar bodies, headers Authorization ni URLs firmadas. Verificar el flujo con un PDF sintético en la infraestructura autorizada antes de datos reales, incluidos límites efectivos, CORS, permisos, expiración y rechazo de contenido.
