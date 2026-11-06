# Estado real del backend y siguientes pasos

Fecha: 2026-11-05. Rama `fix/wellq-backend-hardening`; HEAD `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e` con cambios locales. No se hicieron commit, push ni merge. No se modificó frontend ni se migraron bases existentes.

## Dictamen por nivel

| Nivel | Dictamen | Evidencia concreta | Pendiente |
|---|---|---|---|
| **A — Ejecutable localmente** | Sí, demostrado en el Docker aislado propio | API Python 3.11, Mongo 7 autenticado/replica set, gateway y dos workers arrancados; readiness y flujos HTTP reales | El entorno se detiene al cerrar esta tarea para conservar recursos. `Demo.ps1` lo reinicia; no es una API publicada al host. |
| **B — Flujo funcional demostrable** | Sí, con límites externos declarados | Cinco PDFs sintéticos subidos, confirmaciones, corrección clínica, review y permisos; JSON real; dos PDFs exportados/descargados, siete páginas finales renderizadas e inspeccionadas | Objetos/firma, IA y scanner son dobles explícitos. Escenario incompleto prueba rangos ausentes, no un E2E productivo de aprobación. |
| **C — Integración con React/Flutter** | Preparado para comenzar cliente/UX; integración de red/identidad aún parcial | 20 operaciones y OpenAPI conservados, ejemplos y demo reproducible, estados/nulos/permisos/idempotencia comprobados | Origen CORS/puerto libre localhost, gateway accesible, emisor y grants reales, Drift/background móvil. No se necesita esperar validación clínica para construir UI con fixtures. |
| **D — Producción clínica** | **No preparado** | Puertas de publicación y privacidad implementadas parcialmente; pruebas sintéticas verificables | Catálogo/aprobaciones, corpus/IA real, GCS/IAM/TLS, identidad, consentimiento/revocación, retención/operación/auditoría y staging móvil/cloud. |

## Resultados que no deben confundirse

La regresión de aplicación actual tiene **286 aprobadas y 209 omitidas**; las ocho nuevas de PDF forman parte de las 286. Se ejecutaron también ocho pruebas PDF separadas, sin sumarlas como cobertura adicional. La integración Docker se volvió a ejecutar y su XML actual está en [evidencias_demo/integration.xml](evidencias_demo/integration.xml); los resultados iniciales fallidos se preservan. Los **6/6 ClamAV anteriores** y la sonda de reinicio anterior siguen siendo evidencia de aquella tarea, no nuevos resultados de esta demo. El scanner de la demostración no es el daemon real.

Los **30 ports históricos** conservan clasificación: 28 Mongo/HTTP con dobles externos y dos funciones puras. Ocho históricos de título permanecen pendientes de adaptación; no se borraron ni se habilitó el guard global. Ningún número de pruebas equivale a un porcentaje de cumplimiento de los cinco documentos.

## Lo que ya puede verse

- [PDF principal, cuatro páginas (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion): diez marcadores, cuatro fechas, índice sintético, cuatro pilares, banderas, tablas, deltas y trazabilidad.
- [PDF incompleto, tres páginas (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion): valores confirmados, subscores nulos, exclusiones y ausencia de tendencia inventada.
- [Matriz de las cuatro fuentes distintas contenidas en cinco archivos](18_CUMPLIMIENTO_CINCO_ARCHIVOS_ORIGINALES.md), con implementación, prueba, evidencia y acción por obligación.
- [Inspección visual](19_AUDITORIA_VISUAL_PDF.md), incluidos defectos encontrados y limitaciones que no se maquillaron como cumplimiento.

## Roadmap verificable

| Orden | Trabajo | Criterio de cierre | Dependencia/responsable |
|---|---|---|---|
| 0 | Cerrar seis brechas HTTP documentales G01–G06 | Ownership de asociaciones, extensión/MIME, PATCH null/vacío/auditoría y reglas de review/revisor cubiertos por regresiones reales | Backend/plataforma; resolver modelo de case/appointment. Son pendientes de lógica, no simples bloqueos cloud. |
| 1 | Integración de desarrollo React/Flutter | Consumir API con RS256 test, carga de bytes, polling, revisión/confirmación, nulos, 403/409/422/429 y replay; revisión visual del flujo cliente | Desarrollo cliente y backend; puerto localhost libre y CORS revisados, sin usar 8000/27017 host |
| 2 | Congelar contratos originales frente a implementación | Decidir 422 estructurado, complete asíncrono, refresh/replay vencido y failed, scoring síncrono vs job, review separado de validación | Producto/arquitectura, registrar aprobación/versionado; no revertir seguridad arbitrariamente |
| 3 | Completar esquema y extracción | issuer/description/patient_stated, cotejo de identidad, imágenes textuales/DXA, cualitativos/ordinales, resolver nombres/sinónimos, fechas múltiples | Backend + catálogo + responsable clínico; pruebas específicas antes de ampliar |
| 4 | GCS de pruebas autorizado | PUT, hashes, promoción/generaciones/precondiciones, firma/expiración y fallos de IAM reales sin datos clínicos | Infraestructura e IAM; bucket exclusivo, sin recurrir a credenciales ajenas |
| 5 | Proveedor multimodal real y evaluación | Adaptador aprobado, contrato/region/no entrenamiento, preproceso y corpus anotado con métricas y alucinación bloqueante | Producto/protección de datos/QA; WQINT no sustituye el modelo |
| 6 | Catálogo y scoring clínicos | ~70 marcadores revisados, rangos por edad/sexo, pesos/umbrales firmados y versionados, comparación de distribuciones | Equipo clínico; mantener `CATALOG_CLINICALLY_APPROVED=false` hasta aprobación válida |
| 7 | Privacidad y consentimiento | Base de tratamiento/DPIA/retención aprobadas, revocación por paciente efectiva, acceso/portabilidad/purga compatible con legal hold, EXIF | Responsables de producto/protección de datos; propuestas documentales no son aprobación |
| 8 | Operación y escala | Cola/cloud o poller aprobado, jobs largos/renovación, backpressure/cuotas, scanner/firmas, alertas, conciliación, backup/restore y HA | Plataforma; replica set de un nodo y dos workers locales no certifican desastre |
| 9 | Auditoría comercial y seguridad | Perfil/tier y flags por módulo, RBAC jerárquico, quién/qué/cuándo/dónde/resultado homogéneo, persistencia especializada/WORM/firma/retención por plan | Plataforma/SaaS y privacidad; append-only de aplicación no basta para no repudio |
| 10 | Cierre de producto y staging | React accesible con i18n/light-dark; Flutter/Drift durable probado en iOS/Android; corpus/latencias y siete escenarios de carga completos | Clientes/QA/operación y revisiones clínica/legal/producto |

## Cambios acotados de esta intervención

Aplicación: solo `_build_lab_report_pdf` y la leyenda en `app/routes/clinical_tests.py`; ajustes de presentación verificados, sin variar JSON, fórmulas, pesos/rangos ni permisos. Ocho regresiones nuevas en `checks/test_pdf_presentation.py`. En `integration/`: demo HTTP, renderizador local, scripts de arranque/demo/apertura/tests y soporte de salida aislada; el port del PDF actualiza una tilde de la leyenda. `.dockerignore`/`.gitignore` excluyen artefactos sintéticos y entorno de renderizado. Documentos 17–21 y evidencias nuevas se agregan sin sustituir 01–16.

Las dependencias de aplicación y dev no se cambiaron. PDFium/Pillow de renderizado se instalaron únicamente en un venv desechable de integración, fuera de la imagen y Git. El generador sigue usando ReportLab ya instalado. Los cinco DOCX y las auditorías previas se conservan; el manifiesto de esta entrega registra hashes y cambios respecto del respaldo inicial.

Las sondas de cumplimiento encontraron además G01–G06: asociaciones sin verificación, extensión/MIME de metadatos, PATCH null/vacío, ausencia de evento al editar y revisión prematura/reemplazo de revisor sin auditoría. Se reproducen en el documento 18 y `sondas-brechas-http.json`; **no se contabilizan como aprobaciones ni se declaran cerradas por tener 59 tests verdes**. No impedían exportar y revisar los PDFs, por lo que no se amplió el alcance a una corrección general de rutas.

## Recursos al cierre

Solo se detienen servicios del proyecto `wellq-int-39706292db88`; volúmenes, DB sintética, red e imágenes se conservan. Los contenedores antiguos `wellq-api` y `wellq-mongodb`, `backend_mongodb_data`, sus datos/logs y OneDrive permanecen fuera del alcance. No se usó limpieza global ni se publicó Mongo al host. El estado final exacto está en el inventario de `evidencias_demo`.

El siguiente trabajo útil es integrar clientes sobre el contrato visible y resolver las decisiones bloqueantes de plataforma/proveedores en paralelo. No hace falta otra reescritura general para volver a generar y observar el PDF de demostración.
