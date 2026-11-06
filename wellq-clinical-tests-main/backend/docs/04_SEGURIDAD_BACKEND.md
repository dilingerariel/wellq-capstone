# Seguridad del backend

> **Vigencia tras cierre focalizado F01-F07 (2026-11-05):** Publicacion de subscores/snapshots/reportes/PDF ahora requiere aprobacion y procedencia verificable fuera de test; caches historicos no adquieren aprobacion al cambiar una variable. Accesos/tenant siguen cubiertos; infraestructura no verificada. [Detalle y evidencia](12_CIERRE_DEFECTOS_F01_F07.md).
> El contenido anterior al cierre se conserva a continuacion como referencia historica; esta nota y el documento12 prevalecen donde difieran.

**Fecha:** 2026-11-05 (America/Santiago). **Rama:** fix/wellq-backend-hardening. **Base:** fb8746cd42fe107bbda82dd92d3a4d11d545fd3e + cambios sin commit.

**Alcance:** backend; rutas de código relativas a wellq-clinical-tests-main/backend salvo indicación. **Método:** contraste estático, implementación y pruebas aisladas. **Límites:** sin servicios clínicos, datos reales, migraciones, despliegues ni validación clínica. No se modificó frontend.


## Frontera de identidad
El módulo verifica tokens de una autoridad externa; no crea usuarios ni tokens productivos. RS256 es el único algoritmo aceptado. Clave RSA pública >=2048 bits configurada por operador, nunca jku/jwks indicado por el JWT. iss y aud deben coincidir con configuración confiable.

Claims obligatorios: sub, iss, aud, iat, nbf, exp, client_id, role, resource_id, permissions y capabilities. Para patient exige patient_id=resource_id y ausencia de clinician_id; para clinician exige clinician_id=resource_id y ausencia de patient_id. Los tiempos deben ser enteros y satisfacer iat <= nbf < exp, dentro de la vida máxima. Firma ajena, HMAC, expiración, claims ausentes y mezcla de identidades se rechazan.
La relación entre cuenta sub y recurso clínico debe ser emitida y validada por la plataforma de identidad. Sin esa autoridad configurada el sistema responde 503/no arranca; no se considera completada la integración de identidad. Rotación/revocación/JWKS y política de sesiones definitivas siguen pendientes del proveedor, sin inventar un segundo login.

## Autorización
Identidad, tenant, rol, relación asistencial, permiso y capacidad son comprobaciones distintas.
- Lecturas clínicas: clinical:read.
- Escrituras clínicas generales: clinical:write.
- Confirmación paciente: extractions:confirm.
- Validación clínica: extractions:validate.
- Revisión: clinical:review.
- Descarga: documents:download.
- Exportación: reports:export y capability report_export.
Los grants deben venir de la autoridad firmante. No hay planes ni facturación inventados. Solo se implementó el gating de exportación; la taxonomía comercial general requiere decisión de plataforma.
Se conserva patient_access para clínico de cabecera/lista autorizada, ahora consultado dentro del tenant. Su abastecimiento productivo todavía debe integrarse.

## Aislamiento
TenantDatabase aplica client_id confiable a find/find_one/count/distinct/updates/upserts/inserts. No expone aggregate ni borrado físico. Updates no pueden cambiar client_id; upsert solo admite igualdad sin tenant proporcionado. Operaciones no soportadas fallan.
La DB raw solo se utiliza para conexión/provisionamiento y el worker de sistema que descubre trabajos; cada trabajo pasa después a TenantDatabase. Datos legacy sin client_id no son asignados a un valor por defecto.
La garantía de unicidad necesita índices compuestos del esquema nuevo. Arranque comprueba nombre, claves y unique; no los crea. La migración pendiente es un bloqueo real.

## Archivos
No se montan carpetas clínicas en HTTP. Todo enlace se emite tras rol/propiedad/relación/tenant/permisos. Original solo descargable si ready_for_review y existe verificación y generación. URLs GET <=5 minutos y PUT <=15. Public Access Prevention y uniform bucket-level access son exigidos al inicializar el bucket.
Una URL firmada es una capacidad temporal: quien la reciba puede usarla durante su vigencia. No equivale a una firma digital del PDF ni a autorización en cada GET de GCS. No hay ruta local alternativa por conocer un identificador.

## Errores, CORS y límites
Lista de orígenes explícita, sin wildcard ni cookies con credenciales. Entradas desconocidas se rechazan. Error de validación no refleja body; errores DB devuelven códigos y Retry-After, sin detalles de conexión.
Límite compartido por tenant/sub/minuto en Mongo y cuota de pendientes/refrescos/descargas. No es un WAF ni protección contra volumen de tokens inválidos: el borde de red debe limitar tráfico anónimo y firma costosa.
Cache-Control no-store y X-Content-Type-Options nosniff. Docker desactiva access-log para no volcar rutas clínicas. No hay TLS terminado aquí: responsabilidad de infraestructura pendiente.

## Privacidad y auditoría
Notas de validación nunca se incluyen en la confirmación pública; review no publica private_note. Auditoría técnica admite solo metadatos acotados y excluye valores de corrección y razones libres. clinical_result_history guarda historia clínica de valores en colección tenant privada, distinta de los logs.
Snapshots, historia y eventos son append-only en la fachada de aplicación. Administradores/roles raw de Mongo todavía podrían cambiarlos: no se afirma inmutabilidad física, firma o WORM.
No se verificaron cifrado real en reposo, IAM activo, contratos LLM, retención por plan, política de consentimiento revocable o cumplimiento legal. Consentimiento inicial es un opt-in explícito de IA; no es una plataforma completa de consentimiento granular.

## Evidencia
checks/test_security.py, checks/test_processing.py y checks/test_lifecycle.py. dependencies-before.json documenta 75 avisos en nueve paquetes; dependencies-after.json no registra avisos conocidos en el inventario consultado. Esto no equivale a ausencia de vulnerabilidades o auditoría clínica.
