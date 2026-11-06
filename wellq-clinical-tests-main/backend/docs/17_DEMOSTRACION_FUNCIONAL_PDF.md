# Demostración funcional y PDF descargado

Fecha: 2026-11-05. Rama `fix/wellq-backend-hardening`; HEAD `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e` con cambios locales. El resultado principal es un archivo generado por **POST /api/v1/patients/{patient_id}/lab-report/export**, descargado mediante su enlace autorizado. No es un PDF ilustrativo construido fuera de ese endpoint.

## Abrir el resultado

| Escenario | PDF local descargado | JSON exacto de GET lab-report | Páginas |
|---|---|---|---:|
| Cuatro mediciones, diez marcadores y puntuación sintética | [Reporte principal (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | [reporte-http.json (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | 4 |
| Una medición, rangos ausentes y subscores nulos | [Reporte incompleto (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | [JSON incompleto (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | 3 |

[Páginas PNG del principal](../integration/demo-output/pdf-pages/) y [del incompleto](../integration/demo-output/incompleto/pdf-pages/). Todos los archivos existen en Windows bajo `C:\Dev\wellq-capstone\wellq-clinical-tests-main\backend\integration\demo-output`. Esa carpeta está ignorada por Git y excluida de la imagen Docker. Contiene únicamente datos ficticios. [resultados-demo.json (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) registra IDs, tamaños, hashes, pruebas de acceso y diagnósticos de renderizado. La revisión visual efectiva está documentada en [19](19_AUDITORIA_VISUAL_PDF.md).

Versión final suficiente: **44,774 bytes**, SHA-256 `3663bbf93490cc0ae76d2fb3751c5ad8f319ceff629f24a32479ea01a7965aba`.
Versión final incompleta: **25,706 bytes**, SHA-256 `b5b9a0cd8babc0655adff26b4258f8bd8ffead7f21cb24384ce1c61b3d7636c4`.
Una repetición crea otro escenario y otros IDs/fechas/hashes; estas cifras identifican esta entrega, no una promesa de bytes idénticos entre exportaciones distintas.

## Ejecución y protección

Se verificaron branch, HEAD y status; no se descartaron modificaciones previas ni archivos untracked. Respaldo nuevo legible: `C:\Dev\wellq-demo-backups\20261105-130531\backend-before.zip` (**143 archivos backend**) más `baseline.json` (**249 hashes del repositorio**) y diff. Se comprobó legibilidad del respaldo de integración anterior y sus hashes de evidencias antes de arrancar. La verificación final compara esta línea base y registra el alcance en [evidencias_demo](evidencias_demo/).

Se reutilizó exclusivamente el proyecto **wellq-int-39706292db88**: `mongo-int`, `api-int`, `objects-int`, `worker-int` (dos procesos), `setup-int` y `provision-int`; el runner es temporal. Replica set `wellqIntRs`, DB `wellq_integration_39706292db88`, usuario de aplicación autenticado. Provisionamiento reconoció la DB propia ya preparada; no migró ni reinicializó datos. Ningún puerto host publicado; ningún acceso a datos/logs de `wellq-api` o `wellq-mongodb`, al volumen `backend_mongodb_data` ni a OneDrive. ClamAV no se inició en esta demostración.

Python Docker 3.11.18, MongoDB 7.0.43. Versiones efectivamente observadas: [runtime.json](evidencias_demo/runtime.json). API y worker son reales; **objetos/firma, extracción y escáner de la demo son dobles explícitos**. Los seis ClamAV aprobados pertenecen a la integración anterior, cuyo XML se conserva sin reejecutarlo ni presentarlo como parte de esta demo. El valor DTO `storage:gcs` no certifica GCS real: aquí entrega un enlace HMAC al gateway privado de pruebas.

## Recorrido HTTP real

1. Se crearon tenant, paciente y relación clínica exclusivamente ficticios en la DB propia. El runner emitió JWT RS256 efímeros con la autoridad test existente; ninguna clave/token se guardó en evidencias. Esta preparación de identidad no simula una ruta de login productiva.
2. Se construyeron PDFs **de entrada** legibles con la tabla de valores y una anotación de contenido `WQINT:` para el adaptador de pruebas. La anotación contiene el mismo JSON que representa la tabla; no es OCR ni visión. Se conservan como `entrada-01.pdf` y siguientes en cada escenario.
3. Por cada archivo se llamó initiate, PUT de bytes al gateway y complete; se consultó status hasta `local_file_can_be_deleted=true`. El worker verificó formato/parseo/tamaño/hash, escáner test y promoción privada. Complete respondió inicialmente sin permiso de borrar.
4. Se esperó la propuesta de extracción, comparando **los diez códigos y valores** con el contenido anotado. La propuesta conserva unidades, rangos, `provider_confidence`, confianza efectiva, validación, procedencia y versiones. Cambiar el nombre del archivo no participa en `AnnotatedPdfProvider.extract`; solo lee bytes del PDF.
5. El paciente confirmó por PATCH. En la última medición el clínico corrigió glucosa a **94 mg/dL** y validó por POST; GET posterior mostró `clinically_validated`. Se llamó también al endpoint PATCH review, comprobando `reviewed` y que la nota privada ficticia no apareciera en el detalle del paciente.
6. Se consultaron la serie de glucosa y GET lab-report con `include_series=true&include_snapshot=true`. La serie tiene cuatro mediciones en el escenario suficiente y una en el incompleto. Se guardó el cuerpo HTTP exacto, sin reconstruirlo a partir de llamadas internas.
7. El clínico invocó POST export con una clave estable para esa intención. Se exigió `ready`, enlace y expiración; se descargaron los bytes por HTTP, se verificó `%PDF-`, lectura estricta pypdf, páginas, tamaño y SHA-256 contra la respuesta. El paciente correcto aparece en el PDF y las notas privadas quedan fuera.
8. GET sin firma al mismo objeto respondió **403**; exportar como paciente respondió **403**. Repetir POST export con la misma clave mantuvo export_id, `replayed=true`, un registro y un evento de exportación en Mongo. No se confundió HTTP health con verificación de dependencias externas.
9. PDFium renderizó cada página a PNG a 120 dpi. Se revisaron todas las páginas visualmente; la geometría sola no se trató como aprobación visual.

Respuestas HTTP reales redactadas: [suficiente (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) e [incompleto (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion). Los PUT se registran con hash/tamaño, sin URL; GET lab-report exacto se guarda separado. Auditoría de acciones sin valores ni notas: archivos `auditoria-redactada.json`. Su selección de campos se declara: es un resumen para esta demo, no un nuevo sistema de auditoría.

## Qué demuestra cada escenario

**Suficiente:** diez marcadores del catálogo ilustrativo, cuatro fechas en 90 días, cuatro pilares, índice sintético **81.8**, tres banderas informativas, valores y unidades, deltas y corrección clínica; resumen de primera/última medición y trazabilidad. El catálogo permanece `CATALOG_CLINICALLY_APPROVED=false`. Los números aparecen por la excepción explícita **ENVIRONMENT=test**, con advertencia sintética en cada página; no se presentan como resultados clínicos validados.

**Incompleto:** diez valores confirmados, referencia documental explícitamente sin límites, cuatro pilares sin puntaje, `lab_index:null`, cobertura cero, estado indeterminado, subscores nulos y exclusiones `NO_REFERENCE_RANGE`. No convierte ausencias en puntajes cero. Una única medición no genera una tendencia ficticia.

**Límite de seguridad importante:** este segundo PDF prueba ausencia de cálculo justificable por rangos incompletos dentro de test; **no es un E2E de la puerta productiva de catálogo**. El adaptador de prueba está prohibido fuera de test y `publication_allowed` permite la excepción test. No se desactivó esa restricción ni se creó una API productiva falsa para satisfacer el escenario. Las pruebas F01 fuera de test cubren la política con dobles/estado persistido según su evidencia, pero un E2E productivo completo requiere IA/almacenamiento e identidad autorizados.

## Cambios y verificaciones

Cambios de aplicación acotados al generador `_build_lab_report_pdf` y su leyenda: aviso sintético por página, pie adaptable, etiquetas de pilares/confianza, formatos de rangos, motivos nulos, emisor/descripción cuando existen y explicación de serie insuficiente. No se alteraron fórmulas, pesos, catálogo, fechas clínicas, permisos, schemas ni rutas. Se añadieron ocho casos PDF con tabla de 100 filas, pie/IDs largos, límites unilaterales/nulos, tildes y procedencia test. La nueva prueba inicial falló por comparar una frase sin normalizar saltos de línea del PDF; se corrigió la aserción manteniendo el contenido exigido.

La primera regresión Docker tras el cambio de tildes dio 58/59: el port esperaba literalmente `diagnostico` sin tilde. Se actualizó **solo ese port** a `diagnóstico`, conservando la obligación de leyenda y los originales intactos. XML inicial conservado. Resultados finales de aplicación y Docker en `evidencias_demo`, con las ocho nuevas pruebas incluidas en las 286 de aplicación, no sumadas otra vez. No se sobrescribieron las auditorías anteriores.

Procedimiento completo y apertura local: [21_GUIA_DESARROLLADOR_DOCKER.md](21_GUIA_DESARROLLADOR_DOCKER.md). Matriz respecto de los cinco archivos: [18](18_CUMPLIMIENTO_CINCO_ARCHIVOS_ORIGINALES.md). Dictamen de niveles y pendientes: [20](20_ESTADO_REAL_BACKEND_Y_ROADMAP.md).
