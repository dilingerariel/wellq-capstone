# Inspección visual del PDF real

Fecha: 2026-11-05. Los PDFs revisados fueron generados por el endpoint de exportación de WellQ y descargados por HTTP del gateway autorizado. No se sustituyeron por documentos ilustrativos. La función de entrada genera únicamente el laboratorio ficticio que se sube; el reporte final lo produce `_build_lab_report_pdf` dentro de POST export.

## Método y archivos

Lectura estricta con pypdf, hash/tamaño contra la respuesta HTTP y **renderizado de todas las páginas a PNG a 120 dpi** con pypdfium2 5.14.0/PDFium. El renderizador se instaló en `integration/.runtime/render-venv` con Pillow 13.0.0, separado del entorno y requirements del backend. Se revisaron las imágenes efectivas con el visor local, incluyendo cabeceras, tablas y pies; no se infirió calidad visual de que pypdf leyera el archivo.

Herramienta de renderizado: [API oficial PDFium](https://pypdfium2.readthedocs.io/en/stable/python_api.html) y [paquete publicado](https://pypi.org/project/pypdfium2/5.14.0/). El diagnóstico geométrico recorre caracteres: margen horizontal mínimo 30 pt y contenido dentro de la página, con espacio reservado a aviso superior y pie. Los márgenes del cuerpo son 36 pt laterales, 40 superior y 64 inferior; el aviso está a 22 pt del borde superior y la leyenda a 14 del inferior. Geometría y lectura textual son controles complementarios a la inspección de imágenes.

| Documento final | Páginas | Diagnóstico geométrico | Inspección |
|---|---:|---|---|
| [Suficiente (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | 4 | 0 caracteres fuera del área admitida | Cuatro páginas PNG revisadas |
| [Incompleto (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | 3 | 0 caracteres fuera del área admitida | Tres páginas PNG revisadas |

Los hashes concretos figuran en documento 17 y resultados-demo.json. Las copias de páginas verificadas y sus hashes quedan registradas en `evidencias_demo/visual-review.json`; no se confunde una imagen de un intento anterior con la versión final.

## Resultado por página

| Página | Contenido y observación |
|---|---|
| [Suficiente 1 (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | Identificador paciente, fecha/tipo/examen y estados; índice sintético, cuatro pilares con cobertura/confianza, contribuciones cardio/articulación. Jerarquía y columnas legibles. Aviso test y pie completos. |
| [Suficiente 2 (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | Contribuciones músculo/hueso, tres banderas informativas y resultados óseos. Valores/unidades conservados. Estado bajo expresado como texto; sin dependencia exclusiva del color. |
| [Suficiente 3 (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | Hemograma, inflamación, lípidos, glucosa editada y renal. Nombres largos e IDs se ajustan a celdas, sin truncamiento; rango y fuente visibles. Deltas incluyen fecha previa. |
| [Suficiente 4 (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | Resumen de cuatro mediciones por marcador con unidades y advertencia de no interpretar tendencia; versiones, metadatos test y edición de glucosa. No es una gráfica longitudinal ni lista completa de puntos. Espacio inferior sin texto corresponde al fin del reporte, no a una página vacía. |
| [Incompleto 1 (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | Explicación de índice ausente, pilares sin puntaje y cobertura 0, resultados con “Sin rango” y motivo de subscore. No se imprimen puntajes cero inventados. |
| [Incompleto 2 (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | Resultados restantes y aviso de que una medición no permite inferir tendencia. Inicio de trazabilidad con catálogo/fórmula. Sin cortes de columnas ni solapamiento con pie. |
| [Incompleto 3 (artefacto local; ver regeneraci?n)](25_SANEAMIENTO_SEGURO_PUBLICACION.md#regeneracion) | Continúa trazabilidad: extracción/modelo/prompt, corrección clínica y diez exclusiones. Página corta por continuación de contenido; no está vacía accidentalmente. Pie y aviso test presentes. |

## Problemas encontrados y ajustes acotados

Primeros PDFs reales: cuatro páginas suficiente y dos incompleto, conservados en `demo-output/antes`. Se inspeccionaron esas seis imágenes antes de modificar código. No se observaron superposiciones ni columnas cortadas en esa muestra. Los problemas encontrados fueron de claridad y trazabilidad de presentación:

| Hallazgo | Cambio | Regresión/evidencia |
|---|---|---|
| Aviso sintético estaba en el título del examen de primera página, pero páginas aisladas podían confundirse con un reporte real | Aviso “DEMOSTRACIÓN SINTÉTICA — NO USO CLÍNICO” en cada página cuando entorno/procedencia es test | Test de banner por entorno/procedencia y siete páginas finales |
| Etiquetas de pilares/confianza/estado en códigos ingleses | Traducciones locales de presentación, sin cambiar enums del API ni datos clínicos | PDF final y tests; no constituye i18n completo |
| Rango ausente impreso como guiones; subscore mostraba código técnico partido | “Sin rango”, motivos legibles y formato unilateral Hasta/Desde sin inventar límite | Tres vectores de referencia y caso nulo |
| Sin score se afirmaba una causa posible como si fuese conocida | Mensaje que distingue índice sin cobertura y score global ausente sin motivo explícito | Test de ausencia, conserva valores y no inventa causa |
| Pie era una cadena de una línea, sin adaptación a IDs largos | Párrafo que se ajusta al ancho y reserva inferior; “Página” y “diagnóstico” con tilde | Tabla de 100 filas e IDs largos; revisión de pies |
| Emisor/descripción se omitían aunque existieran en header | Se imprimen si están disponibles | Fixture de regresión con laboratorio/descripcion; en demo API siguen ausentes por brecha del esquema |
| Una sola medición omitía explicación de evolución | Aviso explícito de insuficiencia sin inferir tendencia | Escenario incompleto y regresión |

La primera ejecución de las pruebas nuevas dio 7/8 porque una frase se dividía correctamente en dos líneas y la aserción exigía un string sin saltos. Se normalizó whitespace en esa comparación; no se retiró la obligación de contenido. La primera integración posterior dio 58/59 por la tilde de la leyenda; se actualizó el port a la leyenda correcta, sin editar la fuente histórica. Se conservan ambos XML iniciales y las corridas finales.

## Contraste con §9 del Maestro

| Elemento | Resultado visible | Límite o brecha |
|---|---|---|
| Cabecera | Paciente por ID, fecha de examen, tipo documental, estado de extracción y revisión, ID examen | No hay nombre/edad/sexo ni emisor extraído; no se inventaron. Descripción no llega desde provider actual. |
| Puntaje | Índice, cuatro pilares, cobertura, confianza, contribuciones; test marcado | Catálogo ilustrativo sin aprobación; resultados sintéticos. Caso incompleto mantiene nulos. |
| Banderas | Severidad, marcador, valor/unidad y mensaje coherentes con JSON | El JSON no contiene el límite superado como campo específico; el rango se puede consultar en resultados. No se añadió un umbral inventado. |
| Tabla | Nombres, valores/unidades, rango/fuente, estado textual, deltas, subscore o motivo, origen y “editado” | Sin iconografía/semáforo completo; códigos de panel/estado técnico todavía presentes en cabecera. No prometer i18n. |
| Evolución | Primera/última, cantidad, diferencia y unidad para ≥2; aviso para una | Sin gráfico/banda de referencia, sin render de toda serie de pilares/cobertura. Datos completos en JSON; portal pendiente. |
| Imagen | No hay datos de imagen en estos casos de laboratorio | Modelo canónico/provider no implementan modalidad/región/técnica/hallazgos/conclusión completos. Brecha explícita; no se fabricaron. |
| Trazabilidad | Modelo y versión test, prompt, catálogo, scoring, edición clínica, exclusiones y generación | PDF resume ediciones; historial detallado existe en backend, no es una transcripción íntegra de cada cambio. |
| Pie por página | Paciente, fecha generación, clínico, catálogo/fórmula, leyenda de resumen no diagnóstico y página | No es certificación de firma digital, PDF/A o PDF/UA. |
| Privacidad | Sin notas privadas, sin token ni URL firmada impresa; GET sin firma 403 y paciente export 403 | Control de gateway local, no IAM cloud. |

La presentación de la muestra es legible en A4 horizontal y en las imágenes a 120 dpi. Helvetica cuerpo 8 pt, tablas con texto ajustado y cabeceras repetibles; pie 7 pt. Las páginas no están vacías y no se observaron superposiciones. Esto es una revisión concreta de estas siete páginas y una regresión sintética de 100 filas, no una declaración universal de diseño “profesional”, accesibilidad o fidelidad sobre cualquier idioma/corpus clínico.

## Limitaciones de presentación conservadas

La trazabilidad todavía se imprime como JSON técnico, algunas etiquetas permanecen en códigos y la página final incompleta puede quedar poco ocupada. No bloquean lectura ni correspondencia con JSON, pero requieren diseño de producto antes de uso real. El cuerpo longitudinal es un resumen numérico, no una gráfica clínica. La tabla extensa se probó con cien filas en el generador; el escenario por HTTP usa el catálogo actual de diez marcadores y no se amplió artificialmente para afirmar una carga clínica de cien marcadores.
