# Despliegue, configuración y migración

## Ruta actual hacia pacientes reales — Etapa 9B

**Base de evidencia:** `4f43a74688899e50f83678984e440d08859e1537`, rama
`feature/wellq-phase5-integration`. Consolidación documental: no se ejecutaron
pruebas, compilaciones, despliegues ni consultas a datos persistentes.
**Estado global: no autorizado todavía para recibir pacientes reales.**
Una implementación, inspección estática o prueba sintética no constituye
validación clínica, certificación legal ni verificación de un despliegue.
Los cinco Word originales no fueron consultados; los requisitos documentales
utilizados son los resúmenes y aclaraciones proporcionados por el responsable.

Estados: **implementado** = existe código; **parcial** = faltan capacidades o
acreditación; **bloqueado** = falta una dependencia/decisión; **no verificado** =
no existe evidencia suficiente en esta consolidación. Ninguno equivale a aprobado.
**P0** bloquea el uso real del alcance afectado; **P1** es preparación previa.

| Grupo / requisito | Estado | Evidencia disponible | Trabajo pendiente | Prioridad | Condición de aprobación |
|---|---|---|---|---|---|
| **A. Identidad y permisos productivos** | bloqueado | [RS256/configuración](../app/config.py), [roles y permisos](../app/dependencies/auth.py); barreras React y Flutter revisadas en 6A/9A. | Contrato autorizado del proveedor: adaptadores, claims, issuer/audience, claves y rotación, renovación/revocación/logout; separar la autoridad de integración. | P0 | Proveedor autorizado y pruebas de identidad inválida/expirada, paciente/tenant ajenos y relación clínica revocada sobre configuración candidata. La barrera contra identificadores sintéticos conocidos no acredita un proveedor. |
| **B. Carga de documentos reales desde Flutter** | parcial | [Carga actual](../../mobile/lib/data/uploads.dart) y [política sintética](../../mobile/lib/domain/sample_policy.dart); cola durable implementada. | Definir e implementar selección privada de archivos reales conforme al contrato existente, validaciones e integridad, preservando consentimiento de envío por operación. Sin habilitar pacientes durante desarrollo. | P0 móvil | Pruebas sintéticas aisladas de formatos/MIME/tamaño/hash, rechazo malicioso, recuperación e idempotencia; identidad autorizada y almacenamiento/escáner reales acreditados antes de uso real. |
| **C. Score y validación clínica** | bloqueado | [Motor/versionado](../app/services/scoring.py), [catálogo](../app/services/catalog.py), [reglas técnicas](07_SCORING_Y_REPRODUCIBILIDAD.md); diferencias documentadas en 5B–5D. | Resolver completitud y correspondencias del catálogo; aprobar reglas/parámetros y estrategia de nueva versión antes de corregir cobertura. No cambiar ni normalizar pesos por inferencia. | P0 si se ofrece Score | Aprobación clínica documentada de la versión, casos de referencia y regresión; snapshots históricos preservados. Mantener Score no aprobado y exportación productiva bloqueados mientras falte evidencia. |
| **D. Separación y saneamiento de datos sintéticos** | no verificado | [Aislamiento de integración](../integration/guard.py), proyectos/bases por ejecución; no se inspeccionaron contenidos persistentes ni Android. | Inventario autorizado de destinos; cuentas, bases, buckets y permisos exclusivos por entorno; política de retención/saneamiento posterior con respaldo. No borrar ahora. | P0 | Evidencia del destino productivo autorizado y ausencia de fixtures en él; pruebas de denegación de accesos entre entornos. Un nombre o volumen existente no acredita separación. |
| **E. Empaquetado React, Flutter y FastAPI** | parcial | [Asset Flutter](../../mobile/pubspec.yaml) incluye PDF sintético; [React](../../frontend/src/app/runtime.tsx) conserva importación demo; [Dockerfile](../Dockerfile) copia `app`, con [.dockerignore](../.dockerignore). Revisión estática 8B. | Preparar configuración productiva de assets sin romper desarrollo; verificar exclusión de chunks demo y herramientas/claves de pruebas. Configurar firma y distribución móvil autorizadas. | P0 | Inspección automatizada de APK/AAB, `dist` e imagen finales: sin documentos de prueba, claves privadas ni herramientas de integración; hashes/versiones reproducibles y firma verificada. No basta inspeccionar fuentes. |
| **F. Privacidad, cifrado, consentimiento, auditoría y retención** | no verificado | [Controles backend documentados](04_SEGURIDAD_BACKEND.md); auditoría e aislamiento implementados. No acreditan cumplimiento integral. | Precisar responsabilidades, consentimiento y finalidad; acceso mínimo, TLS, cifrado de almacenamiento y política de claves; retención/eliminación y trazabilidad sin secretos. Evaluar también almacenamiento móvil. | P0 | Revisión de privacidad/legal por responsables competentes y evidencia técnica de controles efectivos y ciclo de datos aprobado. Sin atribuir certificación legal o cifrado no demostrado. |
| **G. Respaldos, recuperación e incidentes** | no verificado | Existen antecedentes de respaldos sintéticos; no son evidencia de recuperación productiva. | Definir RPO/RTO, copias cifradas con acceso separado, procedimiento de restauración, responsables y respuesta/notificación ante incidentes. | P0 | Restauración ensayada en entorno aislado con integridad verificada y tiempos medidos frente a objetivos aprobados; procedimiento de incidentes revisado. |
| **H. E2E, seguridad y aceptación final** | bloqueado | [E2E entre clientes preparada](../../frontend/CROSS_CLIENT_E2E.md), pendiente por RAM; pruebas focalizadas previas no equivalen al recorrido completo. | Proveer capacidad aislada; ejecutar Flutter → FastAPI → confirmación → React → validación → lectura paciente, con el mismo ID; seguridad negativa, accesibilidad y regresión del candidato final. | P0 | Evidencia del recorrido real sintético sin duplicados ni accesos cruzados, pruebas de proveedores autorizados y aceptación de usuarios. Identificar fallos/omisiones; pruebas con dobles no certifican servicios reales. |
| **I. Despliegue controlado y autorización** | bloqueado | Plantillas y barreras de configuración; sin despliegue productivo acreditado. | Definir alcance inicial, responsables, secretos externos, infraestructura/TLS, supervisión, alertas, rollback y procedimiento de cambio. | P0 | Acta de autorización explícita del responsable con evidencias A–H aplicables, riesgos aceptados y criterios de parada. Publicar código en GitHub no autoriza recibir pacientes. |

### Orden mínimo por dependencias

1. **Ahora, sin proveedores ni mayor RAM:** acordar alcance/responsables y
   manifiesto de entornos sin secretos; especificar evidencias de privacidad,
   retención y recuperación; preparar el verificador de artefactos de E.
2. **Con contrato de identidad y decisiones de datos:** integrar A y diseñar la
   carga B conservando cola y permisos; preparar D en entornos independientes.
3. **En paralelo, fuera del desarrollo:** obtener validación clínica C y revisión
   de privacidad F. Si Score no está aprobado, debe permanecer deshabilitado y
   quedar excluido expresamente de cualquier alcance de uso autorizado.
4. **Con infraestructura/capacidad disponible:** acreditar almacenamiento,
   escaneo y demás proveedores necesarios; inspeccionar artefactos E, ensayar G
   y ejecutar H sobre el candidato final. No reutilizar el teléfono protegido.
5. **Solo después:** resolver bloqueos del alcance elegido y obtener I antes de
   habilitar datos reales. No fijar fechas ni asumir aprobaciones pendientes.

**Próxima tarea de programación propuesta, no ejecutada:** un verificador de
artefactos de solo lectura para ZIP APK/AAB, directorio React e inventario de
imagen exportada; debe señalar PDF sintético, claves privadas y herramientas de
integración, sin imprimir contenido sensible ni eliminar archivos. Probarlo con
fixtures temporales pequeñas. No requiere Docker, WSL, builds ni proveedores;
la verificación de artefactos reales quedará pendiente hasta generarlos.

## Referencia histórica de despliegue y migración

El contenido siguiente conserva los antecedentes de noviembre de 2026. Sus
resultados y estados pertenecen a aquellas intervenciones; **no acreditan la
configuración ni preparación productiva actual**. Para decisiones de uso real,
prevalece la matriz anterior y las evidencias que se obtengan posteriormente.

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
