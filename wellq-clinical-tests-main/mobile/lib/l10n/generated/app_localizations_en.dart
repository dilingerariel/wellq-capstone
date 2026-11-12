// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get syntheticWarning => 'Synthetic data only • Not for clinical use';

  @override
  String get syntheticEnvironment => 'Synthetic environment';

  @override
  String get syntheticNoClinical =>
      'Synthetic environment · Not for clinical use';

  @override
  String get noClinicalUse => 'Not for clinical use';

  @override
  String get productionBlocked =>
      'WellQ: production mode is blocked. Debug with synthetic data only.';

  @override
  String get home => 'Home';

  @override
  String get exams => 'Exams';

  @override
  String get upload => 'Upload';

  @override
  String get pending => 'Pending';

  @override
  String get settings => 'Settings';

  @override
  String get docsCaption => 'Docs';

  @override
  String get queueCaption => 'Queue';

  @override
  String get changeTheme => 'Change theme';

  @override
  String get refreshReadings => 'Refresh readings';

  @override
  String get checkConnection => 'Check connection';

  @override
  String get welcomeTitle => 'Your health, organized';

  @override
  String get welcomeSubtitle => 'Connect the test profile to continue.';

  @override
  String get welcomeQueue =>
      'Your local queue is kept. After a restart, verify the same profile to open it.';

  @override
  String get connectSynthetic => 'Connect synthetic patient';

  @override
  String get welcomeRequires =>
      'WellQ must be available. Synthetic data only; not for clinical use.';

  @override
  String get helloPatient => 'Hello, patient';

  @override
  String get documentsAtHand => 'Your documents, within reach.';

  @override
  String get uploadDocument => 'Upload document';

  @override
  String get myExams => 'My exams';

  @override
  String get pendingUploads => 'Pending uploads';

  @override
  String get recentExams => 'Recent exams in this view';

  @override
  String get noExamsYet =>
      'No exams yet. Upload the synthetic document to get started.';

  @override
  String get openExamHint =>
      'Open an exam to check whether it needs your confirmation.';

  @override
  String get viewMyExams => 'View my exams';

  @override
  String get untitledExam => 'Untitled exam';

  @override
  String get pendingOperations => 'Pending operations';

  @override
  String get pendingSubtitle =>
      'Your saved documents. You decide when to send them.';

  @override
  String get checkStatesConnection => 'Check status and connection';

  @override
  String get noLocalOperations =>
      'No local operations. You can prepare a document even if the network is interrupted.';

  @override
  String get verifiedLocalCopy => 'Document verified. The local copy is kept.';

  @override
  String get sendDocument => 'Send document';

  @override
  String get retryUpload => 'Retry upload';

  @override
  String get openExamExtraction => 'Open exam and extraction';

  @override
  String get yourSpace => 'Your space';

  @override
  String get appPreferences => 'Application preferences.';

  @override
  String get changeAppearance => 'Switch light / dark theme';

  @override
  String get patientSession => 'Patient session';

  @override
  String get renewPatientSession => 'Renew session and check statuses';

  @override
  String get syntheticProfile =>
      'Synthetic development profile. Not for clinical use.';

  @override
  String get syncStatus => 'Sync status';

  @override
  String get developmentInfo => 'Development information';

  @override
  String get syntheticIdentity => 'Synthetic identity';

  @override
  String get tokensRam => 'Tokens in RAM; RS256 signing on the host only.';

  @override
  String get testPersistence => 'Test persistence';

  @override
  String get syntheticDrift =>
      'Drift/SQLite without real clinical data. Verified synthetic PDF only.';

  @override
  String get productionPdfBlocked => 'Production PDF blocked';

  @override
  String get noProductionProviders =>
      'No exports, scores or production providers.';

  @override
  String get logoutQuestion => 'Sign out?';

  @override
  String get logoutWarning =>
      'Access ends and cached readings are cleared. The queue and private files are kept for this identity.';

  @override
  String get logout => 'Sign out';

  @override
  String get newDocument => 'New document';

  @override
  String get syntheticPdfOnly =>
      'Select a synthetic test PDF or use the included example. Do not select real medical documents.';

  @override
  String get useTestPdf => 'Use test PDF';

  @override
  String get selectTestPdf => 'Select test PDF';

  @override
  String get viewDocument => 'View document';

  @override
  String get documentTitle => 'Document title';

  @override
  String get examDate => 'Exam date';

  @override
  String get isoDateHint => 'YYYY-MM-DD';

  @override
  String get examDateHint =>
      'Recorded exam date; it may differ from the sample date in the PDF.';

  @override
  String get confirmSyntheticOnly =>
      'I confirm that I am using synthetic data only.';

  @override
  String get authorizeSyntheticProcessing =>
      'I authorize synthetic processing of the document.';

  @override
  String get savePending => 'Save to queue';

  @override
  String get saveDoesNotSend =>
      'Saving does not send the file or delete the original.';

  @override
  String get fileTooLarge => 'The file exceeds 20 MiB.';

  @override
  String get syntheticIntegrityOnly =>
      'Invalid, incomplete or integrity-mismatched PDF. Select a valid synthetic PDF without changing its stored copy.';

  @override
  String get pickerUnavailable =>
      'The file picker could not be opened. You can use the included synthetic PDF.';

  @override
  String get operationNotSaved => 'The operation was not saved.';

  @override
  String get back => 'Back';

  @override
  String get confirmAction => 'Confirm action';

  @override
  String get documentsStatusSubtitle =>
      'Your documents and their current status.';

  @override
  String get lastAvailableReading =>
      'Last available reading. It does not confirm server changes.';

  @override
  String get searchScope =>
      'Search and order: loaded documents. Status and type: server.';

  @override
  String get searchLoadedTitles => 'Search loaded titles';

  @override
  String get clearSearch => 'Clear search';

  @override
  String get filterSort => 'Filter and sort';

  @override
  String get serverStatus => 'Server status';

  @override
  String get all => 'All';

  @override
  String get serverType => 'Server type';

  @override
  String get removeServerFilters => 'Clear server filters';

  @override
  String get loadedDocumentOrder => 'Order of loaded documents';

  @override
  String get newestFirst => 'Newest first';

  @override
  String get oldestFirst => 'Oldest first';

  @override
  String get allStatuses => 'all statuses';

  @override
  String get allTypes => 'all types';

  @override
  String get noMatches =>
      'No matches among loaded documents. Load more pages or change your search.';

  @override
  String get noReading =>
      'No reading is available. Check your connection and try again.';

  @override
  String get noFilteredDocuments =>
      'No documents match these filters. Clear them or refresh.';

  @override
  String get noExamsView =>
      'No exams in this view. Refresh or upload the synthetic PDF.';

  @override
  String get morePagesHint =>
      'More server pages are available; their titles have not been searched yet.';

  @override
  String get loadMore => 'Load more';

  @override
  String get refreshList => 'Refresh list';

  @override
  String get examDetail => 'Exam details';

  @override
  String get reviewCompleted => 'completed';

  @override
  String get reviewPendingUnknown => 'pending or not reported';

  @override
  String get stillProcessing =>
      'The document is still being processed. Check its status; you do not need to upload it again.';

  @override
  String get documentCannotConfirm =>
      'This document is not available for confirmation. The local copy is kept; check the status before preparing another.';

  @override
  String get noVerifiedCopy =>
      'There is no verified synthetic copy on this device. Arbitrary documents are not downloaded.';

  @override
  String get extractionUnavailable =>
      'The extraction is not available yet. Check again.';

  @override
  String get examUnavailable =>
      'The exam is unavailable or no longer exists in this view.';

  @override
  String get proposalReadFailed =>
      'The proposal could not be read. Check again.';

  @override
  String get discardQuestion => 'Discard proposal?';

  @override
  String get reviewConfirmation => 'Review confirmation';

  @override
  String get discardWarning =>
      'This proposal will be discarded. The document will not be deleted.';

  @override
  String get lowConfidenceHint =>
      'Low confidence: check this marker against the original document.';

  @override
  String get valueLabel => 'Value';

  @override
  String get unitLabel => 'Unit';

  @override
  String get documentReference => 'Document reference';

  @override
  String get lowerLimit => 'Lower limit';

  @override
  String get upperLimit => 'Upper limit';

  @override
  String get referenceUnit => 'Reference unit';

  @override
  String get referenceText => 'Reference text';

  @override
  String get compareProposal =>
      'Check the proposal against the original synthetic PDF. This is not a diagnosis.';

  @override
  String get confirmationReceived =>
      'Your confirmation has been received. Professional review may still be pending.';

  @override
  String get noNewConfirmation =>
      'Check the exam status. No new confirmation is required.';

  @override
  String get documentDates => 'Document dates';

  @override
  String get collectionDateLabel => 'Sample date';

  @override
  String get reportDateLabel => 'Report date';

  @override
  String get identityAcknowledgement =>
      'I have checked that this document belongs to me.';

  @override
  String get valuesAcknowledgement =>
      'I have checked values, units and low-confidence fields.';

  @override
  String get reviewConfirm => 'Review and confirm';

  @override
  String get retrySameSubmission => 'Retry the same submission';

  @override
  String get discardProposal => 'Discard proposal';

  @override
  String get serverDeterminesStatus =>
      'Status determined by FastAPI. It does not mean professional validation.';

  @override
  String get checkCurrentQuestion => 'Check current status?';

  @override
  String get checkCurrentWarning =>
      'The draft will be discarded and the current proposal fetched. No mutation will be replayed.';

  @override
  String get checkCurrentProposal => 'Check current proposal';

  @override
  String get syntheticDocument => 'Synthetic document';

  @override
  String get zoomOut => 'Zoom out';

  @override
  String get zoomIn => 'Zoom in';

  @override
  String get pdfOpenFailed =>
      'The document cannot be opened: the file is missing or its integrity check failed.';

  @override
  String get pdfRenderFailed => 'The synthetic PDF could not be rendered.';

  @override
  String get statusReviewed => 'Professionally reviewed';

  @override
  String get statusReady => 'Awaiting professional review';

  @override
  String get statusValidated => 'Professional review completed';

  @override
  String get statusRejected => 'Review not approved';

  @override
  String get statusProcessing => 'Processing document';

  @override
  String get statusPendingUpload => 'Upload pending';

  @override
  String get statusReceived => 'Document received';

  @override
  String get statusDeleted => 'Exam deleted';

  @override
  String get statusFailed => 'Processing unsuccessful';

  @override
  String get statusUnknown => 'Status to be checked';

  @override
  String get typeBlood => 'Blood test';

  @override
  String get typeUrine => 'Urine test';

  @override
  String get typeImaging => 'Medical imaging';

  @override
  String get typePathology => 'Pathology';

  @override
  String get typeOther => 'Other document';

  @override
  String get extractionAwaiting => 'Awaiting your confirmation';

  @override
  String get extractionConfirmed => 'Data confirmed';

  @override
  String get extractionPreparing => 'Preparing proposal';

  @override
  String get extractionFailed => 'Information could not be extracted';

  @override
  String get extractionUnreadable => 'Unreadable document';

  @override
  String get extractionDiscarded => 'Proposal discarded';

  @override
  String get extractionRejected => 'Proposal not approved';

  @override
  String get extractionNotApplicable => 'No result proposal';

  @override
  String get uploadQueued => 'Queued for upload';

  @override
  String get uploadBytesPending => 'File pending';

  @override
  String get uploadCompletePending => 'Receipt pending';

  @override
  String get uploadVerified => 'Document verified';

  @override
  String get uploadRejected => 'Document rejected';

  @override
  String get uploadFailed => 'Processing failed';

  @override
  String get uploadConflict => 'Current status must be checked';

  @override
  String get pendingConflictHelp =>
      'Check status before continuing. Do not prepare another upload to resolve this conflict.';

  @override
  String get pendingProcessingHelp =>
      'The server received the upload. Check its status; you do not need to send it again.';

  @override
  String get pendingRejectedHelp =>
      'The server rejected the document. The local copy is kept; it is not resent automatically.';

  @override
  String get pendingFailedHelp =>
      'Processing failed. Check the details before preparing another operation.';

  @override
  String get pendingVerifiedHelp =>
      'Receipt was verified; open the exam to check its extraction and confirmation.';

  @override
  String get pendingHashHelp =>
      'The copy does not match its hash. It will not be sent; keep the original and review the operation.';

  @override
  String get pendingRetryHelp =>
      'Wait for the interval indicated by the server before explicitly retrying.';

  @override
  String get pendingInterruptedHelp =>
      'The last attempt did not finish. Check status, then explicitly retry; the upload identity is preserved.';

  @override
  String get pendingLocalHelp =>
      'Saved on this device only. Sending requires your explicit action.';

  @override
  String get errorExtractionNotReady =>
      'The document proposal is still being prepared. Check again.';

  @override
  String get errorOffline =>
      'No verified connection. Your operation is still pending.';

  @override
  String get errorSession =>
      'The session expired. Reconnect the synthetic profile.';

  @override
  String get errorStorageAuth =>
      'File authorization expired. Explicitly retry.';

  @override
  String get errorDenied => 'You do not have permission for this operation.';

  @override
  String get errorConflict =>
      'Conflict: check the current status before continuing.';

  @override
  String get errorValidation => 'Check the document fields and consent.';

  @override
  String get errorRateLimit => 'Temporary limit. Wait before retrying.';

  @override
  String get errorService =>
      'Service unavailable. Success has not been confirmed.';

  @override
  String get errorUnknown => 'The operation could not be completed.';

  @override
  String get operationInterrupted =>
      'Operation interrupted. Check the status before retrying.';

  @override
  String get sessionExpired => 'Session expired';

  @override
  String get accessUnauthorized => 'Access denied';

  @override
  String get verifying => 'Verifying';

  @override
  String get connected => 'Connected';

  @override
  String get connectionUnverified => 'No verified connection';

  @override
  String get dateUnavailable => 'Date unavailable';

  @override
  String get timeUnavailable => 'Time unavailable';

  @override
  String get referenceFinite =>
      'Check the reference limits: use finite numbers.';

  @override
  String get referenceOrder =>
      'The lower limit must be less than the upper limit.';

  @override
  String get markerFieldsRequired =>
      'Complete the value and unit of edited markers.';

  @override
  String get reviewDatesInvalid =>
      'Check the dates (YYYY-MM-DD). The API does not allow clearing an existing date.';

  @override
  String get referenceOriginal => 'Original reference';

  @override
  String get referenceRevised => 'Revised reference';

  @override
  String get withoutDate => 'no date';

  @override
  String get panelUnnamed => 'Unnamed panel';

  @override
  String get language => 'Language';

  @override
  String get languageHint => 'Saved on this device, even offline.';

  @override
  String get spanish => 'Español';

  @override
  String get english => 'English';

  @override
  String get languageSaveFailed =>
      'The language could not be saved. Try again.';

  @override
  String get loadingDocument => 'Loading document';

  @override
  String get lightTheme => 'Light theme';

  @override
  String get darkTheme => 'Dark theme';

  @override
  String currentViewCount(int count) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countString in the current view',
      one: '$countString in the current view',
    );
    return '$_temp0';
  }

  @override
  String localOperationsCount(int count) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countString local operations',
      one: '$countString local operation',
    );
    return '$_temp0';
  }

  @override
  String attemptCount(int count) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    return 'Upload attempts: $countString';
  }

  @override
  String pendingConnection(int count, String connection) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countString local pending operations',
      one: '1 local pending operation',
    );
    return '$_temp0 ? $connection';
  }

  @override
  String selectedPdf(int count) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    return 'PDF selected · $countString bytes';
  }

  @override
  String serverFilter(String status, String type) {
    return 'Server filter: $status · $type';
  }

  @override
  String resultCount(int visible, int loaded) {
    final intl.NumberFormat visibleNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String visibleString = visibleNumberFormat.format(visible);
    final intl.NumberFormat loadedNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String loadedString = loadedNumberFormat.format(loaded);

    return '$visibleString of $loadedString documents loaded for this query.';
  }

  @override
  String referenceDescription(
    String low,
    String high,
    String unit,
    String text,
  ) {
    return 'Document reference: $low – $high $unit $text';
  }

  @override
  String professionalReview(String status) {
    return 'Professional review: $status';
  }

  @override
  String fileName(String name) {
    return 'File: $name';
  }

  @override
  String fileSize(int count) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    return 'Size: $countString bytes';
  }

  @override
  String patientNotes(String notes) {
    return 'Your notes: $notes';
  }

  @override
  String currentServerState(String status) {
    return 'Current server status: $status. Review the current proposal before continuing.';
  }

  @override
  String sampleDate(String date) {
    return 'Sample date: $date';
  }

  @override
  String reportDate(String date) {
    return 'Report date: $date';
  }

  @override
  String confirmedOn(String date) {
    return 'Confirmed: $date';
  }

  @override
  String pagesCount(int count) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countString pages',
      one: '$countString page',
    );
    return '$_temp0';
  }

  @override
  String submissionSummary(String summary) {
    return '$summary\n\nOriginal → review. Human confirmation, without clinical validation.';
  }

  @override
  String get errorNotFound => 'Document not found.';

  @override
  String get queueSending => 'Sending operation';

  @override
  String get queueMissing => 'Private copy missing. The operation is kept.';

  @override
  String get queueIncomplete => 'Copy interrupted. Available data is kept.';

  @override
  String get queueCorrupt =>
      'The copy does not match its hash. It will not be sent.';

  @override
  String get queueUnreadable =>
      'Could not save or read the copy. The operation is kept.';

  @override
  String get queueVerifying => 'Verifying receipt on the server';

  @override
  String get queueWaitingConnection => 'Waiting for a verified connection';

  @override
  String get queuePaused => 'Upload paused. An action is required to continue.';

  @override
  String get queueAwaitingAuthorization =>
      'Saved locally. Waiting for permission to send.';

  @override
  String get queueReadyToResume => 'Ready to resume with your permission.';

  @override
  String queueRetryAfter(String date, String time) {
    return 'Recoverable error. You can retry from $date, $time.';
  }

  @override
  String get queuePause => 'Pause upload';
}
