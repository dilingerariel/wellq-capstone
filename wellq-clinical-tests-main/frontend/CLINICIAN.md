# Revisión y validación clínica

Ruta `/exams/:id/clinical-review`, exclusiva del profesional en modo API, desde el detalle del examen. Conserva selección de paciente y filtros de estado/tipo existentes; no agrega filtros clínicos que el endpoint de listado no acepta. El paciente y el tenant se autorizan nuevamente en FastAPI. Sin identidad externa configurada no hay operaciones reales ni fallback a demo.

## Dos operaciones independientes

- **PATCH `/clinical-tests/{id}/review`**: `ReviewRequest`, `review_status=reviewed`, `review_note` privada opcional, hasta 2000 caracteres. Exige `clinical:review`, relación clínica y archivo verificado disponible. La revisión es inmutable: el mismo profesional con la misma nota recibe el resultado existente; otra nota u otro profesional recibe 409. No utiliza Idempotency-Key y no valida la extracción.
- **POST `/clinical-tests/{id}/extraction/validate`**: `ClinicianValidationRequest`, `validation_status=validated|rejected`, `clinical_note` independiente y `marker_corrections`. Exige `extractions:validate`, relación clínica y extracción `confirmed`. Se corrigen solo valores/unidades de marcadores numéricos mapeados, únicos y con validación pasada; opcionalmente se indica `reason`. No se añaden ni eliminan marcadores, cambian referencias ni calculan diagnósticos/puntuaciones en React. El catálogo del servidor decide unidades, conversión y plausibilidad. Errores 422 por marcador se muestran mediante códigos acotados, sin reflejar mensajes internos o valores rechazados.

Rechazar invalida marcadores vigentes; no aplica correcciones. La interfaz bloquea rechazo si quedan cambios de valor/unidad para evitar perderlos silenciosamente. No hay ampliación de permisos, ni control de descarte/reproceso. Las notas sin enviar de la otra operación permanecen en el borrador después de una respuesta exitosa.

## Estados y límites del contrato actual

Se distinguen revisión `not_reviewed/reviewed` del documento y extracción `confirmed/clinically_validated/rejected`. La vista muestra valores, unidades, referencias, procedencia y banderas del servidor. No convierte una espera en éxito. Cada envío tiene resumen y confirmación explícita, y un único propietario de ejecución bloquea doble clic.

Antes de escribir se revalida identidad y se vuelven a consultar documento y extracción. Se comparan paciente, ID, contenido y metadatos públicos; cualquier cambio observado bloquea el envío sin sobrescribir el borrador. Las respuestas tardías se descartan por generación. El servidor conserva sus transacciones y reglas de concurrencia.

**Limitación que requiere evolución del backend:** POST validate no acepta `extraction_id`, ETag/If-Match ni clave idempotente. Una revalidación GET reduce conflictos, pero no cierra la ventana entre lectura y escritura: si otro proceso sustituye una extracción por otra también confirmada durante esa ventana, el servidor decide sobre la vigente. React no puede garantizar una precondición atómica que el endpoint no ofrece. Se necesita añadir una versión/ID esperado al contrato y verificarlo dentro de la transacción antes de afirmar protección completa frente a ese caso. No se ha modificado el backend para ocultar esta limitación.

Ante timeout/503 o resultado incierto, la revisión conserva el mismo cuerpo y permite reintento expreso bajo la semántica inmutable del servidor. La validación/rechazo **no se repite**: la acción de reconciliar solamente lee. Un estado terminal observado no se atribuye automáticamente a este envío. Se muestra incertidumbre y se requiere consultar/cargar conscientemente el estado actual antes de preparar otra operación. No se inventa un lock ni un registro de auditoría cliente. Un 429 respeta Retry-After; 401 borra la identidad; 403/404/409/422 y fallos de servicio se manejan sin dar por realizada una operación.

**Lectura tras rechazo:** GET extraction actualmente devuelve 409 al profesional para estados distintos de confirmed, clinically_validated y not_applicable, incluido rejected. El resultado rejected se muestra desde la respuesta real del POST mientras siga en RAM. Después de consultar nuevamente o recargar no se inventa ese estado: se informa que el servidor no permite leer la extracción, lo que también puede ocurrir mientras espera confirmación del paciente. Distinguir ambas situaciones tras recarga requiere ampliar la proyección de lectura del backend.

Las notas privadas de revisión no se devuelven en GET del documento. GET extraction elimina las notas clínicas de su bloque público de confirmación. No se simula recuperar notas anteriores; los formularios se identifican como borradores nuevos. El esquema cliente excluye además las notas del bloque público y la ruta clínica está protegida por rol. La prueba aislada comprueba su ausencia en GET del paciente.

## RAM, offline y consultas

El controlador vive fuera de la ruta. Navegar conserva el borrador en RAM; cerrar/recargar lo pierde y se avisa. No usa almacenamiento clínico persistente ni cambia el service worker. Offline bloquea escrituras, conserva notas/correcciones y no reproduce operaciones al reconectar. La reconexión revalida sesión; cada envío vuelve a comprobar permisos y estado.

Se corrigió una carrera de recuperación de lecturas: después de aprobar la identidad se espera la activación de los observadores React y se consultan únicamente lecturas activas obsoletas, sin cancelar una lectura ya en curso. Se comprueba de nuevo la identidad/conexión antes de hacerlo. No se reenvía ninguna mutación clínica.

Cambiar paciente exige confirmar antes de descartar un borrador o envío pendiente; se cancela el trabajo local, se limpia el contexto anterior y se retiran consultas de otro paciente. Cancelar no revoca operaciones ya recibidas por el servidor. Cerrar/cambiar identidad, tenant, rol o permisos, o expirar, limpia inmediatamente datos privados por seguridad, sin esperar una confirmación que retenga datos de otra identidad.

Tras éxito se usan las respuestas reales y se restablecen las consultas de examen/listado para evitar reutilizar datos anteriores. La auditoría solo la crea FastAPI. No se muestran puntuaciones clínicas no aprobadas ni se añaden reglas médicas al cliente.

## Verificación

Resultado local: typecheck, lint, formato, contratos y build aprobados; 93 pruebas Vitest y 61 escenarios Playwright aprobados, más tres repeticiones dirigidas de reconexión. Los cuatro escenarios de navegador contra FastAPI real pasaron. Los 30 controles directos de lectura/permisos/repetición, las carreras de revisión y validación (un 200 y un 409 en cada una), la privacidad de notas y las comprobaciones Mongo de correcciones, instantáneas, historia y auditoría pasaron. El escáner no encontró secretos en los cambios y npm audit informó cero vulnerabilidades conocidas. Los 368 archivos versionados fuera del frontend conservaron sus bytes; los contenedores de integración quedaron detenidos sin puertos publicados. No se hizo push ni merge.

Vitest cubre payloads separados, integridad de correcciones, doble envío, conservación de notas de la otra operación, revisión repetida, validación incierta sin replay, conflicto de extracción, permisos, límites temporales, errores y respuestas tardías. Playwright usa interceptaciones sintéticas para estados y fallos controlados, diez anchos, ES/EN, temas, Axe, tacto, teclado, reflow, offline y cambio de paciente/sesión.

`npm.cmd run test:live` reutiliza el stack aislado con sus guardas de propiedad, montajes y base. No aprovisiona ni modifica el backend. Ejecuta carga/extracción/confirmación del paciente y luego revisión, corrección clínica y rechazo desde React por HTTP real. Dos copias sintéticas identificadas del examen confirmado permiten probar rechazo y concurrencia sin repetir cargas ni atribuirlas a documentos reales. Se verifica propuesta original, instantánea confirmada del paciente, historia de correcciones, marcadores vigentes y eventos de auditoría. Dos profesionales autorizados compiten en HTTP real; se exige un ganador y un 409, sin cambiar revisor ni duplicar eventos. Se comprueban roles, scopes, tenant, relación y privacidad de notas. Se conservan fixtures y se detienen los contenedores iniciados.

La autoridad RS256, proveedor de PDF anotado, almacenamiento y escáner son de integración. Esto no valida SSO, IA, GCS ni antivirus productivos. Continúan pendientes el host aprobado con permisos clínicos y la infraestructura privada descrita en INTEGRATION.md y UPLOAD.md.
