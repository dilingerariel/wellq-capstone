# Integración Docker aislada de WellQ

Fecha: 2026-11-05, America/Santiago. Rama `fix/wellq-backend-hardening`; HEAD base `fb8746cd42fe107bbda82dd92d3a4d11d545fd3e`. Trabajo local sin commit. Resultados y límites en [14](14_RESULTADOS_PRUEBAS_INTEGRACION.md) y [16](16_PENDIENTES_POST_INTEGRACION.md).

## Protección e identidad

Se conservaron status, diff y hashes de 197 archivos existentes antes de editar. Respaldo legible de 91 archivos backend, incluidos untracked relevantes, sin secretos reales: `C:\Dev\wellq-integration-backups\20261105-115253\backend-before.zip`; su directorio contiene `baseline.json` y `baseline.diff`. No se descartaron cambios previos. La comprobación posterior está en [preservation.json](evidencias_integracion/preservation.json).

La inspección inicial fue de lectura: Docker version/info/ps, Compose ls y contexto. Acceso efectivo al motor desde Codex. Engine 29.8.2, Desktop 4.94.0, contexto `desktop-linux`, Compose v5.5.1, Linux; memoria disponible para Docker 3,021,676,544 bytes (~2.81 GiB). No se cambiaron ACL ni políticas persistentes de PowerShell.

Los contenedores antiguos `wellq-api` y `wellq-mongodb`, el volumen `backend_mongodb_data`, sus datos/logs y la carpeta OneDrive no se utilizaron ni se modificaron. Los puertos host 8000 y 27017 no se emplearon. La presencia y estado de contenedores antiguos se observaron exclusivamente como metadatos de `docker ps`.

| Recurso nuevo | Identidad |
|---|---|
| Proyecto Compose | `wellq-int-39706292db88` |
| Base de pruebas | `wellq_integration_39706292db88` |
| Replica set de un nodo | `wellqIntRs`; miembro `mongo-int:27017` |
| Red | `wellq-int-39706292db88-net` |
| Volúmenes | Prefijo del proyecto más `mongo-data`, `mongo-key`, `synthetic-store`, `clam-signatures` |
| Imagen backend | `wellq-int-39706292db88-backend` |
| Servicios | `setup-int`, `mongo-int`, `provision-int`, `objects-int`, `api-int`, `worker-int` (2 réplicas), `runner-int`, `clamav-int` (perfil antivirus) |
| Puertos publicados | Ninguno; HTTP, Mongo y ClamAV solo dentro de la red Docker |

Inventario efectivo, imágenes, límites y montajes: [resources.json](evidencias_integracion/resources.json). Configuración resuelta sin contraseñas/URI: [compose-resolved-redacted.json](evidencias_integracion/compose-resolved-public.json).

## Construcción y controles

[Compose](../integration/compose.yaml) y [Dockerfile](../integration/Dockerfile) independientes de los Compose antiguos. La imagen copia `app`, `scripts` e `integration` desde el backend de `C:\Dev`; no monta código desde OneDrive ni importa el backend antiguo. `.dockerignore` excluye runtime privado y evidencias. Python real **3.11.18**, MongoDB **7.0.43**. Imagen base observada `python:3.11-slim@sha256:064f01707f2fc8b06bae86bb43875266c6e41bac7994e77ec5dc623c4a4d0545`. Versiones completas de dependencias en [runtime.json](evidencias_integracion/runtime.json); no se cambiaron requirements en esta tarea. Los tags de imágenes pueden avanzar: conservar el inventario y la imagen local para repetir exactamente esta corrida.

API/worker/gateway/runner usan usuario 10001, raíz de imagen de solo lectura, tmpfs `/tmp`, sin capabilities y `no-new-privileges`. Límites: Mongo 512 MiB (cache WiredTiger 0.25 GB), API/workers 256 MiB por proceso, gateway 128 MiB, runner 512 MiB. ClamAV tiene límite 1800 MiB y se ejecuta por separado para respetar la memoria disponible. El host no fue reconfigurado.

`Prepare.ps1` genera RSA 2048 de prueba, claves de gateway, contraseñas aleatorias y nombres exclusivos en `integration/.runtime/`, ignorado por Git. La clave privada RS256 solo se monta en el runner; API/workers reciben la pública. Issuer `https://identity.wellq-integration.invalid`, audiencia `wellq-integration-only`; identidades, relaciones, claims y PDFs son sintéticos. No hay login productivo nuevo.

`Common.ps1` exige la ruta autorizada de C:\Dev, proyecto con patrón exclusivo, configuración Compose sin puertos publicados ni nombres globales, montajes permitidos y volúmenes/red con etiquetas del propio proyecto. Rechaza referencias antiguas, OneDrive, volúmenes externos y URI de otra base. Cada comando utiliza `-f`, `--env-file` y `-p` explícitos. No se invoca el Compose antiguo por autodetección.

Mongo utiliza keyfile, autenticación y usuario de aplicación `readWrite` limitado a la base nueva. `provision.py` inicia el replica set, espera primary y ejecuta el `init_indexes` administrativo del backend solo sobre una base vacía. Inserta una marca con proyecto/run. Si la base existe con esa marca, no migra ni reinicializa esquemas; si contiene datos sin marca compatible, aborta. `guard.py` verifica entorno test, URI, DB, ownership y replica set antes de habilitar adaptadores o escribir datos. API y workers no reciben credenciales root.

El primer arranque rechazó un keyfile sintético generado con alfabeto URL-safe. Se corrigió el generador a Base64 estándar y se preparó nuevamente solo el volumen recién creado de esta integración. Se preservaron los volúmenes existentes. El siguiente arranque provisionó correctamente; no se presenta el intento fallido como prueba aprobada.

## Servicios reales y dobles declarados

| Componente | Ejecución y alcance |
|---|---|
| API | Uvicorn/FastAPI real, HTTP sobre la red Docker; lifespan y readiness reales |
| Mongo | MongoDB autenticado, replica set, índices/validadores, sesiones y transacciones reales |
| Workers | Dos procesos separados ejecutando el worker de la aplicación; leases y estados persistidos |
| Objetos | Doble explícito filesystem/gateway HTTP sobre volumen exclusivo; PUT real, bytes/hash/MIME, create-only y promoción privada modelados |
| Firma de enlaces | HMAC local del gateway de pruebas; **no** firma Google, IAM ni GCS |
| IA | Doble explícito `AnnotatedPdfProvider`, extrae JSON `WQINT:` del contenido del PDF generado; no clasifica por título ni contacta modelos externos |
| Escáner, suite principal | Doble explícito que reconoce un marcador sintético; no acredita ClamAV |
| Escáner, suite antivirus | `ClamAVScanner` de la aplicación contra daemon TCP real y firmas oficiales incluidas en la imagen; almacenamiento sigue siendo doble |

El DTO de almacenamiento mantiene el enum existente `gcs` por compatibilidad, pero en **este entorno** la implementación es filesystem/gateway. Ese valor no acredita un bucket, firmas, generaciones, precondiciones ni políticas reales de Google Cloud. Los adaptadores solo se inyectan mediante el bootstrap de integración tras verificar la DB propia; no se cambió el adaptador productivo ni se habilitaron URLs ficticias productivas.

`ENVIRONMENT=test`, `CATALOG_CLINICALLY_APPROVED=false`. El scoring numérico observado usa la excepción explícita de pruebas preexistente. `AI_PROVIDER_APPROVED=true` autoriza únicamente el proveedor sintético de esta configuración; no constituye aprobación del catálogo ni del proveedor productivo.

## Reproducción desde PowerShell

Desde `C:\Dev\wellq-capstone\wellq-clinical-tests-main\backend`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File integration/Prepare.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File integration/Inspect.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File integration/Start.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File integration/Test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File integration/Examples.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File integration/RestartProbe.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File integration/ClamAV.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File integration/Stop.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File integration/Report.ps1 -BaselinePath C:\Dev\wellq-integration-backups\20261105-115253\baseline.json
```

`Prepare` usa `.venv\Scripts\python.exe` en la raíz del repositorio y `cryptography` ya instalado; Docker Desktop/Compose deben estar accesibles. Bypass afecta únicamente ese proceso. `Build.ps1` permite reconstruir solo la imagen. `Test` espera API healthy y falla ante cualquier error de pytest; el runner desaparece al terminar y conserva XML mediante bind del directorio de evidencias.

`RestartProbe` deja un job pendiente con workers detenidos y reinicia exclusivamente API y workers propios. `ClamAV` detiene API, workers y gateway propios para liberar RAM, ejecuta su suite y al salir detiene ClamAV; no reactiva HTTP automáticamente. Para volver a probar HTTP, ejecutar `Start` después de terminar antivirus. No ejecutar ambas suites simultáneamente: utilizan controles de fallos compartidos de esta base sintética. El gateway local solo tiene sentido dentro de Docker y no está publicado al navegador.

`Stop` conserva todos los volúmenes, datos sintéticos e imágenes. Ningún script elimina recursos ni ejecuta limpiezas globales. La limpieza futura de volúmenes requiere una instrucción explícita y revisión de sus nombres. No compartir `.runtime`, claves ni contraseñas; conservarlo localmente para reiniciar este mismo proyecto. `Report` es una comprobación de esta entrega: exige el baseline original y falla si cambian archivos previos fuera de los tres ajustes autorizados.
