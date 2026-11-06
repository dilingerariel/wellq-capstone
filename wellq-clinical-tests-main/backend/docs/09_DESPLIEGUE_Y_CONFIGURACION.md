# Despliegue, configuración y migración

> **Vigencia tras cierre focalizado F01-F07 (2026-11-05):** Docker no se utilizo en esta intervencion. Segun usuario, Desktop funciona, pero wellq-api/wellq-mongodb, volumen backend_mongodb_data y puertos8000/27017 son antiguos/ocupados: NO reutilizarlos para pruebas. Integracion posterior requiere proyecto/volumen/puertos aislados y provisionamiento revisado. [Detalle y evidencia](12_CIERRE_DEFECTOS_F01_F07.md).
> El contenido anterior al cierre se conserva a continuacion como referencia historica; esta nota y el documento12 prevalecen donde difieran.

**Fecha:** 2026-11-05 (America/Santiago). **Rama:** fix/wellq-backend-hardening. **Base:** fb8746cd42fe107bbda82dd92d3a4d11d545fd3e + cambios sin commit.

**Alcance:** backend; rutas de código relativas a wellq-clinical-tests-main/backend salvo indicación. **Método:** contraste estático, implementación y pruebas aisladas. **Límites:** sin servicios clínicos, datos reales, migraciones, despliegues ni validación clínica. No se modificó frontend.


## Estado
No se desplegó, inició servicios ni modificó una base existente. Docker no respondió; la imagen no fue construida. Configuraciones entregadas son preparativos sujetos a pruebas reales y revisión operativa.

## Requisitos
Autoridad RS256 aprobada, MongoDB replica set/sharded con autenticación, esquema tenant provisionado, bucket GCS con controles privados, escáner ClamAV y proceso worker administrado. IA y scoring se habilitan solo tras las aprobaciones correspondientes.
La API arranca sin sembrar catálogo ni crear índices. Exige autoridad configurada y nombres/claves/unicidad esperados en índices. Mongo standalone se rechaza.

## Variables
| Variable | Finalidad |
|---|---|
| ENVIRONMENT | development, test o production; no convierte datos sintéticos en producción |
| WELLQ_DEBUG | Alias explícito para evitar colisión con DEBUG del host |
| MONGODB_URI / MONGODB_DB | Conexión/DB; nunca escribir URI en logs o documentación de credenciales |
| JWT_PUBLIC_KEY / JWT_ISSUER / JWT_AUDIENCE | Frontera externa confiable; clave pública PEM RSA >=2048 bits |
| JWT_MAX_LIFETIME_SECONDS | Máximo aceptado, por defecto 3600 |
| CORS_ORIGINS | Lista JSON de orígenes permitidos; sin wildcard |
| GCS_PROJECT_ID / GCS_BUCKET_NAME / GCS_CREDENTIALS_PATH | GCS real, credenciales por archivo o ADC; sin fallback |
| CLAMAV_HOST / CLAMAV_PORT | Servicio de escaneo autorizado |
| MAX_CLINICAL_FILE_BYTES / MAX_DOCUMENT_PAGES / MAX_IMAGE_PIXELS | Límites de contenido |
| JOB_LEASE_SECONDS / JOB_MAX_ATTEMPTS | Lease/reintentos del worker |
| MAX_REQUESTS_PER_MINUTE | Límite compartido por tenant y sujeto |
| AI_PROVIDER_APPROVED | Aprobación externa; además requiere adaptador concreto, hoy ausente |
| CATALOG_CLINICALLY_APPROVED | Atestación de aprobación clínica; false por defecto |

.env.example contiene espacios vacíos y flags deshabilitados, sin credenciales utilizables. No guardar secretos reales en Git. Debe suministrarse el PEM y demás valores por configuración segura.

## Contenedores
Dockerfile usa usuario 10001, sin reload ni bind mount de código. No copia los estáticos demo al build por .dockerignore; no se editó el HTML. Uvicorn desactiva access-log.
Compose retira credenciales predeterminadas, exposición de Mongo al host y scripts de índices al inicio. Requiere variables de administración/keyfile proporcionadas externamente; replica set y permisos de keyfile deben provisionarse. API expone solo loopback en esta plantilla y usa filesystem read_only/tmpfs/cap_drop.
No se afirma que el template constituya un despliegue productivo completo: TLS, secretos, segmentación, rotación, backups, supervisión, roles DB mínimos y retención siguen pendientes.
docker-compose.test.yml solo debe usarse bajo otro proyecto y volúmenes desechables, nunca superpuesto al proyecto clínico. No fue ejecutado.

## Nuevo esquema vacío
database.init_indexes(db) solo está preparado para una DB vacía y rechaza datos existentes. Crea validación client_id, índices compuestos, series y TTL de límites. No está conectado al startup. Su ejecución administrativa debe autorizarse y verificarse en entorno aislado antes de cualquier despliegue.
Colecciones nuevas/adaptadas: clinical_tests, clinical_test_extractions, clinical_markers, marker_catalog, score_snapshots, patient_access, lab_report_exports, audit_events, audit_logs, request_limits y clinical_result_history.

## Plan de migración legacy: preparado, NO ejecutado
1. **Objetivo:** incorporar pertenencia real a organizaciones y unicidad compuesta sin perder historia.
2. **Datos afectados:** todas las colecciones clínicas/acceso/export/auditoría e índices globales anteriores; identificar huérfanos y referencias cruzadas.
3. **Precondiciones:** Documento Maestro, mapping autorizado registro->client_id, DBA/privacidad, versión objetivo, ventana operativa y replica set verificado. No hay mapping disponible.
4. **Riesgos:** asignación incorrecta, duplicados, pérdida de relación clínica, referencias/snapshots obsoletos y clientes incompatibles. Los datos sin mapping deben quedar aislados para revisión.
5. **Respaldo:** snapshot/backup consistente, inventario de índices/validadores y prueba de restauración en entorno separado, con acceso y retención revisados.
6. **Dry-run:** generar conteos y manifiesto de cambios sin escrituras; comprobar que todas las referencias comparten tenant, que no haya duplicados ni solicitudes de asignación por defecto. No se entregó un script de aplicación arbitraria sin mapping.
7. **Aplicación y validación posterior:** solo con autorización separada, aplicar por lotes trazables, crear índices revisados, validar segregación, conteos, hashes, relaciones, casos HTTP y rollback transaccional. Recalcular historia es otra decisión, no parte implícita de migrar tenant.
8. **Reversión:** conservar mapping antes/después, backups y código anterior; restaurar en entorno controlado o aplicar inversa solo si no hay escrituras nuevas incompatibles. No mezclar código antiguo con esquema nuevo sin análisis.

## Referencias primarias consultadas
[Transacciones MongoDB](https://www.mongodb.com/docs/manual/core/transactions/), [precondiciones GCS](https://docs.cloud.google.com/storage/docs/request-preconditions), [verificación de claims PyJWT](https://pyjwt.readthedocs.io/en/latest/api.html). Se usaron para decisiones técnicas; no prueban configuración o cumplimiento de este despliegue.
