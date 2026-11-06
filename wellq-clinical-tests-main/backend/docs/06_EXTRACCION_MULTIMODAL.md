# Extracción multimodal

> **Vigencia tras cierre focalizado F01-F07 (2026-11-05):** Se conservan confianza declarada (provider_confidence), validacion y confianza efectiva; se guarda salida original en proposal.provider_output. Rango/estado comparten resolucion; se validan fechas con reloj UTC inyectable. No se agrego proveedor. [Detalle y evidencia](12_CIERRE_DEFECTOS_F01_F07.md).
> El contenido anterior al cierre se conserva a continuacion como referencia historica; esta nota y el documento12 prevalecen donde difieran.

**Fecha:** 2026-11-05 (America/Santiago). **Rama:** fix/wellq-backend-hardening. **Base:** fb8746cd42fe107bbda82dd92d3a4d11d545fd3e + cambios sin commit.

**Alcance:** backend; rutas de código relativas a wellq-clinical-tests-main/backend salvo indicación. **Método:** contraste estático, implementación y pruebas aisladas. **Límites:** sin servicios clínicos, datos reales, migraciones, despliegues ni validación clínica. No se modificó frontend.


## Qué cambió
El pipeline anterior generaba resultados fijos a partir del título. Ese camino fue retirado. No se usa model_id como prueba de inferencia. app/services/extractor.py contiene MultimodalProvider, ExtractionEngine y contratos ProviderOutput/ProviderPanel/ProviderMarker/ProviderConfidence.

## Frontera productiva
Sin proveedor configurado o AI_PROVIDER_APPROVED, ExtractionUnavailable conserva el trabajo seguro y explícito. Un proveedor is_test=true se rechaza fuera de ENVIRONMENT=test. Los únicos resultados sintéticos están en checks, no en adaptadores productivos ni fallbacks.
No se seleccionó proveedor ni se mandó documento alguno a un servicio externo. Falta contrato de tratamiento, aprobación de privacidad, credenciales y evaluación de proveedor. La integración real permanece bloqueada.

## Pipeline preparado
1. Obtiene examen dentro del tenant, exige ready_for_review, verified_at y consentimiento IA.
2. Lee generación privada verificada desde GCS; no usa el título como contenido.
3. HEIC se convierte a JPEG. PDF se entrega nativamente al futuro adaptador; no hay OCR independiente.
4. Invoca provider.extract(bytes, mime_type), con modelo/versión declarados por adaptador.
5. Valida schema_version=1.0, tipos, campos, límites, confianza obligatoria por campo y procedencia página/evidence.
6. Rechaza duplicados y fechas/páginas inválidas. Normaliza valores/unidades; conserva no mapeados/implausibles con banderas, sin inventar valores ausentes.
7. Usa referencia del documento cuando su unidad puede convertirse inequívocamente; si no, señala limitación.
8. Conserva proposal original y metadata de modelo/prompt/catálogo/generación. awaiting_confirmation nunca significa verificación clínica.
9. Clasificaciones unreadable/other producen estados correspondientes. El proveedor debe determinar la clasificación desde contenido.

## Identidad y revisión
No existe registro maestro de nombres de paciente accesible en el módulo. Se emite identity_unverified y se exige document_edits.identity_confirmed=true antes de confirmar. No se fabrica identity_match. Comparación automática de identidad requiere integrar la fuente de identidad de pacientes.
Marcadores low_confidence exigen acknowledged_marker_codes explícitos. La política de umbral del código es 0,9 para revisión, no una métrica de precisión clínica validada.

## Esquema y límites
Ver OpenAPI para DTO público y código de ProviderOutput para el contrato interno del adaptador. El Documento Maestro íntegro no estuvo disponible: se preservaron contratos conocidos y se evitó inventar campos clínicos/rangos de catálogo.
No se implementó rasterización PDF ni sandbox específico de inferencia. Un proveedor que no soporte PDF nativo necesitará conversión acotada y pruebas antes de habilitarse. No hay OCR separado.
Evidence no vacía y JSON válido no prueban que una respuesta esté respaldada por el documento: el problema semántico de alucinación sigue sujeto a evaluación y revisión humana. No se afirma detección universal de respuestas inventadas.

## Evaluación
services/evaluation.py calcula cobertura de marcadores, exactitud de valor/unidad y proporción de propuestas sin correspondencia, con denominadores explícitos; cero observaciones produce None. No ejecuta IA ni lleva corpus clínico.
Solo se probó mecánica con anotaciones sintéticas identificadas como tales. No hay corpus anonimizado autorizado ni mediciones de clasificación, rangos, latencia o precisión/alucinación frente a umbrales del Documento Maestro. Esas métricas y la aceptación del proveedor quedan pendientes.
