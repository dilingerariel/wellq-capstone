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

Generar y descargar son acciones separadas. Se revalida identidad y fuente antes/después de generar y antes de descargar. El controlador mantiene un único envío concurrente y la misma clave/cuerpo ante timeout, firmador pendiente o renovación explícita de URL. No hay replay automático al reconectar. `409 EXPORT_SOURCE_CHANGED` bloquea el PDF obsoleto. Una URL nula nunca habilita descarga.

El contrato actual no ofrece una precondición atómica para vincular un **nuevo** POST a un GET previo. Las comprobaciones del cliente detectan cambios observados; no garantizan que una instantánea descargada refleje toda modificación posterior. El servidor protege los reintentos mediante su hash de fuente. Para una garantía atómica adicional se necesitaría ampliar el contrato, fuera de esta entrega.

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
```

Vitest verifica contratos, separación de unidades/referencias, scores ausentes/cero, cambios de procedencia, cancelación y exportación. Playwright con respuestas interceptadas cubre diez anchos de 320 a 1920 px, ambas vistas, Axe, teclado/tacto, orientación horizontal, reflow equivalente al 200 %, idiomas, temas, offline, cambios de sesión/paciente, fallos de almacenamiento, expiración e idempotencia.

`test:live` utiliza FastAPI/MongoDB aislados y datos sintéticos, sin interceptar las respuestas del navegador. Amplía el flujo existente con lectura del historial/reporte, ausencia real de score y exportación/descarga oficial. Comprueba autorizaciones negativas, un único registro/auditoría de exportación, bytes ReportLab con tamaño/SHA-256 y páginas PDF, firmador temporalmente indisponible con restauración, firma expirada y fuente cambiada. No modifica backend ni documentos; conserva detenidos los contenedores propios de prueba y no interviene MongoDB de desarrollo. Identidad RS256, IA, escáner y almacenamiento local son dobles explícitos: estas pruebas no certifican SSO, GCS o validación clínica productivos.

La publicación y despliegue requieren autorización posterior y configuración de los proveedores aprobados. Esta entrega se conserva en una rama de desarrollo mediante commit local, sin push ni merge a main.
