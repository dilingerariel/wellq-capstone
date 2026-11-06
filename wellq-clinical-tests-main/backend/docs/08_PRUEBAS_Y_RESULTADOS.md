# Pruebas y resultados

> **Vigencia tras cierre focalizado F01-F07 (2026-11-05):** Resultado vigente: 276 aprobadas, 209 omitidas, 0 fallidas; 61 casos nuevos. Los 171 historicos puros tambien pasan como evidencia complementaria; 140 solapan aserciones reutilizadas. Resultado 215 anterior se conserva debajo como evidencia historica. Ver XML nuevos en evidencias_f01_f07; no se reemplaza test-results.xml. [Detalle y evidencia](12_CIERRE_DEFECTOS_F01_F07.md).
> El contenido anterior al cierre se conserva a continuacion como referencia historica; esta nota y el documento12 prevalecen donde difieran.

**Fecha:** 2026-11-05 (America/Santiago). **Rama:** fix/wellq-backend-hardening. **Base:** fb8746cd42fe107bbda82dd92d3a4d11d545fd3e + cambios sin commit.

**Alcance:** backend; rutas de código relativas a wellq-clinical-tests-main/backend salvo indicación. **Método:** contraste estático, implementación y pruebas aisladas. **Límites:** sin servicios clínicos, datos reales, migraciones, despliegues ni validación clínica. No se modificó frontend.


## Entorno y aislamiento
Python 3.12 local, .venv del workspace. Versiones fijadas en requirements.txt y requirements-dev.txt. No se usaron credenciales de producción ni datos de pacientes.
checks/conftest.py genera claves RSA efímeras en memoria, documentos sintéticos, TestClient sin lifespan/servidor, mongomock y un modelo explícito de rollback. Bloquea socket.create_connection. GCS, escáner y proveedor se sustituyen deliberadamente en las pruebas que lo requieren.
Este diseño comprueba aplicación y contratos, no transacciones reales, IAM, firmas cloud, antivirus real o exactitud médica.

## Resultado final
Comando desde backend:
`../../.venv/Scripts/python.exe -m pytest -q --tb=short -W ignore::DeprecationWarning --junitxml=docs/test-results.xml`

**215 aprobadas, 209 omitidas, cero fallidas; una advertencia Starlette por transporte httpx del TestClient.** La advertencia no se convirtió en error ni se presentó como cumplimiento de integración.

Las 209 omitidas pertenecen a la suite histórica bajo tests. Conservan código y aserciones; su fixture de entorno fue bloqueada antes de cualquier centinela o escritura porque usa identidades HS256, flujo sintético y servicios locales. No se utilizó un bypass de seguridad. Debe portarse a un replica set aislado y proveedor/almacenamiento de test explícitos.
La igualdad entre 209 casos históricos y antiguos resultados del handoff no implica que hoy pasen. Las 215 aprobadas son otro conjunto de casos: nuevos controles y reglas puras reutilizadas.

## Cobertura funcional evidenciada
| Archivo | Qué comprueba |
|---|---|
| checks/test_security.py | Firma/emisor/audiencia/claims/expiración, rol/binding, paciente ajeno, tenant, legacy invisible, grants, paths privados, errores sin body, rate limit, CORS y append-only |
| checks/test_processing.py | Idempotencia/cuota/refresco, ausencia de objeto, escáner faltante, hash/MIME/corrupción/tamaño, PDF/PNG/JPEG/HEIC reales sintéticos, malware simulado, leases y agotamiento, concurrencia con doble transaccional, argumentos/TTL de firma |
| checks/test_scoring.py | Factores y fórmula anteriores, no finitos, ventana calendario, selección vigente, fuentes eliminadas/no confirmadas, empate, versiones, snapshot y dry-run |
| checks/test_lifecycle.py | Confirmación explícita, revisión low confidence, varios paneles, corrección clínica, privacidad de nota, reporte/PDF/hash/replay, borrado, reproceso, propuesta, esquema proveedor y OpenAPI |

## Otras comprobaciones
- Ruff F821/F822/F823 sobre app, scripts y checks: sin nombres indefinidos.
- pip check: sin incompatibilidades declaradas.
- git diff --check: sin errores de whitespace.
- pip-audit: línea base 75 avisos conocidos en nueve paquetes, incluidos herramientas/transitivas; posterior cero avisos en la consulta registrada. Se conservaron JSON before/after.
- OpenAPI generado por app.openapi(), sin iniciar servicios, en docs/openapi.json.

No se calculó cobertura de líneas. Contar casos no permite inferir porcentaje de cobertura ni progreso.

## Bloqueadas y no ejecutadas
Docker CLI está instalado, pero docker info no pudo contactar el motor. No se inició Docker ni otro servicio para eludir esa condición.
Quedan bloqueadas transacciones/índices/validadores contra Mongo real, integración GCS/IAM, ClamAV real, modelo multimodal aprobado y corpus autorizado. No hubo builds de imagen, despliegues, migraciones, recálculos de datos existentes o llamadas con documentos a terceros.

## Interpretación
Las pruebas respaldan las correcciones locales descritas. No bastan para declarar todas las fases completadas, integración cloud operativa o backend listo para producción clínica.
