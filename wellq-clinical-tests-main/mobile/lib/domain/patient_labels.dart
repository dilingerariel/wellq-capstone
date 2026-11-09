// API identifiers remain unchanged. Unknown values never leak technical enums.
String examLabel(String status, {String? review}) => review == 'reviewed'
    ? 'Con revisión profesional'
    : switch (status) {
        'ready_for_review' => 'Pendiente de revisión profesional',
        'validated' ||
        'clinically_validated' => 'Revisión profesional completada',
        'rejected' => 'Revisión no aprobada',
        'processing' || 'uploaded' => 'Procesando documento',
        'draft' || 'pending_upload' => 'Carga pendiente',
        'initiated' => 'Carga pendiente',
        'object_uploaded' => 'Documento recibido',
        'deleted' => 'Examen eliminado',
        'failed' => 'No se pudo procesar',
        _ => 'Estado por consultar',
      };

String? testTypeLabel(String? type) => switch (type) {
  'blood_test' => 'Examen de sangre',
  'urine_test' => 'Examen de orina',
  'imaging' => 'Imagen médica',
  'pathology' => 'Anatomía patológica',
  'other' => 'Otro documento',
  _ => null,
};

String extractionLabel(String status) => switch (status) {
  'awaiting_confirmation' => 'Esperando tu confirmación',
  'confirmed' => 'Datos confirmados',
  'clinically_validated' => 'Revisión profesional completada',
  'queued' || 'extracting' => 'Preparando propuesta',
  'extraction_failed' => 'No se pudo extraer la información',
  'unreadable' => 'Documento ilegible',
  'discarded' => 'Propuesta descartada',
  'rejected' => 'Propuesta no aprobada',
  'not_applicable' => 'Sin propuesta de resultados',
  _ => 'Estado por consultar',
};

String uploadLabel(String status) => switch (status) {
  'queued' => 'Pendiente de envío',
  'initiated' || 'bytes_pending' => 'Archivo pendiente',
  'complete_pending' => 'Recepción pendiente',
  'processing' => 'Procesando documento',
  'confirmed' => 'Documento verificado',
  'rejected' => 'Documento rechazado',
  'failed' => 'Procesamiento fallido',
  'conflict' => 'Requiere revisar el estado actual',
  _ => 'Estado por consultar',
};

String pendingHelp(String phase, {String? error, bool retryScheduled = false}) {
  if (phase == 'conflict') {
    return 'Consulta estados antes de continuar. No prepares otra carga para resolver este conflicto.';
  }
  if (phase == 'processing' || phase == 'object_uploaded') {
    return 'El servidor recibió la carga. Consulta estados; no necesitas enviarla otra vez.';
  }
  if (phase == 'rejected') {
    return 'El servidor rechazó el documento. La copia local se conserva; no se reenvía automáticamente.';
  }
  if (phase == 'failed') {
    return 'El procesamiento falló. Consulta el detalle antes de preparar otra operación.';
  }
  if (phase == 'confirmed') {
    return 'La recepción fue verificada; abre el examen para consultar su extracción y confirmación.';
  }
  if (error == 'LOCAL_FILE_CHANGED') {
    return 'La copia no coincide con su hash. No se enviará; conserva el original y revisa la operación.';
  }
  if (error == 'RETRY_AFTER' || retryScheduled) {
    return 'Espera el intervalo indicado por el servidor antes de reintentar explícitamente.';
  }
  if (error != null) {
    return 'El último intento no terminó. Consulta estados y luego reintenta explícitamente; se conserva la identidad de la carga.';
  }
  return 'Guardado solo en este dispositivo. El envío requiere tu acción explícita.';
}
