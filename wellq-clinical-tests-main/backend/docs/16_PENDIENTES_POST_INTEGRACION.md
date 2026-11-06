# Pendientes posteriores a la integración

Fecha: 2026-11-05. Rama `fix/wellq-backend-hardening`; HEAD `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e` con cambios locales. Este documento actualiza el alcance de integración de 10/12; conserva esos informes históricos sin reescribirlos. Resultados ejecutados en [14](14_RESULTADOS_PRUEBAS_INTEGRACION.md).

## Dictamen diferenciado

| Escenario | Dictamen | Evidencia y límite |
|---|---|---|
| A. Aislamiento de aplicación | Verificado en el alcance de la suite | 278 aprobadas, 209 omitidas. Incluye F01–F07 y dos regresiones nuevas de scoring. Omisiones históricas no son aprobaciones. |
| B. Infraestructura Docker real | Verificado localmente para API/Mongo/worker; antivirus en cohorte separada | 59/59 de integración y 6/6 ClamAV. Python 3.11, Mongo 7 autenticado con replica set, índices/validadores, transacciones y conflictos, dos workers, recuperación de job tras reinicio. Dobles explícitos de objetos e IA. No es certificación cloud ni alta disponibilidad. |
| C. Integración del frontend | Preparado para desarrollo de UI/cliente y pruebas funcionales controladas | 20 operaciones, OpenAPI coincidente, ocho ejemplos HTTP y reglas de roles, nulos, errores y reintentos. Para un navegador faltan exposición deliberada de localhost/origen CORS y transferencia de objetos accesible. Identidad externa, GCS e IA reales siguen pendientes. No se modificó frontend. |
| D. Producción clínica | No preparado | Faltan aprobación clínica, proveedores/identidad reales autorizados, infraestructura cloud, privacidad y procedimientos operacionales. Números de pruebas sintéticas no levantan estos bloqueos. |

## Dependencias que siguen abiertas

| Prioridad | Pendiente | Criterio de cierre |
|---|---|---|
| Alta | GCS de pruebas separado y autorizado | Bucket/IAM/credenciales aprobados; PUT y lectura reales; generaciones/precondiciones, promoción, firma/expiración, errores de IAM y recuperación de firma. Evidencia sin secretos. No usar bucket clínico ni asumir que gateway local certifica GCS. |
| Alta | IA/OCR real y contrato de privacidad | Proveedor aprobado, región/retención/consentimiento, credenciales y adaptador concreto; PDFs/imágenes sintéticos y corpus autorizado; evaluación reproducible de clasificación, extracción, confianza, errores y latencia. |
| Alta | Catálogo y scoring aprobados | Revisión profesional del catálogo ampliado, unidades/rangos/edad/sexo/pesos y procedencia/versionado. Los diez marcadores actuales son ilustrativos; conservar la puerta de publicación y no activar aprobación por haber pasado tests. |
| Alta | Identidad de plataforma | Autoridad RS256 definitiva, distribución/rotación de claves, mapping de tenant/usuario/recurso, grants/capabilities y relaciones asistenciales. Las claves efímeras de `.runtime` no se trasladan a producción. |
| Alta | Migración de datos existentes | Backup verificado, mapping de tenant, revisión DBA y plan reversible aprobado. Esta tarea inicializó una base nueva; no migró ni recalculó bases anteriores. |
| Media | Navegador React y contratos extensibles | Cliente tipado, estados pendientes/nulos, reintentos con misma intención, validación visual de permisos, origen CORS y puerto localhost libre; concretar secciones dict extensibles de reportes cuando el producto lo requiera. |
| Media | Operación cloud y seguridad de transporte | TLS/red privada, secretos gestionados, observabilidad sin contenido clínico, límites efectivos, monitoreo de colas y scanner, backups/restauración/HA. Replica set de un nodo no prueba failover ni desastre. |
| Media | Jobs largos y efectos externos | Medir latencias reales frente al lease y timeout transaccional; diseñar heartbeat/renovación o etapas fuera de transacción si se justifica. Fencing protege escrituras finales; no evita cobros/llamadas externas repetidas. No hay garantía exactamente una vez sobre IA/GCS. |
| Media | Conciliación y retención | Procedimiento para objetos huérfanos, jobs terminales, resultados inciertos de commit/ack, revocación/retención/purga, recuperación operativa y scheduler de recomputación. No se añadió limpieza automática. |
| Media | Antivirus operativo | Actualización periódica de firmas, disponibilidad y alertas, límites/formatos y política de adjuntos; ampliar corpus inocuo. Esta corrida usa la base incluida en una imagen y `freshclam` deshabilitado para reproducirla. EICAR acredita una ruta de detección, no ausencia universal de malware. |
| Media | QA y mantenimiento | Adaptar ocho históricos de título y revisar warnings/deprecaciones. Ampliar pruebas de fallos de red/ack, carga, elecciones de replica set y proveedores reales. No contar pruebas repetidas como cobertura nueva. |

## Ocho históricos de clasificación por título

Se conservan intactos en `tests/test_extractor_rules.py`, con el guard histórico sin desactivar. Cuatro esperan carta clínica (seguimiento, carta médica, alta y epicrisis); cuatro esperan laboratorio (analítica, perfil lipídico, hemograma y título vacío). Permanecen **pendientes de adaptación**, sin aprobación para eliminarlos ni declarar obsoleto su contrato.

Propuesta: mantener esos títulos como metadatos y proporcionar un PDF sintético cuyo contenido declare `clinical_letter` o `blood_panel` mediante un proveedor explícito de pruebas. Comprobar documento no aplicable frente a panel extraíble y que cambiar el título sin cambiar contenido no cambia la clasificación. La infraestructura `AnnotatedPdfProvider` ya permite suministrar contenido determinista y el port de carta clínica comprueba `not_applicable`; esto no equivale a haber ejecutado los ocho casos. La selección/aprobación formal de su nuevo contrato sigue pendiente.

## Límites de lo demostrado

Los 30 casos previamente marcados como integración se mapearon individualmente. 28 se ejecutaron con Mongo/HTTP reales y dobles de objetos, IA y scanner; dos eran funciones puras y se reclasifican con transparencia. Sus variantes con GCS e IA reales permanecen sin certificar; no hay 30 E2E cloud aprobados. Las 171 recuperadas previamente no se vuelven a sumar a esta entrega ni a la suite habitual; aquella evidencia permanece en el documento 12.

F01 fuera de test se probó invocando la política real en el runner sobre registros de Mongo real. La API arrancó siempre en test; no se afirma haber hecho E2E de un despliegue productivo. F06 se verificó con fallos del firmante local, no un incidente real de GCS. La prueba lenta del proveedor pierde el lease bajo una escritura de otra conexión real y demuestra rollback y recuperación lógica; el proveedor y su demora son sintéticos.

Las firmas ClamAV de esta imagen están fechadas el 2026-11-01 (versión de daemon/DB registrada en evidencias). No se probó renovación de firmas. Los enlaces locales redactados no son enlaces entregables a pacientes y la red no está publicada al host.

## Conservación y siguiente uso

Solo se agregaron infraestructura/pruebas/documentación de integración y tres ajustes a archivos existentes: exclusiones en `.dockerignore`, precisión/orden estable en `app/services/scoring.py`, y dos regresiones en `checks/test_scoring.py`. Requirements, fórmulas/pesos/rangos del catálogo, contratos OpenAPI, frontend, guard histórico y documentos 01–12 se conservaron. El inventario y hashes verifican el alcance; el estado Git sigue sin commit/push/merge.

Al terminar se detienen únicamente servicios del proyecto `wellq-int-39706292db88`; volúmenes, DB sintética, red e imágenes quedan conservados. `Start.ps1` permite reanudar el entorno. No se ejecutó limpieza global ni se borraron recursos; los servicios antiguos no se detuvieron, reiniciaron ni consultaron para datos o logs.
