# Almacenamiento y procesamiento

> **Vigencia tras cierre focalizado F01-F07 (2026-11-05):** Fecha clinica invalida se registra como INVALID_CLINICAL_DATE sin perder permiso de borrado local de upload verificado. PDF almacenado sin firma retorna download_pending y permite recuperacion idempotente, sin fallback local. [Detalle y evidencia](12_CIERRE_DEFECTOS_F01_F07.md).
> El contenido anterior al cierre se conserva a continuacion como referencia historica; esta nota y el documento12 prevalecen donde difieran.

**Fecha:** 2026-11-05 (America/Santiago). **Rama:** fix/wellq-backend-hardening. **Base:** fb8746cd42fe107bbda82dd92d3a4d11d545fd3e + cambios sin commit.

**Alcance:** backend; rutas de código relativas a wellq-clinical-tests-main/backend salvo indicación. **Método:** contraste estático, implementación y pruebas aisladas. **Límites:** sin servicios clínicos, datos reales, migraciones, despliegues ni validación clínica. No se modificó frontend.


## Camino real
initiate valida metadatos y obtiene URL PUT real para quarantine/clinical-tests/<hash-tenant>/<clinical-id>/original. Requiere cabecera firmada x-goog-if-generation-match: 0: no se puede sobrescribir el objeto existente reutilizando la URL.
complete comprueba correspondencia con la sesión y deja processing + upload.job pending en el mismo documento/transacción. No confirma existencia o integridad solo por recibir complete. El cliente debe ejecutar el PUT previamente con todos los required_headers.
Worker lee la generación del objeto, limita bytes, compara tamaño y SHA-256, Content-Type y magic bytes. Parseo estricto de PDF no cifrado y páginas acotadas; JPEG/PNG/HEIC se decodifican con límites de píxeles. ClamAV INSTREAM debe responder exactamente aprobación. Falta de escáner, respuesta ambigua o error nunca se considera limpio.
Se copia la generación verificada a prefijo privado, con precondiciones de generación. La promoción es direccionada por hash; un reintento valida un destino ya creado. Cuarentena no se sirve por descarga. No se borran automáticamente objetos de cuarentena: retención/GC necesita política revisada.

## Condición de borrado local
status devuelve local_file_can_be_deleted=true solo con ready_for_review, file.verified_at, file.generation y ambos estados malware_scan/mime_validation passed. complete devuelve false incluso al repetir sesión ya verificada: el cliente debe consultar status.
La extracción, confirmación paciente y validación clínica son independientes. Un proveedor IA no disponible NO quita la autorización de borrado local de un archivo ya validado. Esta regla se prueba explícitamente.
La configuración de bucket debe proporcionar durabilidad y protección operativa; el código no prueba por sí solo las garantías de una cuenta cloud concreta.

## Outbox y garantías
La intención de verificación está embebida en upload.job del examen. Su actualización con el estado processing comparte documento y transacción. No existe una ventana entre “marcar processing” y “publicar en cola en memoria”. extraction_job es otra intención persistida, activada tras verificación y consentimiento.
El worker reclama con find_one_and_update y lease_token/lease_until, incrementa attempts y confirma mediante fencing. Al vencer lease otro worker recupera el trabajo; reintentos usan retroceso exponencial, jitter y máximo configurado. Un trabajo agotado pasa a fallo explícito, incluso si el último worker murió.
El procesamiento es al menos una vez. Copias/firmas de GCS no son parte de una transacción Mongo: pueden quedar objetos privados huérfanos si la DB aborta. Las generaciones y los checks evitan publicar un resultado equivocado; conciliación/GC queda pendiente.
No hay exactamente una vez global. No se verificaron estos mecanismos contra un replica set real. El rollback de checks es un doble de prueba, no prueba del motor de transacciones.

## Transporte
No se eligió Cloud Tasks/Pub/Sub sin conocer el despliegue. El worker de sondeo Mongo implementa consumo durable sin infraestructura adicional. Está preparado para un futuro despachador cloud, pero ese transporte NO está implementado. Debe ejecutarse como proceso administrado:
`python -m app.workers.processing`
No se inició durante este encargo. Requiere identidad/configuración y esquema igual que la API, más privilegios de sistema acotados para descubrir jobs.

## Idempotencia
initiate conserva fingerprint de todo el body y respuesta de firma; replay no consume cuota. client_upload_id pertenece a tenant/paciente; su reutilización con otro contenido o tras borrado falla.
refresh conserva respuesta por hash de Idempotency-Key; replay no incrementa contador. Si ese enlace expiró, usar una clave nueva para pedir un refresco nuevo. complete repetido no añade otro job.
Confirmación verifica hash de solicitud. Export combina tenant/paciente/clínico/clave, y rechaza cambios de parámetros o fuente. Índices y revisión transaccional resuelven unicidad; conflictos Mongo devuelven 409/503 y Retry-After para reintentar con la misma clave.
No hay migración automática de índices ni asignación automática de tenant.

## Límites y pendientes
No se intentó escanear malware real ni usar GCS. Casos de prueba usan blobs sintéticos, parsers reales y escáner explícitamente sustituido. Parseo acotado por bytes/páginas/píxeles no sustituye sandbox de CPU/memoria: debe aislarse el worker a nivel de contenedor y medir documentos hostiles.
La recuperación de trabajos terminales requiere procedimiento operativo revisado; no existe endpoint para reiniciar ilimitadamente un job fallido. No se ha implementado conciliación, retención o panel de trabajos.
