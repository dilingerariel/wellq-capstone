# Identidad y HTTP real

La confirmación de paciente está descrita en [REVIEW.md](REVIEW.md). El harness actual también pide consentimiento IA sintético, ejecuta extracción con el proveedor de PDF anotado y verifica correcciones/confirmación reales; las referencias anteriores a «no se pide IA» describen la entrega previa de carga, no la cobertura actual.

## Autoridad pendiente

El diseño delega la identidad en la plataforma principal de WellQ; las fuentes consultadas no eligen una marca de proveedor. En este checkout no hay SDK, registro de cliente ni host de identidad productivo conectado al portal. Tampoco hay un `.env` operativo del backend con autoridad confiable. No es seguro arrancarlo con los valores predeterminados de MongoDB. No se inició ni se reconfiguró la instancia local de desarrollo.

FastAPI verifica exclusivamente RS256 con clave pública RSA de al menos 2048 bits, emisor y audiencia configurados por el operador. No consulta JWKS, `jku` ni claves suministradas por el token. Claims exigidos por `app/dependencies/auth.py`:

| Claim                             | Requisito                                                                                      |
| --------------------------------- | ---------------------------------------------------------------------------------------------- |
| `iss`, `aud`                      | Coincidir con `JWT_ISSUER` y `JWT_AUDIENCE`                                                    |
| `iat`, `nbf`, `exp`               | Segundos Unix enteros; `iat <= nbf < exp <= iat + JWT_MAX_LIFETIME_SECONDS` (3600 por defecto) |
| `sub`, `client_id`, `resource_id` | Cadenas no vacías de hasta 200 caracteres; `client_id` identifica el tenant                    |
| `role`                            | `patient` o `clinician`                                                                        |
| `patient_id` / `clinician_id`     | El correspondiente al rol coincide con `resource_id`; el otro ausente o nulo                   |
| `permissions`, `capabilities`     | Listas de cadenas emitidas por la autoridad, nunca concedidas por el navegador                 |

Lecturas requieren `clinical:read`. Futuras operaciones exigen sus propios permisos (`clinical:write`, `clinical:review`, `extractions:confirm`, `extractions:validate`, `documents:download`, `reports:export`); exportar también requiere `report_export`. El servidor filtra el tenant, verifica la propiedad y consulta `patient_access` para el profesional (`care_clinician_id`, `authorised_clinicians` o `authorized_clinicians`). El helper admite `clinic_id`, pero el token y las llamadas actuales no lo suministran; no concede acceso por sí solo.

El responsable de identidad debe proporcionar:

1. Proveedor/tenant autorizado, SDK o integración, registro de cliente web, flujo aprobado, dominios y URLs de retorno/salida permitidos. Estos valores aún no están definidos: no se pueden deducir ni inventar.
2. Access token **para esta API**, con los claims anteriores; correspondencia del sujeto con paciente/profesional y tenant, permisos y capacidades. Un ID token OIDC genérico no basta.
3. `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_PUBLIC_KEY` confiables **en FastAPI**, más política de renovación, revocación y cambio de claves. La clave de firma permanece en el proveedor. El backend usa una clave pública estática; la rotación necesita actualización coordinada del operador.
4. Sesiones de prueba autorizadas de ambos roles, relación asistencial en el tenant correcto y MongoDB autenticado con replica set/esquema/índices ya preparados mediante su procedimiento existente. No inicializar bases con datos.

## Conectar el host aprobado

Instalar `window.wellqIdentity` antes de montar React, implementando `IdentityProvider` de `src/types/session.ts`. Obtener la sesión mediante el SDK autorizado; no interpretar un JWT no verificado para inventar permisos. Mapear valores verificados a `accessToken`, `tenantId` (`client_id`), `resourceId` (`resource_id`), `role`, `permissions`, `capabilities`, `expiresAt` (`exp`). `getSession`/`refreshSession` retornan `null` si la sesión fue revocada o cerrada; un fallo de transporte puede lanzar una excepción. `subscribe` notifica cambios de cuenta, tenant, permisos y cierre. El cierre local limpia inmediatamente las vistas aunque el proveedor esté inaccesible.

Tokens solo en memoria; no añadir formularios de tokens ni claves al frontend. El host determina inicio/cierre/renovación; no hay endpoint de login propio. Sin host válido, el modo API queda bloqueado y nunca recurre a demo.

Después de configurar **el backend mediante su procedimiento autorizado**, crear `frontend/.env.local` (ignorado por Git):

```dotenv
VITE_DATA_MODE=api
VITE_API_BASE_URL=/api/v1
VITE_API_HEALTH_URL=/health
```

```powershell
# Solo si la API autorizada está escuchando en este destino.
$env:WELLQ_DEV_API_TARGET = 'http://127.0.0.1:8000'
npm.cmd run dev
```

`WELLQ_DEV_API_TARGET` pertenece al proceso Vite, no al bundle. Admite HTTP exclusivamente en loopback y HTTPS remoto, sin credenciales/query/fragmento en la URL; es opcional para el destino local predeterminado. Reiniciar Vite tras cambios. Para alojamiento, configurar TLS y proxy del mismo origen para `/api/*` y `/health`; con otro origen, FastAPI debe permitir explícitamente el origen web en `CORS_ORIGINS`. El proxy de desarrollo no se incluye en `dist/`. Verificar `/ready` en el backend: `/health` solo acredita disponibilidad básica. Ninguna variable `VITE_*` puede contener secretos.

## Prueba contra FastAPI

```powershell
npm.cmd run test:live
```

Requiere Docker Desktop y el entorno **de integración ya aprovisionado** bajo `../backend/integration/.runtime`: `state.json`, claves sintéticas y contenedores Compose existentes, inicialmente detenidos. Python necesita las dependencias del backend (`PyJWT`, `cryptography`); se busca el venv del checkout o `WELLQ_TEST_PYTHON`. Si falta el entorno o falla una comprobación, se detiene: no aprovisiona, reinstala, omite pruebas ni usa otra base.

El harness comprueba labels, volúmenes, montajes, exclusividad, ausencia de puertos publicados y coincidencia de los fuentes Python de la imagen con este checkout. Arranca solo Mongo/API/objects de ese proyecto. Antes de escribir verifica el marcador de propiedad de la base y el replica set. Añade siete registros sintéticos de metadatos y una relación asistencial bajo un tenant único, más una carga sintética real desde el navegador. No contiene datos de pacientes reales. Se conservan registros/objetos y evidencias; no borra datos ni reinicializa volúmenes. Detiene los contenedores que inició incluso al fallar las pruebas. El worker de producto se invoca con selección restringida al tenant sintético; no se arrancan los workers generales.

La autoridad RS256 **es sintética de integración**, firmada en Python fuera de React; no acredita SSO externo. Las claves permanecen en el runtime ignorado. Los JWT temporales se pasan a Playwright en memoria/entorno de proceso, sin archivos, argumentos, trazas, vídeos ni capturas de autenticación. El navegador usa Vite y un relay limitado a loopback que transporta respuestas HTTP de uvicorn dentro del contenedor. No publica puertos Docker ni intercepta rutas con `page.route`. Es FastAPI real con MongoDB autenticado, no `TestClient` ni respuestas inventadas. En la carga se ejercitan almacenamiento HTTP firmado y escáner dobles explícitos, no GCS/antivirus productivos; no se pide IA. Detalles y alcance en [UPLOAD.md](UPLOAD.md).

Comprueba los cuatro endpoints de consulta, cursor 6+1 sin duplicados, detalle, permisos, relación asistencial, separación de tenant/paciente, token expirado, acceso anónimo, cursor inválido y documento inexistente. React verifica lecturas patient/clinician y el 403 de un paciente sin relación. No existe un endpoint de directorio: el profesional selecciona el ID y el servidor autoriza cada solicitud.

`test:browser` sigue usando interceptaciones sintéticas para fallos controlados (503/red), continuidad, cambios de identidad y responsive. Vitest verifica timeout/cancelación y fallos del proveedor. No se atribuyen esos fallos inyectados a averías reales de FastAPI ni se acredita SSO o subida productiva.

Validación del incremento anterior de identidad: typecheck, lint, formato, build, 32 pruebas Vitest, 23 regresiones de navegador, 15 comprobaciones HTTP directas y dos escenarios React contra FastAPI aprobados. La matriz cubre los diez anchos de 320 a 1920 px, tablet, horizontal/tacto, teclado, reflow equivalente al 200 %, Axe, sesiones y PWA offline. El escáner existente no detectó secretos en la selección y `npm audit` no informó vulnerabilidades conocidas. Los 368 archivos versionados fuera de frontend conservan sus bytes. Los contenedores de integración terminaron detenidos y sin puertos publicados.

## Continuidad y carga

Un fallo de red del proveedor conserva una sesión aún vigente y formularios/cachés de esa identidad en RAM; estado `unverified`, sin nuevas lecturas hasta revalidación. Expiración, 401, sesión nula/inválida o cambio de identidad limpian los datos privados. Reconexión no ejecuta mutaciones. El shell offline guarda exclusivamente recursos públicos; recargar pierde el trabajo privado en memoria.

`features/uploads/intent.ts` prepara metadatos, SHA-256 y claves estables; `controller.ts` y `/upload` implementan el flujo real de initiate/PUT/complete/sondeo, con cancelación y recuperación explícita en RAM. No se permite prescindir del original hasta la autorización explícita del estado servidor. No hay replay offline ni almacenamiento persistente de documentación médica. La identidad y el almacenamiento productivos siguen pendientes de configuración/aprobación. Véase [el módulo de carga](UPLOAD.md).
