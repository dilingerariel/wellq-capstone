# Scoring y reproducibilidad

> **Vigencia tras cierre focalizado F01-F07 (2026-11-05):** Se mantienen formulas/parametros. Referencia incompleta incompatible con direccion se excluye con motivo; referencias unilaterales solo usan ramas justificables. No se inventan limites. Publicacion filtrada por aprobacion/procedencia tambien en historicos. [Detalle y evidencia](12_CIERRE_DEFECTOS_F01_F07.md).
> El contenido anterior al cierre se conserva a continuacion como referencia historica; esta nota y el documento12 prevalecen donde difieran.

**Fecha:** 2026-11-05 (America/Santiago). **Rama:** fix/wellq-backend-hardening. **Base:** fb8746cd42fe107bbda82dd92d3a4d11d545fd3e + cambios sin commit.

**Alcance:** backend; rutas de código relativas a wellq-clinical-tests-main/backend salvo indicación. **Método:** contraste estático, implementación y pruebas aisladas. **Límites:** sin servicios clínicos, datos reales, migraciones, despliegues ni validación clínica. No se modificó frontend.


## Política preservada
Puntuar tras confirmación de paciente es válido según la aclaración del encargo; validación clínica es un nivel adicional. No se cambió la función a cuadrática. Se preserva la función lineal por tramos 0–100, cuatro pilares (bone, muscle, joint, cardio), coberturas y penalizaciones de la implementación existente.
Los pesos/rangos originales son ilustrativos y no se han ampliado ni declarado clínicamente aprobados. La publicación de score fuera del entorno test exige CATALOG_CLINICALLY_APPROVED. Con aprobación pendiente se puede confirmar/eliminar, pero no se publica puntaje.

## Correcciones
La ventana se calcula por meses calendario, configurable de 1 a 60. Se filtra measured_on entre inicio y hoy ANTES de escoger última medición por código. Se excluyen futuros, invalidated_at, no confirmados, valores no finitos, fuente sin padre activo y examen eliminado.
Orden de desempate: measured_on, updated_at e _id descendentes. La normalización también rechaza NaN e infinitos.
Borrado y reproceso invalidan marcadores y recalculan. Rechazo clínico también recalcula. Corrección clínica guarda historial y propaga valores a extracción/serie/reporte. Sin correcciones, validar no cambia matemáticas.
El contexto transaccional protege cambios relacionados; el gate por paciente fuerza conflicto serializable entre escritores. No se probó la garantía real del servidor Mongo.

## Catálogo
Se mantiene cat-2026.08 de diez marcadores, copiado defensivamente. No se siembra/upsertea al arranque ni se sustituye con contenido mutable de DB. No hay catálogo más amplio aprobado, sinónimos multilenguaje ni rangos por edad/sexo implementados.
Una actualización clínica futura debe publicar una versión nueva, tests y aprobación. No basta activar una variable para validar médicamente los parámetros: la variable representa una decisión externa que debe quedar respaldada.

## Snapshot
Nueva inserción en score_snapshots; la fachada rechaza updates sobre snapshots. Guarda scoring_version, catalog_version, catálogo íntegro, hash de catálogo, parámetros, inputs clínicos privados, source_digest, contribuciones, banderas y exclusiones disponibles.
Los inputs clínicos están en almacenamiento privado, no en auditoría técnica. No se afirma inmutabilidad física o capacidad histórica de ejecutar cualquier versión.
Versión de algoritmo disponible: score-v1.0. Un override distinto se rechaza en vez de renombrar la misma fórmula. Recuperar código de una versión histórica es un procedimiento separado, no un flag mágico.
Lecturas clínicas comprueban coherencia de snapshot con los datos vigentes y el día de ventana. Si cambió el origen, expiró el día o falta catálogo aprobado, no se presenta como score vigente. Debe programarse el recálculo periódico: hoy no existe un scheduler diario.

## Recálculo
scripts/recompute_scoring.py exige --client-id, admite --dry-run explícito/por omisión y --apply mutuamente excluyentes. Simulación no cambia Mongo; la CLI puede escribir su informe Markdown incluso en dry-run.
No se ejecutó el script contra datos reales. Cada paciente aplicado usa transacción y revisión por paciente. No hay atomicidad de lote completo: una caída puede dejar algunos pacientes procesados; debe conciliarse por snapshots/auditoría.
El SOP anterior se conserva como histórico, pero sus promesas de rollback por simple --version y siembra mutable quedan superadas por este documento. Cualquier recálculo histórico requiere respaldo, simulación y autorización independiente.

## Evidencia y pendientes
checks/test_scoring.py reutiliza conversiones y fórmula de referencia existentes y agrega ventana, bordes, empates, invalidación, borrado, no finitos, versión y dry-run. checks/test_lifecycle.py verifica propagación de corrección y borrado.
No hay validación médica de pesos/rangos, certificación diagnóstica ni tratamiento/triage automático. Pacientes no tienen acceso a endpoints de score/reportes ni reciben subscores en DTO de extracción.
