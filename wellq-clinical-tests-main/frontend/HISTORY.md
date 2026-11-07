# Historial, tendencias y reportes clínicos

Las rutas `/history` y `/reports` requieren modo API, identidad clínica verificada, `clinical:read` y un paciente autorizado. El servidor conserva la autoridad sobre tenant y relación clínica. Demo muestra explícitamente la necesidad de una sesión real; no fabrica historiales, scores ni PDFs. Los enlaces aparecen en la navegación y el dashboard clínico.

## Contratos existentes

| Operación                                   | Uso y límites                                                                                                                                                                    |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET `/patients/{id}/markers`                | `marker_codes` obligatorio; selección de un marcador, fechas `from`/`to` y `only_confirmed=true`. Mediciones cronológicas, procedencia, edición y confirmación.                  |
| GET `/patients/{id}/lab-score?history=true` | Solo snapshots vigentes publicados por el servidor. `404 NO_SCORE_AVAILABLE` distingue cobertura insuficiente y ausencia de exámenes confirmados. No genera ni recalcula scores. |
| GET `/patients/{id}/lab-report`             | Ventana de 1–60 meses o examen seleccionado, `include_series=true`, `include_snapshot=true`. Resultados, referencias, exclusiones y metadatos autorizados.                       |
| POST `/patients/{id}/lab-report/export`     | Mismos filtros, `Idempotency-Key`, `reports:export` y capacidad `report_export`. PDF oficial del backend; `ready` o `download_pending`.                                          |

El catálogo enumera marcadores admitidos, no inventaría los disponibles para un paciente. La selección combina ese catálogo con los códigos recibidos en el reporte y consulta sus observaciones reales. Los contadores describen únicamente la respuesta recibida. El contrato no expone notas privadas de revisión ni un inventario histórico completo por paciente; no se inventan esos campos. El score del reporte pertenece al paciente incluso al filtrar un examen.

Los scores nulos permanecen ausentes; cero se conserva. Se muestran catálogo, fórmula, cobertura, confianza, estado y snapshots recibidos, sin cálculos clínicos en React. Los números de catálogos no aprobados se ocultan. El índice del reporte exige además un snapshot aprobado coincidente entregado por `/lab-score`. El entorno aislado mantiene `CATALOG_CLINICALLY_APPROVED=false`: comprueba `404` antes de validar y un snapshot sintético no aprobado después. El backend permite esos snapshots en `ENVIRONMENT=test`; el frontend oculta sus números. Los estados positivos aprobados son fixtures de presentación, sin validación clínica.

## Gráficos y accesibilidad

Recharts 3.10.1, compatible con React 19, se carga con el módulo clínico. Se utiliza su [capa accesible oficial](https://github.com/recharts/recharts/blob/main/storybook/stories/API/Accessibility.mdx), tooltip con teclado, leyenda, selección explícita de observación y tabla HTML alternativa. Cada unidad tiene un gráfico independiente; faltantes producen huecos, sin mediciones intermedias. Las líneas unen observaciones registradas y no representan diagnósticos ni estimaciones.

Una banda exige referencia coherente en todos los puntos, misma unidad y límites, procedente del documento o de un catálogo aprobado. Las referencias variables permanecen en la tabla. Observaciones sin unidad, fecha válida o número no se grafican, pero conservan sus detalles tabulados. Tablas se reorganizan como tarjetas móviles, sin ocultar procedencia ni unidades. Español/inglés, temas claro/oscuro y controles táctiles se integran con las preferencias existentes.

## Exportación y continuidad

Generar y descargar son acciones separadas. Se revalida identidad y fuente antes/después de generar y antes de descargar. Tras recibir y verificar los bytes, se repite explícitamente el POST con la misma clave/cuerpo: el servidor compara su fuente completa con la del PDF persistido. Solo se guardan bytes si devuelve `replayed=true`, el mismo paciente, exportación, tamaño y SHA-256. No se crea una segunda exportación ni auditoría. Un fallo o `409 EXPORT_SOURCE_CHANGED` descarta los bytes antes de entregarlos al navegador. Este control cubre cambios durante la transferencia y la secuencia A → B → A alrededor de la generación, que las lecturas anteriores no detectaban. No hay replay automático al reconectar. Una URL nula nunca habilita descarga; el último POST valida bytes ya recibidos y no inicia otra descarga.

GET incorpora `source_version` opaca (`rpt1:revision:sha256`), independiente de `generated_at` y de las proyecciones `include_series`/`include_snapshot`. POST exige `expected_source_version`, conservada con los filtros y la clave para cada reintento. Una solicitud antigua sin versión recibe `428 EXPORT_VERSION_REQUIRED`; formato inválido, `422`; fuente obsoleta, `409 EXPORT_SOURCE_CHANGED`. No hay fallback para clientes antiguos. Una respuesta lista incluye esa misma versión y `verified_at`; React rechaza pruebas de otra versión antes de habilitar o guardar bytes.

El backend reserva `pending` en una transacción corta. Genera ReportLab y carga un objeto privado fuera de la transacción, confirma `committed` condicionalmente y vuelve a comprobar la fuente después de firmar, antes de entregar el enlace. Cada comprobación escribe un contador mediante CAS en el documento de revisión: una lectura snapshot por sí sola no bastaría. Las mutaciones de fuentes mediante `TenantDatabase` incrementan esa revisión e invalidan exportaciones en la misma transacción. El documento no tiene TTL y reutiliza el índice único existente `(client_id,key)`. El ámbito de invalidación es todo el tenant; una modificación de otro paciente puede exigir refrescar conservadoramente. Usuarios/roles, algoritmos y valores clínicos no cambian. [MongoDB documenta por qué una lectura snapshot requiere una escritura para excluir fuentes modificadas concurrentemente](https://www.mongodb.com/docs/manual/core/transactions-production-consideration/).

El mismo intento pendiente devuelve `409 EXPORT_IN_PROGRESS` y `Retry-After`. Un intento fallido o con lease vencido devuelve `EXPORT_ATTEMPT_FAILED`/`EXPORT_ATTEMPT_EXPIRED`; requiere refrescar y una nueva solicitud explícita, sin recargar automáticamente el objeto. Un resultado de transporte incierto conserva la clave en RAM para comprobarlo manualmente. Una caída del firmador conserva el PDF confirmado (`download_pending`) y permite renovar con la misma clave. Las exportaciones anteriores al contrato carecen de versión y no se reutilizan. Los fallos quedan auditados sin valores clínicos ni enlaces. Los objetos cargados pero no publicados permanecen privados, referenciados por el intento; no se borran ni se consideran revertidos por MongoDB. Su reconciliación/retención exige una política y revisión operativa futura.

El PDF es una instantánea fechada con versión, no una garantía de vigencia continua después de `verified_at`. Un cambio posterior invalida el registro y el replay, pero no revoca una URL firmada ya entregada ni un archivo ya descargado. Escrituras administrativas externas que eludan `TenantDatabase`, cambios de política entre procesos y revocación externa de sesiones requieren gobierno/control propio; este protocolo no los certifica. **Se conserva el bloqueo productivo**: solo desarrollo (`import.meta.env.DEV`) permite exportar. Los builds productivos bloquean botones y controlador incluso con grants. Esto no protege por sí solo el endpoint FastAPI ni autoriza desplegarlo: antes de habilitarlo se requieren decisión explícita, integración real de identidad/almacenamiento, política de vigencia/retención y validación del conjunto de escritores y procesos productivos.

La descarga no envía bearer al almacenamiento; usa petición anónima sin caché, cookies, redirecciones ni referrer. Antes de guardar verifica tamaño (máximo 50 MB), cabecera PDF y SHA-256 entregados por el backend. Los enlaces HTTPS firmados permanecen en RAM; HTTP solo se admite en loopback de desarrollo. Una firma expirada requiere renovación explícita, conservando la clave. El blob temporal se revoca tras iniciar la descarga.

Sin red, los filtros y respuestas ya recibidas permanecen en memoria de la sesión con aviso; no se generan ni descargan reportes. Cambios de paciente, identidad, permisos, expiración o logout cancelan consultas y limpian datos y exportaciones privadas. Respuestas tardías no repueblan otro contexto. Recargar o actualizar manualmente descarta el plan de exportación en RAM; si una operación quedó incierta, puede haber finalizado en el servidor y una nueva generación explícita usaría otra clave. No hay persistencia durable de recuperación.

El service worker no se amplía: no almacena respuestas clínicas, PDF, tokens ni URLs privadas. El archivo que el usuario descarga queda bajo la política de almacenamiento y privacidad de su equipo.

## Verificación reproducible y alcance

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run format:check
npm.cmd test
npm.cmd run build
npm.cmd run test:browser
npm.cmd run test:live
npm.cmd run test:release
```

Vitest verifica contratos, separación de unidades/referencias, scores ausentes/cero, cambios de procedencia, cancelación y exportación. Playwright con respuestas interceptadas cubre diez anchos de 320 a 1920 px, ambas vistas, Axe, teclado/tacto, orientación horizontal, reflow equivalente al 200 %, idiomas, temas, offline, cambios de sesión/paciente, fallos de almacenamiento, expiración e idempotencia.

`test:live` utiliza FastAPI/MongoDB aislados y datos sintéticos, sin interceptar las respuestas del navegador. Amplía el flujo existente con lectura del historial/reporte, ausencia real de score y exportación/descarga oficial. Comprueba autorizaciones negativas, un único registro/auditoría por clave pese a la revalidación, bytes ReportLab con tamaño/SHA-256 y páginas PDF, firmador temporalmente indisponible con restauración, firma expirada y fuente cambiada. Una prueba adicional modifica temporalmente metadatos de una extracción sintética, genera PDF B, restaura exactamente la fuente A y verifica `409` al repetir la clave: el hash completo rechaza el PDF aunque las lecturas A coincidan. No modifica backend ni documentos; conserva detenidos los contenedores propios de prueba y no interviene MongoDB de desarrollo. Identidad RS256, IA, escáner y almacenamiento local son dobles explícitos: estas pruebas no certifican SSO, GCS o validación clínica productivos.

`test:live` añade `scripts/atomic_pdf_live.py`: otro servidor ASGI exclusivamente loopback, tenant sintético independiente, MongoDB real y escritor clínico HTTP en un proceso separado. Barreras de prueba externas al producto detienen generación, carga, firma y las escrituras condicionales de reserva/publicación. Comprueba misma clave concurrente, conflicto snapshot en Mongo, A→B→A, fuente obsoleta, fallos de carga/firma, expiración de lease, timeout HTTP/reconexión explícita, identidad/relación denegada, auditoría y conservación byte a byte de snapshots. El JWT expirado se comprueba realmente; el vencimiento durante generación utiliza un reloj de prueba explícito. El almacenamiento firmado de filesystem sigue siendo un doble y no certifica GCS.

`test:release` compila separadamente el portal en modo API productivo y comprueba en Edge que un clínico autorizado puede leer el reporte, pero no generar ni descargar PDF, incluso con grants y capacidad de exportación. Usa respuestas sintéticas interceptadas y deja sus artefactos ignorados en `test-results/`.

La publicación del código en main conserva el historial y no constituye un despliegue ni una habilitación productiva. Identidad, almacenamiento y controles de exportación productivos requieren una intervención posterior.

Validación local del protocolo atómico (2026-11-07): 430 pruebas backend y dos comprobaciones de contrato repetidas después de actualizar OpenAPI; 130 Vitest; 82 Playwright de la suite completa y 20 del módulo repetidas tras distinguir estados pendientes/fallidos/obsoletos; una prueba del build API productivo con PDF bloqueado. Integración: cinco pruebas de navegador HTTP y 21 comprobaciones adicionales del protocolo con MongoDB real, incluidos seis snapshots históricos preservados. Typecheck, contratos generados, ESLint, formato y build aprobaron. Gate Ruff sin infracciones nuevas, con deuda previa inventariada; escaneo de los 28 archivos seleccionados sin secretos y auditorías npm/pip sin vulnerabilidades conocidas. Los 101 archivos académicos, scoring, catálogo y dependencias conservaron sus hashes. Estas verificaciones no habilitan producción ni certifican proveedores externos.
