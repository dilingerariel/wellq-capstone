# WellQ · Portal web

Primera implementación React del portal. Rama `feature/wellq-react-frontend`, basada en `20fa09c`. Sin cambios de lógica clínica ni de infraestructura. Se retira únicamente el HTML de demostración no servido por FastAPI.

## Ejecutar en Windows

Node.js 24 LTS y npm. Usar `npm.cmd` evita modificar la política de ejecución de PowerShell.

```powershell
cd C:\Dev\wellq-capstone\wellq-clinical-tests-main\frontend
npm.cmd ci
npm.cmd run dev
```

Abrir http://127.0.0.1:5173. La configuración inicial es **demostración explícita**, con documentos sintéticos y selección de los dos roles acreditados. No hay login simulado ni JWT firmado en el navegador.

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd run preview
npm.cmd run test:browser
```

Las pruebas de navegador usan Edge instalado en Windows y dos servidores locales temporales: 5173 (demo) y 5174 (API con identidad/respuestas sintéticas interceptadas). Cerrar otros procesos que usen esos puertos antes de ejecutarlas. Capturas y trazas quedan en `test-results/`, ignorado por Git. Estas pruebas no acreditan integración clínica real.

## Estructura

- `src/app`: rutas, proveedores, límite de errores y sesión.
- `src/components`: tabla, estados y badges accesibles.
- `src/features`: exámenes, contexto de paciente, vista principal, catálogo y adaptador demo separado.
- `src/layouts`: navegación y estructura responsive.
- `src/services`: HTTP y adaptador REST.
- `src/types`: contratos OpenAPI generados y validación de las respuestas renderizadas.
- `src/hooks`, `src/lib`, `src/styles`, `src/i18n`, `src/test`: preferencias visuales, formatos, tokens, diccionarios y pruebas.
- `e2e`, `scripts`, `public`: verificaciones de navegador, generación reproducible y recursos locales.

React Router separa las vistas `/clinical` y `/patient`; `/exams`, `/exams/:id` y `/catalog` son compartidas. El backend mantiene la autoridad sobre rol, grants, tenant, propiedad y relación clínica. La navegación de paciente no expone scores ni reportes clínicos. No existe un rol administrador implementado porque el backend actual no lo admite.

## Demostración y API real

Para API real, crear `.env.local` (ignorado):

```dotenv
VITE_DATA_MODE=api
VITE_API_BASE_URL=/api/v1
```

Reiniciar Vite. El proxy de desarrollo envía `/api` a `http://127.0.0.1:8000`; requiere que el backend se inicie **por su procedimiento existente**, con identidad y dependencias ya configuradas. Este proyecto no inicia Docker ni modifica secretos. Las variables `VITE_*` son públicas: nunca incluir credenciales en ellas.

La plataforma de identidad debe instalar `window.wellqIdentity` **antes de montar React**, con:

```ts
interface IdentityHost {
  getSession(): Promise<unknown>
  subscribe?(onSessionChanged: () => void): () => void
}
```

El resultado válido se define en `src/types/session.ts`: `accessToken`, `role` (`patient` o `clinician`), `resourceId`, `tenantId`, `permissions`, `capabilities`, `expiresAt` (segundos Unix). Debe proceder del proveedor de identidad aprobado. El frontend valida la estructura; **el backend verifica la firma y la autoridad de los claims**. No se interpreta un JWT no verificado para conceder permisos ni se proporciona un formulario para introducir tokens. No hay endpoint de login/refresh en este módulo. El host debe notificar cambios de sesión para limpiar la caché; al expirar o recibir 401 se cierra el acceso hasta una comprobación explícita. Tokens y datos remotos permanecen en memoria. Solo tema e idioma se guardan en localStorage.

Sin host de identidad, el modo API muestra el bloqueo. Nunca cae automáticamente a demo. El clínico introduce el ID de un paciente autorizado porque no hay endpoint de directorio de pacientes en este contrato. Los errores del servidor se muestran por categoría, sin reflejar mensajes privados. `Retry-After` se conserva; 429 y 503 no desencadenan reintentos automáticos. El listado usa el cursor opaco del servidor, sin inventar totales. Los recuentos de la vista principal describen únicamente la página cargada.

| Función implementada              | Ruta REST                                   | Estado                                                    |
| --------------------------------- | ------------------------------------------- | --------------------------------------------------------- |
| Exámenes del paciente autenticado | GET `/clinical-tests`                       | Adaptador API tipado + demo                               |
| Exámenes de paciente autorizado   | GET `/patients/{patient_id}/clinical-tests` | Adaptador API tipado + demo; requiere relación clínica    |
| Detalle del documento             | GET `/clinical-tests/{clinical_test_id}`    | Adaptador API tipado + demo                               |
| Catálogo                          | GET `/marker-catalog`                       | Adaptador API tipado + demo; muestra validación declarada |

Prefijo común `/api/v1`. Los contratos se generan desde `../backend/docs/openapi.json`; `npm.cmd run contracts:generate` actualiza tipos y `contracts:check` detecta divergencias. `items` del listado es abierto en OpenAPI: se comprueba en runtime el formato `ClinicalTestResponse` que realmente serializa la ruta. Las secciones clínicas abiertas no se presentan como tipos más precisos que el servidor.

Todavía **no implementados**: carga, PUT firmado, confirmación, edición, validación clínica, descarga, series, scores y exportación. Se muestran como pendientes, sin botones de éxito ficticio. La futura carga debe usar SHA-256 real, `required_headers`, sesión de subida, consentimiento, claves idempotentes estables, confirmación y sondeo; nunca simular progreso o eliminación segura del archivo. Scores y PDF deben provenir del servidor.

## HTML histórico y despliegue

`frontend/index.html` es ahora la entrada de Vite. Se retiró `backend/app/static/index.html` tras comprobar que FastAPI no lo montaba. En FastAPI, `/dashboard/`, `/demo` y `/static/index.html` continúan cerradas (404); no se expone una interfaz antigua. En el servidor web React, los marcadores `/dashboard/` y `/demo` redirigen a la vista inicial **sin cambiar el modo configurado**.

Producción: `npm.cmd ci` y `npm.cmd run build`. Servir `dist/` mediante un servidor web independiente que resuelva las rutas SPA a `index.html`, mantenga `/api/*` como proxy a FastAPI y respete sus errores (no devolver HTML en una ruta API fallida). No versionar `dist/`. No se añadió un montaje público a FastAPI. Configurar TLS, CSP, políticas de caché privadas y el proveedor de identidad en el alojamiento definitivo. `vite preview` solo permite revisar la compilación localmente.

## Fuentes y alcance académico

Se consultaron el Documento Maestro disponible en Downloads, Visión y Roles Scrum, Requerimientos, DAS, Épicas, Plantilla de Historias y Product Backlog de `FASE 2/Evidencias Proyecto`, además de los contratos 03, handoff 11 y OpenAPI del backend. Los documentos `05_AUDITORIA_FRONTEND.md` y `09_PREPARACION_FRONTEND.md` no existen en este checkout; no se inventaron. La documentación vigente de almacenamiento y despliegue está en los documentos 05 y 09 del backend.

| Clasificación                 | Requisito y estado en este incremento                                                                                                                                                             |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Académico transversal · EP-09 | i18n ES/EN, temas mediante CSS, foco, teclado y estados con texto e iconos implementados; pruebas automáticas no equivalen a una certificación integral de accesibilidad.                         |
| Portal · EP-06                | Listado, filtros, cursores, detalle y catálogo implementados. Reporte tabulado clínico, longitudinal y PDF pendientes.                                                                            |
| Accesos · EP-07               | Roles patient/clinician y contrato externo de sesión preparados; permisos definitivos en servidor. Proveedor de identidad real y validación multi-tenant E2E con infraestructura pendientes.      |
| Flutter exclusivo · EP-01     | Copia privada, cola durable Drift/SQLite, recuperación tras cierres, sincronización y conectividad intermitente pendientes en el cliente móvil. React responsive no los sustituye.                |
| Backend/servicios externos    | Proveedor multimodal, identidad, almacenamiento firmado y aprobación clínica deben habilitarse y verificarse en sus entornos. No se presentan como resueltos por esta interfaz.                   |
| Decisiones técnicas           | Vite, TanStack Query, RHF/Zod y tipos derivados organizan compilación, caché y validación. Tokens CSS y Lucide evitan un framework visual adicional. No constituyen requisitos académicos nuevos. |

Las fuentes académicas también mencionan administrador/auditor: no se implementa ese rol contra una API que solo admite patient/clinician. No se alteraron documentos académicos.

Las versiones exactas se fijan en `package.json` y `package-lock.json`. Los overrides de minimatch 11.0.1 afectan únicamente a herramientas de lint; corrigen GHSA-g3hv-75wg-m249 sin ejecutar `audit fix --force` ni degradar ESLint. Revalidar al actualizar herramientas. Documentación oficial consultada: [Vite](https://vite.dev/guide/), [React Router](https://reactrouter.com/start/declarative/installation), [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview).

Siguiente módulo: integrar el proveedor real de identidad y verificar lectura con sesiones patient/clinician y relaciones clínicas autorizadas; después, revisión/validación clínica del examen con trazabilidad.

## Validación de este incremento · 6 de noviembre de 2026

Instalación `npm.cmd ci`, typecheck, lint, comprobación de contratos, formato y build aprobados. Vitest: 17 pruebas aprobadas. Edge/Playwright: seis pruebas aprobadas, con escritorio, tablet (820 px), móvil (390 px), navegación por teclado, ES/EN, temas, cursores, guardas de rol, sesión externa pendiente, errores 403/401 y limpieza de caché al cambiar identidad. Axe no detectó violaciones en las vistas comprobadas (WCAG A/AA y 2.1 AA); no es una certificación de toda la aplicación. Se inspeccionaron capturas reales. El test focalizado existente de FastAPI para rutas privadas y acceso anónimo también aprobó. Las operaciones OpenAPI y el resto del backend conservan sus bytes. `npm audit`: cero vulnerabilidades conocidas en la resolución actual.

La API se comprobó mediante interceptaciones sintéticas en navegador; identidad y servicios externos reales todavía requieren integración. Las dependencias exactas instaladas constan en el lockfile. Esta validación no reemplaza las pruebas clínicas del backend ni acredita un despliegue productivo.
