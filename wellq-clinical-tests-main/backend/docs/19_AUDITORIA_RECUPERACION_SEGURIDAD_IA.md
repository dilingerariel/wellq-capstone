# Auditoría y recuperación: seguridad, extracción y puntuación

Fecha de auditoría: 2026-11-18. Alcance: rama `main`, backend FastAPI, configuración Docker/Vercel, historial Git y pruebas aisladas. No se consultaron ni escribieron credenciales.

## A. Estado previo

- La validación de carga comprueba tamaño, SHA-256, MIME detectado, estructura del PDF y límites de páginas/píxeles. El worker de carga ya invoca el escáner ClamAV mediante `INSTREAM` y deja los trabajos sin aprobar cuando el servicio no responde.
- La configuración Docker de backend no iniciaba ClamAV ni el worker persistente. El worker ya existe en `app/workers/processing.py` y usa trabajos/leases persistidos en MongoDB.
- La ruta de almacenamiento Mongo de la demo acepta únicamente el PDF sintético fijo y marca ClamAV como `not_applicable`. No es apta para archivos reales ni para validación de antivirus.
- El motor de extracción está implementado con esquemas estrictos, normalización, confianza, estados, confirmación humana, reintentos y auditoría. El despliegue no tiene un adaptador real: `ExtractionEngine.provider` queda vacío y `AI_PROVIDER_APPROVED` vale `false`.
- La rama histórica `ariel-componente-f` declaraba `gemini-1.5-pro`, pero generaba valores prefijados usando el título y no leía el PDF ni invocaba Gemini. No es una integración recuperable de IA.
- `integration/AnnotatedPdfProvider` extrae un bloque `WQINT` de PDFs sintéticos y tiene `is_test=True`; es un doble de integración, no IA.
- Hay motor de puntuación, historial y exportación de informes. La publicación fuera de pruebas requiere aprobación y catálogo completo; el catálogo actual declara `definition_complete = false`. No debe activarse puntuación clínica con un simple cambio de variable.
- La arquitectura multi-tenant, autenticación, relación asistencial y pruebas entre clínicas se conservan sin cambios funcionales.

## B. Cambios realizados

- `app/services/file_validation.py`: ClamAV escanea el PDF y cada adjunto incrustado por separado. El tamaño agregado de adjuntos queda limitado; si no se pueden enumerar de forma segura, el documento se rechaza.
- `app/workers/processing.py`: el worker usa el escaneo por documento antes de promover el archivo o encolar extracción.
- `docker-compose.yml`: se agregaron servicios persistentes `clamav` y `worker`; el worker apunta a ClamAV por la red privada de Compose y mantiene su cola MongoDB.
- `checks/test_processing.py`: prueba aislada que verifica que un EICAR en un adjunto PDF llega por separado al escáner.
- Se actualizaron pruebas que dependían de endpoints demo legacy apagados por defecto, del número viejo de rutas OpenAPI o de una aprobación de catálogo incompleta.
- No se añadieron credenciales, adaptadores de IA ficticios ni cambios a la relación clínica/multi-tenant.

## C. Estado funcional resultante

- El flujo normal de carga conserva el rechazo de archivos infectados y el bloqueo/reintento cuando ClamAV no está disponible. Ahora también inspecciona adjuntos PDF.
- Docker Compose declara API, MongoDB, ClamAV y worker, pero esta configuración no fue iniciada ni validada en Docker en esta sesión. Requiere una URI Mongo autenticada de replica set, identidad RS256, índices/esquema provisionados y configuración GCS válidas.
- El flujo demo de Atlas continúa siendo exclusivamente sintético y omite antivirus y extracción de IA.
- La extracción productiva sigue bloqueada hasta integrar y aprobar un proveedor multimodal real. El motor existente no inventa resultados si no hay provider.
- Confirmación humana, estados, normalización, puntuación y reportería siguen conectados en el backend; la publicación de score clínico permanece cerrada mientras el catálogo no esté completo/aprobado.
- Vercel puede servir el portal y funciones HTTP, pero no inicia por sí mismo el bucle persistente de `app.workers.processing`. El worker y ClamAV deben ejecutarse en un host de contenedores persistente, con acceso seguro a Mongo y al almacenamiento privado.

## D. Evidencia ejecutada

- `python -m pytest -q checks --tb=short`: **499 passed, 7 subtests passed**. Las pruebas usan `mongomock`, proveedor sintético de tests y dobles; no prueban Atlas, GCS, un clamd real ni inferencia externa.
- El test nuevo confirma que el worker entrega individualmente los adjuntos PDF al escáner (doble de prueba).
- No se ejecutó el conjunto `integration/av_checks.py` con ClamAV real: Docker CLI está instalado, pero esta sesión no tiene permiso para conectar con el pipe `dockerDesktopLinuxEngine`. No se afirma que EICAR haya sido bloqueado por un servicio ClamAV operativo tras el cambio.
- No se ejecutó inferencia con proveedor real: no existe adaptador productivo ni se configuraron credenciales/aprobación.

## E. Pendientes que bloquean aceptación integral

1. El equipo debe elegir y aprobar el proveedor multimodal permitido para los PDFs médicos, y acordar el tratamiento/consentimiento de datos. Su API key se configura como secreto en el host de ejecución; no se pega en chat ni se versiona.
2. Implementar el adaptador para ese proveedor y desplegar API + worker persistente. Mantener estados terminales/reintentos y permitir consulta del error sin perder el archivo seguro.
3. Iniciar ClamAV con firmas actualizadas y ejecutar las pruebas de archivo limpio, EICAR directo, EICAR dentro de PDF, servicio indisponible y worker real. Verificar el rechazo antes de extracción.
4. Reemplazar el bypass de almacenamiento de demo por bucket privado + ClamAV antes de aceptar documentos que no sean el PDF sintético fijo.
5. Completar la aprobación clínica del catálogo y sus parámetros antes de publicar scores. Los scores no son diagnóstico.
6. Desplegar API/worker/ClamAV en infraestructura persistente configurada con la base, identidad, redes, secretos, almacenamiento y respaldos apropiados. El proyecto Vercel actual no constituye esa infraestructura.

No se hizo commit, push ni despliegue en esta recuperación.

## Actualización: integración Gemini para la demo sintética

- Se añadió `app/services/gemini_provider.py`, que envía el PDF al endpoint oficial Gemini `generateContent` y exige JSON estructurado antes de validar la respuesta con `ProviderOutput`. El prompt prohíbe diagnósticos, inferencias y devolver identificadores personales; la cantidad de páginas se obtiene localmente del PDF.
- El adaptador queda limitado en código al PDF sintético fijo de presentación. No puede procesar archivos clínicos reales. Para documentos reales se requiere una integración Vertex AI separada y aprobada, junto con los términos de procesamiento de datos y un worker persistente.
- En el flujo Vercel de demo, la carga encola la extracción solo si el paciente dio consentimiento y existe un proveedor habilitado. La solicitud procesa un trabajo de la cola; infraestructura productiva continúa requiriendo el worker persistente.
- El adaptador está apagado por defecto. El repositorio local no tiene `GEMINI_API_KEY`; no se hizo llamada real al modelo. Para habilitar la demo, configurar `AI_PROVIDER=gemini_api`, `GEMINI_API_KEY` como secreto, `GEMINI_MODEL_ID=gemini-3.8-flash` y `AI_PROVIDER_APPROVED=true` en el proyecto API de Vercel, luego desplegar.

## Seguimiento en `feature/ai-extraction-module` (2026-11-23)

- Se centralizó la programación serverless en `app/services/demo_ai.py`: solo agenda documentos con consentimiento, estado verificado y hash/tamaño exactos del PDF sintético. La solicitud de reproceso también despierta el worker; repetir una solicitud idempotente pendiente vuelve a intentar programarla.
- El worker admite un `clinical_test_id` opcional y la ejecución desde Vercel queda acotada al documento solicitado, evitando consumir por accidente otro trabajo de MongoDB.
- `vercel.json` fija 60 segundos para el handler Python. Vercel sigue sin alojar el bucle persistente; producción necesita un worker siempre activo.
- El esquema permite unidad vacía cuando el PDF no imprime una, sin inferirla.
- Verificación local: `python -m pytest -q checks --tb=short` terminó con **503 passed, 7 subtests passed**. Son pruebas aisladas; esta ejecución no invocó Gemini ni validó las credenciales, cuota o respuesta del servicio desplegado.
