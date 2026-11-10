// API identifiers remain unchanged. Unknown values never leak technical enums.
String examLabel(String status, {String? review}) => review == 'reviewed'
    ? 'statusReviewed'
    : switch (status) {
        'ready_for_review' => 'statusReady',
        'validated' || 'clinically_validated' => 'statusValidated',
        'rejected' => 'statusRejected',
        'processing' || 'uploaded' => 'statusProcessing',
        'draft' || 'pending_upload' => 'statusPendingUpload',
        'initiated' => 'statusPendingUpload',
        'object_uploaded' => 'statusReceived',
        'deleted' => 'statusDeleted',
        'failed' => 'statusFailed',
        _ => 'statusUnknown',
      };

String? testTypeLabel(String? type) => switch (type) {
  'blood_test' => 'typeBlood',
  'urine_test' => 'typeUrine',
  'imaging' => 'typeImaging',
  'pathology' => 'typePathology',
  'other' => 'typeOther',
  _ => null,
};

String extractionLabel(String status) => switch (status) {
  'awaiting_confirmation' => 'extractionAwaiting',
  'confirmed' => 'extractionConfirmed',
  'clinically_validated' => 'statusValidated',
  'queued' || 'extracting' => 'extractionPreparing',
  'extraction_failed' => 'extractionFailed',
  'unreadable' => 'extractionUnreadable',
  'discarded' => 'extractionDiscarded',
  'rejected' => 'extractionRejected',
  'not_applicable' => 'extractionNotApplicable',
  _ => 'statusUnknown',
};

String uploadLabel(String status) => switch (status) {
  'queued' => 'uploadQueued',
  'initiated' || 'bytes_pending' => 'uploadBytesPending',
  'complete_pending' => 'uploadCompletePending',
  'processing' => 'statusProcessing',
  'confirmed' => 'uploadVerified',
  'rejected' => 'uploadRejected',
  'failed' => 'uploadFailed',
  'conflict' => 'uploadConflict',
  _ => 'statusUnknown',
};

String pendingHelp(String phase, {String? error, bool retryScheduled = false}) {
  if (phase == 'conflict') {
    return 'pendingConflictHelp';
  }
  if (phase == 'processing' || phase == 'object_uploaded') {
    return 'pendingProcessingHelp';
  }
  if (phase == 'rejected') {
    return 'pendingRejectedHelp';
  }
  if (phase == 'failed') {
    return 'pendingFailedHelp';
  }
  if (phase == 'confirmed') {
    return 'pendingVerifiedHelp';
  }
  if (error == 'LOCAL_FILE_CHANGED') {
    return 'pendingHashHelp';
  }
  if (error == 'RETRY_AFTER' || retryScheduled) {
    return 'pendingRetryHelp';
  }
  if (error != null) {
    return 'pendingInterruptedHelp';
  }
  return 'pendingLocalHelp';
}
