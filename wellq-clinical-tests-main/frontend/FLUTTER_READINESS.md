# Base verificada para Flutter + Dart + Drift

No se ha creado Flutter ni cambiado contratos. El cliente móvil será independiente
de React y accederá a FastAPI, nunca directamente a MongoDB. Los contratos vigentes
son `../backend/docs/openapi.json` y `src/types/api.generated.ts`; no copiar versiones
anteriores ni inventar endpoints de login, refresh o sincronización.

## Desarrollo y autenticación

Seguir [LOCAL_DEVELOPMENT.md](../../LOCAL_DEVELOPMENT.md). API para Windows:
`http://127.0.0.1:8765/api/v1`; salud `/health` y `/ready`. Los puertos Docker y MongoDB
siguen cerrados. La autoridad sintética está en el host Python, con issuer
`https://identity.wellq-integration.invalid`, audience `wellq-integration-only`, RSA
de al menos 2048 bits y tokens de diez minutos. No copiar claves privadas ni JWT a
Dart, Git, comandos, URLs, analytics o bases locales. El adaptador web de perfiles
no es SSO ni una API productiva de identidad. El cliente Flutter necesitará su
adaptador de identidad externo, con tokens de corta duración conservados en RAM
durante pruebas.

| Perfil      | Operaciones autorizadas                                                                   |
| ----------- | ----------------------------------------------------------------------------------------- |
| Paciente    | Sus documentos, carga, consulta de estados y confirmación; requiere scopes propios        |
| Profesional | Relación clínica verificada, consulta, revisión, validación/rechazo, historial y reportes |

Scopes existentes: `clinical:read`, `clinical:write`, `documents:download`,
`extractions:confirm`, `extractions:validate`, `clinical:review`, `reports:export`.
Exportar exige además `report_export` y rol/relación clínica. El servidor conserva
la autoridad: seleccionar un ID en UI no concede acceso. Cambios de tenant,
identidad, permisos, expiración o logout invalidan datos/borradores/cachés previos.

## Endpoints reales y precondiciones

Prefijo `/api/v1`; usar OpenAPI para DTO completos, parámetros y límites.

| Flujo                    | Contrato                                                                                                                                                                      |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Documentos               | GET `/clinical-tests`, GET/PATCH/DELETE `/clinical-tests/{id}`; cursor de listado                                                                                             |
| Paciente del profesional | GET `/patients/{id}/clinical-tests`                                                                                                                                           |
| Carga                    | POST `/clinical-tests/uploads/initiate`, PUT a la URL firmada recibida, POST `/clinical-tests/uploads/{upload_id}/complete`, GET `/clinical-tests/uploads/{upload_id}/status` |
| Renovar carga            | POST `/clinical-tests/uploads/{upload_id}/refresh-url`                                                                                                                        |
| Extracción               | GET/PATCH `/clinical-tests/{id}/extraction`; acción confirm/discard y ediciones según DTO                                                                                     |
| Revisión                 | PATCH `/clinical-tests/{id}/review` con `expected_version` del detalle actual                                                                                                 |
| Validación               | POST `/clinical-tests/{id}/extraction/validate` con `expected_version`                                                                                                        |
| Series y scores          | GET `/patients/{id}/markers`, GET `/patients/{id}/lab-score?history=true`                                                                                                     |
| Reporte                  | GET `/patients/{id}/lab-report`, `source_version` opaca                                                                                                                       |
| PDF de pruebas           | POST `/patients/{id}/lab-report/export`, `expected_source_version` y `Idempotency-Key`                                                                                        |

No enviar bearer al PUT/GET firmado; conservar headers exigidos por el descriptor.
Antes de borrar un archivo pendiente, comprobar la confirmación de servidor
`local_file_can_be_deleted`, tamaño y SHA-256. Un timeout no equivale a rechazo ni
autoriza repetir la carga con una identidad nueva. Conservar exactamente cuerpo,
versión y clave para los reintentos explícitos admitidos por el contrato. Review
puede tener replay autorizado; validate/reject no deben suponerse idempotentes.

Errores son envelopes `detail.code`: 401 revalidar identidad; 403 denegar y limpiar
contexto; 404 puede indicar `NO_SCORE_AVAILABLE` y no debe fabricar un cero;
409 conflicto/obsolescencia/retryable exige comprobar estado; 428 exige versión;
422 corregir entrada; 429 respetar Retry-After; 502/503 dependencia/resultado
incierto, sin éxito ficticio. No registrar texto clínico, notas ni URLs firmadas.

## Drift, archivos y sincronización futura

Drift/SQLite no constituyen por sí solos una política aprobada de privacidad o
cifrado. Antes de guardar información clínica: cifrado con claves del sistema,
separación tenant/sujeto, retención, borrado, recuperación/backup y revocación
aprobados. Las primeras pruebas pueden usar bases en RAM o solo datos sintéticos;
no habilitar una cola durable de mutaciones clínicas reales por defecto.

Estados locales sugeridos (no endpoints nuevos): borrador → archivo pendiente →
autorización de carga → bytes enviados → confirmación incierta/procesamiento →
confirmado; añadir bloqueado por conflicto, error recuperable y error definitivo.
Persistir una outbox real requerirá versión, cuerpo y clave inmutables, control de
concurrencia y reconciliación: nunca declarar "exactly once" por tener una tabla.
La reconexión revalida identidad y lecturas; no reproduce mutaciones clínicas sin
política/acción explícita. Las guías generales de offline-first no sustituyen las
restricciones de seguridad de WellQ.

Los scores no aprobados permanecen ausentes. El PDF es una instantánea fechada;
`verified_at` no garantiza vigencia continua ni revoca URLs ya entregadas. Conservar
el bloqueo PDF productivo de React y no habilitarlo en el futuro móvil sin decisión
explícita, políticas de enlaces/huérfanos y proveedores reales verificados.

## Android

El emulador documenta `10.0.2.2` como alias del loopback del host. Este puente
rechaza Hosts distintos de los loopback permitidos, por lo que cambiar simplemente
la URL a ese alias **no es una integración móvil verificada**. Para desarrollo,
evaluar `adb reverse tcp:8765 tcp:8765` y URL `http://127.0.0.1:8765/api/v1` sin abrir
MongoDB o listeners externos. No se ejecutó ADB ni se probó un emulador aquí.
Android necesita permiso INTERNET y una excepción cleartext solo en el manifest
debug si se usa HTTP local; producción exige HTTPS y autoridad real. Mantener los
endpoints sintéticos/nonce fuera de builds release. La próxima intervención puede
comenzar el cliente Dart/UI y el esquema Drift sintético; deberá implementar y
probar el adaptador de identidad móvil, no firmar tokens en el dispositivo.

Pendientes externos: SSO, GCS/IAM/firma/retención, antivirus real, proveedor IA,
aprobación clínica, escritores fuera de la fachada transaccional y validación de
infraestructura. Las pruebas locales no certifican esos sistemas.

Fuentes oficiales: [Android: red del emulador](https://developer.android.com/studio/run/emulator-networking-address),
[Flutter offline-first](https://docs.flutter.dev/app-architecture/design-patterns/offline-first),
[Drift](https://drift.simonbinder.eu/).
