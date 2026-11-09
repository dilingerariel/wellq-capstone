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
