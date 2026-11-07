# Revisión y validación clínica

Ruta `/exams/:id/clinical-review`, exclusiva del profesional en modo API, desde el detalle del examen. Conserva selección de paciente y filtros de estado/tipo existentes; no agrega filtros clínicos que el endpoint de listado no acepta. El paciente y el tenant se autorizan nuevamente en FastAPI. Sin identidad externa configurada no hay operaciones reales ni fallback a demo.

## Dos operaciones independientes

- **PATCH `/clinical-tests/{id}/review`**: `ReviewRequest`, `review_status=reviewed`, `review_note` privada opcional, hasta 2000 caracteres. Exige `clinical:review`, relación clínica y archivo verificado disponible. La revisión es inmutable: el mismo profesional con la misma nota recibe el resultado existente; otra nota u otro profesional recibe 409. No utiliza Idempotency-Key y no valida la extracción.
- **POST `/clinical-tests/{id}/extraction/validate`**: `ClinicianValidationRequest`, `validation_status=validated|rejected`, `clinical_note` independiente y `marker_corrections`. Exige `extractions:validate`, relación clínica y extracción `confirmed`. Se corrigen solo valores/unidades de marcadores numéricos mapeados, únicos y con validación pasada; opcionalmente se indica `reason`. No se añaden ni eliminan marcadores, cambian referencias ni calculan diagnósticos/puntuaciones en React. El catálogo del servidor decide unidades, conversión y plausibilidad. Errores 422 por marcador se muestran mediante códigos acotados, sin reflejar mensajes internos o valores rechazados.

Rechazar invalida marcadores vigentes; no aplica correcciones. La interfaz bloquea rechazo si quedan cambios de valor/unidad para evitar perderlos silenciosamente. No hay ampliación de permisos, ni control de descarte/reproceso. Las notas sin enviar de la otra operación permanecen en el borrador después de una respuesta exitosa.

## Estados y límites del contrato actual

Se distinguen revisión `not_reviewed/reviewed` del documento y extracción `confirmed/clinically_validated/rejected`. La vista muestra valores, unidades, referencias, procedencia y banderas del servidor. No convierte una espera en éxito. Cada envío tiene resumen y confirmación explícita, y un único propietario de ejecución bloquea doble clic.

Antes de escribir se revalida identidad y se vuelven a consultar documento y extracción. Se comparan paciente, ID, contenido y metadatos públicos; cualquier cambio observado bloquea el envío sin sobrescribir el borrador. Las respuestas tardías se descartan por generación. El servidor conserva sus transacciones y reglas de concurrencia.

**Precondición atómica:** GET del documento y GET de la extracción incluyen `clinical_version`, huella opaca del documento y de la extracción vigente, calculada sin truncar los timestamps. PATCH review y POST validate reciben `expected_version`. FastAPI compara la versión dentro de la transacción existente antes de modificar el dominio; Mongo detecta escrituras concurrentes. Revisión, validación, rechazo y correcciones comparten esta precondición. Una sustitución de extracción también la invalida. Un conflicto devuelve 409 `CLINICAL_VERSION_CONFLICT` o `RETRYABLE_CONFLICT`, conserva el borrador RAM y no reenvía mutaciones. Una lectura mezclada de versiones también bloquea el envío.

Los clientes anteriores pueden seguir leyendo; las nuevas escrituras clínicas sin versión reciben 428 `CLINICAL_VERSION_REQUIRED`, sin cambios. Deben leer el detalle vigente y enviar su versión. Se conserva el reintento semántico de revisión del mismo profesional con la misma nota, incluso con versión antigua; no cambia el revisor ni duplica auditoría. Validación/rechazo conservan su contrato sin replay idempotente. OpenAPI y tipos generados reflejan estos campos. No requiere migración ni nuevas credenciales.

Ante timeout/503 o resultado incierto, la revisión conserva el mismo cuerpo y permite reintento expreso bajo la semántica inmutable del servidor. La validación/rechazo **no se repite**: la acción de reconciliar solamente lee. Un estado terminal observado no se atribuye automáticamente a este envío. Se muestra incertidumbre y se requiere consultar/cargar conscientemente el estado actual antes de preparar otra operación. No se inventa un lock ni un registro de auditoría cliente. Un 429 respeta Retry-After; 401 borra la identidad; 403/404/409/422 y fallos de servicio se manejan sin dar por realizada una operación.

**Lectura tras rechazo:** GET permite `rejected` al profesional autorizado con los mismos scopes, tenant y relación clínica. Tras recargar y seleccionar de nuevo el paciente, la vista representa el rechazo del servidor y mantiene deshabilitadas las correcciones y validaciones. La prueba de navegador real verifica esta recarga. Las notas privadas siguen fuera de GET; la propuesta y la confirmación original se conservan.

Las notas privadas de revisión no se devuelven en GET del documento. GET extraction elimina las notas clínicas de su bloque público de confirmación. No se simula recuperar notas anteriores; los formularios se identifican como borradores nuevos. El esquema cliente excluye además las notas del bloque público y la ruta clínica está protegida por rol. La prueba aislada comprueba su ausencia en GET del paciente.

## RAM, offline y consultas

El controlador vive fuera de la ruta. Navegar conserva el borrador en RAM; cerrar/recargar lo pierde y se avisa. No usa almacenamiento clínico persistente ni cambia el service worker. Offline bloquea escrituras, conserva notas/correcciones y no reproduce operaciones al reconectar. La reconexión revalida sesión; cada envío vuelve a comprobar permisos y estado.

Se corrigió una carrera de recuperación de lecturas: después de aprobar la identidad se espera la activación de los observadores React y se consultan únicamente lecturas activas obsoletas, sin cancelar una lectura ya en curso. Se comprueba de nuevo la identidad/conexión antes de hacerlo. No se reenvía ninguna mutación clínica.

Cambiar paciente exige confirmar antes de descartar un borrador o envío pendiente; se cancela el trabajo local, se limpia el contexto anterior y se retiran consultas de otro paciente. Cancelar no revoca operaciones ya recibidas por el servidor. Cerrar/cambiar identidad, tenant, rol o permisos, o expirar, limpia inmediatamente datos privados por seguridad, sin esperar una confirmación que retenga datos de otra identidad.

Tras éxito se usan las respuestas reales y se restablecen las consultas de examen/listado para evitar reutilizar datos anteriores. La auditoría solo la crea FastAPI. No se muestran puntuaciones clínicas no aprobadas ni se añaden reglas médicas al cliente.

## Verificación

Cierre de integridad: 416 pruebas backend, 99 Vitest, 62 escenarios Playwright y cuatro escenarios de navegador contra FastAPI/Mongo y carreras HTTP con información sintética. En las carreras revisión/revisión, validación/validación, revisión/validación y corrección/rechazo hay un 200 y un 409. Se verifican versiones obsoletas, extracción sustituida, cliente sin versión (428), replay autorizado, auditoría/historial sin duplicados y lote inválido sin cambios parciales. El arn?s monta el backend actual en solo lectura en una API separada, conserva la imagen/API original y comprueba sus fuentes. Solo escribe fixtures sintéticos del tenant de prueba; MongoDB de desarrollo queda fuera de estas pruebas. No acredita SSO, almacenamiento, antivirus ni IA de producción.

La recuperación de lecturas observa la activación tardía de consultas tras aprobar la identidad. Comparte peticiones en curso y permite un intento por consulta y recuperación; no reproduce mutaciones ni crea bucles de reintento. Las pruebas cubren montaje tardío, revocación, cancelación y fallo de servicio conservando RAM.

Typecheck, lint frontend, formato, contratos, build y escaneo de secretos de cambios aprobados; npm audit sin vulnerabilidades conocidas. Se preservaron 354 archivos versionados fuera del alcance autorizado, incluidos scoring, configuración y documentos académicos. El gate global Ruff sigue señalando un I001 previo en `backend/tests/test_recompute_batch.py`, idéntico a HEAD; esta corrección no introduce infracciones Ruff nuevas ni modifica su baseline. Los proveedores externos siguen pendientes de validación de producción. Sin push ni merge.
