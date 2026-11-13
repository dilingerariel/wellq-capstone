// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Spanish Castilian (`es`).
class AppLocalizationsEs extends AppLocalizations {
  AppLocalizationsEs([String locale = 'es']) : super(locale);

  @override
  String get syntheticWarning => 'Solo datos sintéticos • Sin uso clínico';

  @override
  String get syntheticEnvironment => 'Entorno sintético';

  @override
  String get syntheticNoClinical => 'Entorno sintético · Sin uso clínico';

  @override
  String get noClinicalUse => 'Sin uso clínico';

  @override
  String get productionBlocked =>
      'WellQ: modo productivo bloqueado. Solo debug con datos sinteticos.';

  @override
  String get home => 'Inicio';

  @override
  String get exams => 'Exámenes';

  @override
  String get upload => 'Cargar';

  @override
  String get pending => 'Pendientes';

  @override
  String get settings => 'Ajustes';

  @override
  String get docsCaption => 'Docs.';

  @override
  String get queueCaption => 'Cola';

  @override
  String get changeTheme => 'Cambiar tema';

  @override
  String get refreshReadings => 'Actualizar lecturas';

  @override
  String get checkConnection => 'Comprobar conexión';

  @override
  String get welcomeTitle => 'Tu salud, en orden';

  @override
  String get welcomeSubtitle => 'Conecta el perfil de prueba para continuar.';

  @override
  String get welcomeQueue =>
      'Tu cola local se conserva. Después de reiniciar necesitas verificar el mismo perfil para abrirla.';

  @override
  String get connectSynthetic => 'Conectar paciente sintético';

  @override
  String get welcomeRequires =>
      'Requiere WellQ disponible. Solo datos sintéticos; sin uso clínico.';

  @override
  String get helloPatient => 'Hola, paciente';

  @override
  String get documentsAtHand => 'Tus documentos, a mano.';

  @override
  String get uploadDocument => 'Cargar documento';

  @override
  String get myExams => 'Mis exámenes';

  @override
  String get pendingUploads => 'Pendientes de envío';

  @override
  String get recentExams => 'Exámenes recientes en esta vista';

  @override
  String get noExamsYet =>
      'Aún no hay exámenes. Carga el documento sintético para comenzar.';

  @override
  String get openExamHint =>
      'Abre un examen para consultar si requiere tu confirmación.';

  @override
  String get viewMyExams => 'Ver mis exámenes';

  @override
  String get untitledExam => 'Examen sin título';

  @override
  String get pendingOperations => 'Operaciones pendientes';

  @override
  String get pendingSubtitle =>
      'Tus documentos guardados. Tú decides cuándo enviarlos.';

  @override
  String get checkStatesConnection => 'Consultar estados y conexión';

  @override
  String get noLocalOperations =>
      'Sin operaciones locales. Puedes preparar un documento aunque se interrumpa la red.';

  @override
  String get verifiedLocalCopy =>
      'Documento verificado. La copia local se conserva.';

  @override
  String get sendDocument => 'Enviar documento';

  @override
  String get retryUpload => 'Reintentar envío';

  @override
  String get openExamExtraction => 'Abrir examen y extracción';

  @override
  String get yourSpace => 'Tu espacio';

  @override
  String get appPreferences => 'Preferencias de la aplicación.';

  @override
  String get changeAppearance => 'Cambiar tema claro / oscuro';

  @override
  String get patientSession => 'Sesión de paciente';

  @override
  String get renewPatientSession => 'Renovar sesión y consultar estados';

  @override
  String get demoAccessCode => 'Código de acceso de demostración';

  @override
  String get demoAccessHelp =>
      'Acceso sintético temporal. No es un OTP ni una identidad productiva.';

  @override
  String get syntheticProfile =>
      'Perfil sintético de desarrollo. Sin uso clínico.';

  @override
  String get syncStatus => 'Estado de sincronización';

  @override
  String get developmentInfo => 'Información de desarrollo';

  @override
  String get syntheticIdentity => 'Identidad sintética';

  @override
  String get tokensRam => 'Tokens en RAM; firma RS256 solo en el host.';

  @override
  String get testPersistence => 'Persistencia de pruebas';

  @override
  String get syntheticDrift =>
      'Drift/SQLite sin datos clínicos reales. Solo PDF sintético verificado.';

  @override
  String get productionPdfBlocked => 'PDF productivo bloqueado';

  @override
  String get noProductionProviders =>
      'Sin exportaciones, scores ni proveedores productivos.';

  @override
  String get logoutQuestion => '¿Cerrar sesión?';

  @override
  String get logoutWarning =>
      'Se cerrar? el acceso y se limpiar? la cach?. La cola y los archivos privados se conservan para esta identidad.';

  @override
  String get logout => 'Cerrar sesión';

  @override
  String get newDocument => 'Nuevo documento';

  @override
  String get syntheticPdfOnly =>
      'Selecciona un PDF sintético de prueba o usa el ejemplo incluido. No selecciones documentos médicos reales.';

  @override
  String get useTestPdf => 'Usar PDF de prueba';

  @override
  String get selectTestPdf => 'Seleccionar PDF de prueba';

  @override
  String get viewDocument => 'Ver documento';

  @override
  String get documentTitle => 'Título del documento';

  @override
  String get examDate => 'Fecha del examen';

  @override
  String get isoDateHint => 'AAAA-MM-DD';

  @override
  String get examDateHint =>
      'Fecha registrada del examen; puede diferir de la fecha de muestra del PDF.';

  @override
  String get confirmSyntheticOnly => 'Confirmo que solo uso datos sintéticos.';

  @override
  String get authorizeSyntheticProcessing =>
      'Autorizo el procesamiento sintético del documento.';

  @override
  String get savePending => 'Guardar en pendientes';

  @override
  String get saveDoesNotSend =>
      'Guardar no envía el archivo ni elimina el original.';

  @override
  String get fileTooLarge => 'El archivo excede 20 MiB.';

  @override
  String get syntheticIntegrityOnly =>
      'PDF inválido, incompleto o con integridad incorrecta. Selecciona un PDF sintético válido sin modificar su copia guardada.';

  @override
  String get pickerUnavailable =>
      'No se pudo abrir el selector. Puedes usar el PDF sintético incluido.';

  @override
  String get operationNotSaved => 'No se guardó la operación.';

  @override
  String get back => 'Volver';

  @override
  String get confirmAction => 'Confirmar acción';

  @override
  String get documentsStatusSubtitle => 'Tus documentos y su estado actual.';

  @override
  String get lastAvailableReading =>
      'Última lectura disponible. No confirma cambios del servidor.';

  @override
  String get searchScope =>
      'Búsqueda y orden: documentos cargados. Estado y tipo: servidor.';

  @override
  String get searchLoadedTitles => 'Buscar en títulos cargados';

  @override
  String get clearSearch => 'Limpiar búsqueda';

  @override
  String get filterSort => 'Filtrar y ordenar';

  @override
  String get serverStatus => 'Estado en el servidor';

  @override
  String get all => 'Todos';

  @override
  String get serverType => 'Tipo en el servidor';

  @override
  String get removeServerFilters => 'Quitar filtros del servidor';

  @override
  String get loadedDocumentOrder => 'Orden de documentos cargados';

  @override
  String get newestFirst => 'Más recientes';

  @override
  String get oldestFirst => 'Más antiguos';

  @override
  String get allStatuses => 'todos los estados';

  @override
  String get allTypes => 'todos los tipos';

  @override
  String get noMatches =>
      'Sin coincidencias entre los documentos cargados. Puedes cargar más páginas o cambiar la búsqueda.';

  @override
  String get noReading =>
      'No hay una lectura disponible. Verifica la conexión y consulta nuevamente.';

  @override
  String get noFilteredDocuments =>
      'No hay documentos para estos filtros. Puedes quitarlos o actualizar.';

  @override
  String get noExamsView =>
      'Sin exámenes en esta vista. Actualiza o carga el PDF sintético.';

  @override
  String get morePagesHint =>
      'Hay más páginas del servidor; aún no se buscaron sus títulos.';

  @override
  String get loadMore => 'Cargar más';

  @override
  String get refreshList => 'Actualizar listado';

  @override
  String get examDetail => 'Detalle del examen';

  @override
  String get reviewCompleted => 'completada';

  @override
  String get reviewPendingUnknown => 'pendiente o no informada';

  @override
  String get stillProcessing =>
      'El documento aún no termina de procesarse. Consulta el estado; no necesitas cargarlo otra vez.';

  @override
  String get documentCannotConfirm =>
      'Este documento no está disponible para confirmar. Se conserva la copia local; consulta el estado antes de preparar otro.';

  @override
  String get noVerifiedCopy =>
      'No hay una copia sintética verificada en este dispositivo. No se descargan documentos arbitrarios.';

  @override
  String get extractionUnavailable =>
      'La extracción aún no está disponible. Consulta nuevamente.';

  @override
  String get examUnavailable =>
      'El examen no está disponible o ya no existe en esta vista.';

  @override
  String get proposalReadFailed =>
      'No se pudo leer la propuesta. Consulta nuevamente.';

  @override
  String get discardQuestion => '¿Descartar propuesta?';

  @override
  String get reviewConfirmation => 'Revisar confirmación';

  @override
  String get discardWarning =>
      'Se descartará esta propuesta. No se elimina el documento.';

  @override
  String get lowConfidenceHint =>
      'Baja confianza: coteja este marcador con el documento original.';

  @override
  String get valueLabel => 'Valor';

  @override
  String get unitLabel => 'Unidad';

  @override
  String get documentReference => 'Referencia del documento';

  @override
  String get lowerLimit => 'Límite inferior';

  @override
  String get upperLimit => 'Límite superior';

  @override
  String get referenceUnit => 'Unidad de referencia';

  @override
  String get referenceText => 'Texto de referencia';

  @override
  String get compareProposal =>
      'Coteja la propuesta con el PDF sintético original. No es un diagnóstico.';

  @override
  String get confirmationReceived =>
      'La confirmación ya fue recibida. Puede faltar la revisión profesional.';

  @override
  String get noNewConfirmation =>
      'Consulta el estado del examen. No se requiere una nueva confirmación.';

  @override
  String get documentDates => 'Fechas del documento';

  @override
  String get collectionDateLabel => 'Fecha de muestra';

  @override
  String get reportDateLabel => 'Fecha de informe';

  @override
  String get identityAcknowledgement =>
      'He comprobado que este documento me corresponde.';

  @override
  String get valuesAcknowledgement =>
      'He cotejado valores, unidades y campos de baja confianza.';

  @override
  String get reviewConfirm => 'Revisar y confirmar';

  @override
  String get retrySameSubmission => 'Reintentar el mismo envío';

  @override
  String get discardProposal => 'Descartar propuesta';

  @override
  String get serverDeterminesStatus =>
      'Estado determinado por FastAPI. No equivale a validación profesional.';

  @override
  String get checkCurrentQuestion => '¿Consultar estado actual?';

  @override
  String get checkCurrentWarning =>
      'Se descartará el borrador y se consultará la propuesta vigente. No se reenviará ninguna mutación.';

  @override
  String get checkCurrentProposal => 'Consultar propuesta actual';

  @override
  String get syntheticDocument => 'Documento sintético';

  @override
  String get zoomOut => 'Alejar documento';

  @override
  String get zoomIn => 'Acercar documento';

  @override
  String get pdfOpenFailed =>
      'No se puede abrir el documento: falta el archivo o su integridad no coincide.';

  @override
  String get pdfRenderFailed => 'No se pudo representar el PDF sintético.';

  @override
  String get statusReviewed => 'Con revisión profesional';

  @override
  String get statusReady => 'Pendiente de revisión profesional';

  @override
  String get statusValidated => 'Revisión profesional completada';

  @override
  String get statusRejected => 'Revisión no aprobada';

  @override
  String get statusProcessing => 'Procesando documento';

  @override
  String get statusPendingUpload => 'Carga pendiente';

  @override
  String get statusReceived => 'Documento recibido';

  @override
  String get statusDeleted => 'Examen eliminado';

  @override
  String get statusFailed => 'No se pudo procesar';

  @override
  String get statusUnknown => 'Estado por consultar';

  @override
  String get typeBlood => 'Examen de sangre';

  @override
  String get typeUrine => 'Examen de orina';

  @override
  String get typeImaging => 'Imagen médica';

  @override
  String get typePathology => 'Anatomía patológica';

  @override
  String get typeOther => 'Otro documento';

  @override
  String get extractionAwaiting => 'Esperando tu confirmación';

  @override
  String get extractionConfirmed => 'Datos confirmados';

  @override
  String get extractionPreparing => 'Preparando propuesta';

  @override
  String get extractionFailed => 'No se pudo extraer la información';

  @override
  String get extractionUnreadable => 'Documento ilegible';

  @override
  String get extractionDiscarded => 'Propuesta descartada';

  @override
  String get extractionRejected => 'Propuesta no aprobada';

  @override
  String get extractionNotApplicable => 'Sin propuesta de resultados';

  @override
  String get uploadQueued => 'Pendiente de envío';

  @override
  String get uploadBytesPending => 'Archivo pendiente';

  @override
  String get uploadCompletePending => 'Recepción pendiente';

  @override
  String get uploadVerified => 'Documento verificado';

  @override
  String get uploadRejected => 'Documento rechazado';

  @override
  String get uploadFailed => 'Procesamiento fallido';

  @override
  String get uploadConflict => 'Requiere revisar el estado actual';

  @override
  String get pendingConflictHelp =>
      'Consulta estados antes de continuar. No prepares otra carga para resolver este conflicto.';

  @override
  String get pendingProcessingHelp =>
      'El servidor recibió la carga. Consulta estados; no necesitas enviarla otra vez.';

  @override
  String get pendingRejectedHelp =>
      'El servidor rechazó el documento. La copia local se conserva; no se reenvía automáticamente.';

  @override
  String get pendingFailedHelp =>
      'El procesamiento falló. Consulta el detalle antes de preparar otra operación.';

  @override
  String get pendingVerifiedHelp =>
      'La recepción fue verificada; abre el examen para consultar su extracción y confirmación.';

  @override
  String get pendingHashHelp =>
      'La copia no coincide con su hash. No se enviará; conserva el original y revisa la operación.';

  @override
  String get pendingRetryHelp =>
      'Espera el intervalo indicado por el servidor antes de reintentar explícitamente.';

  @override
  String get pendingInterruptedHelp =>
      'El último intento no terminó. Consulta estados y luego reintenta explícitamente; se conserva la identidad de la carga.';

  @override
  String get pendingLocalHelp =>
      'Guardado solo en este dispositivo. El envío requiere tu acción explícita.';

  @override
  String get errorExtractionNotReady =>
      'El documento sigue preparando la propuesta. Consulta nuevamente.';

  @override
  String get errorOffline =>
      'Sin conexión verificada. Tu operación sigue pendiente.';

  @override
  String get errorSession =>
      'La sesión venció. Vuelve a conectar el perfil sintético.';

  @override
  String get errorStorageAuth =>
      'Autorización del archivo vencida. Reintenta explícitamente.';

  @override
  String get errorDenied => 'No tienes permiso para esta operación.';

  @override
  String get errorConflict =>
      'Conflicto: consulta el estado actual antes de continuar.';

  @override
  String get errorValidation =>
      'Revisa los campos y el consentimiento del documento.';

  @override
  String get errorRateLimit => 'Límite temporal. Espera antes de reintentar.';

  @override
  String get errorService =>
      'Servicio no disponible. No se ha confirmado éxito.';

  @override
  String get errorUnknown => 'No se pudo completar la operación.';

  @override
  String get operationInterrupted =>
      'Operación interrumpida. Consulta el estado antes de reintentar.';

  @override
  String get sessionExpired => 'Sesión expirada';

  @override
  String get accessUnauthorized => 'Acceso no autorizado';

  @override
  String get verifying => 'Verificando';

  @override
  String get connected => 'Conectado';

  @override
  String get connectionUnverified => 'Sin conexión verificada';

  @override
  String get dateUnavailable => 'Fecha no disponible';

  @override
  String get timeUnavailable => 'Hora no disponible';

  @override
  String get referenceFinite =>
      'Revisa los límites de referencia: usa números finitos.';

  @override
  String get referenceOrder =>
      'El límite inferior debe ser menor que el superior.';

  @override
  String get markerFieldsRequired =>
      'Completa valor y unidad de los marcadores editados.';

  @override
  String get reviewDatesInvalid =>
      'Revisa las fechas (AAAA-MM-DD). La API no permite vaciar una fecha existente.';

  @override
  String get referenceOriginal => 'Referencia original';

  @override
  String get referenceRevised => 'Referencia revisada';

  @override
  String get withoutDate => 'sin fecha';

  @override
  String get panelUnnamed => 'Panel sin nombre';

  @override
  String get language => 'Idioma';

  @override
  String get languageHint =>
      'Se guarda en este dispositivo, incluso sin conexión.';

  @override
  String get spanish => 'Español';

  @override
  String get english => 'English';

  @override
  String get languageSaveFailed =>
      'No se pudo guardar el idioma. Inténtalo nuevamente.';

  @override
  String get loadingDocument => 'Cargando documento';

  @override
  String get lightTheme => 'Tema claro';

  @override
  String get darkTheme => 'Tema oscuro';

  @override
  String currentViewCount(int count) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countString en la vista actual',
      one: '$countString en la vista actual',
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
      other: '$countString operaciones locales',
      one: '$countString operación local',
    );
    return '$_temp0';
  }

  @override
  String attemptCount(int count) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    return 'Intentos de envío: $countString';
  }

  @override
  String pendingConnection(int count, String connection) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countString pendientes locales',
      one: '1 pendiente local',
    );
    return '$_temp0 ? $connection';
  }

  @override
  String selectedPdf(int count) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    return 'PDF seleccionado · $countString bytes';
  }

  @override
  String serverFilter(String status, String type) {
    return 'Filtro del servidor: $status · $type';
  }

  @override
  String resultCount(int visible, int loaded) {
    final intl.NumberFormat visibleNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String visibleString = visibleNumberFormat.format(visible);
    final intl.NumberFormat loadedNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String loadedString = loadedNumberFormat.format(loaded);

    return '$visibleString de $loadedString documentos cargados en esta consulta.';
  }

  @override
  String referenceDescription(
    String low,
    String high,
    String unit,
    String text,
  ) {
    return 'Referencia del documento: $low – $high $unit $text';
  }

  @override
  String professionalReview(String status) {
    return 'Revisión profesional: $status';
  }

  @override
  String fileName(String name) {
    return 'Archivo: $name';
  }

  @override
  String fileSize(int count) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    return 'Tamaño: $countString bytes';
  }

  @override
  String patientNotes(String notes) {
    return 'Tus notas: $notes';
  }

  @override
  String currentServerState(String status) {
    return 'Estado actual del servidor: $status. Revisa la propuesta actual antes de continuar.';
  }

  @override
  String sampleDate(String date) {
    return 'Fecha de muestra: $date';
  }

  @override
  String reportDate(String date) {
    return 'Fecha de informe: $date';
  }

  @override
  String confirmedOn(String date) {
    return 'Confirmado: $date';
  }

  @override
  String pagesCount(int count) {
    final intl.NumberFormat countNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String countString = countNumberFormat.format(count);

    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countString páginas',
      one: '$countString página',
    );
    return '$_temp0';
  }

  @override
  String submissionSummary(String summary) {
    return '$summary\n\nOriginal → revisión. Confirmación humana, sin validación clínica.';
  }

  @override
  String get errorNotFound => 'Documento no encontrado.';

  @override
  String get queueSending => 'Enviando operaci?n';

  @override
  String get queueMissing =>
      'Falta la copia privada. La operaci?n se conserva.';

  @override
  String get queueIncomplete =>
      'Copia interrumpida. Los datos disponibles se conservan.';

  @override
  String get queueCorrupt =>
      'La copia no coincide con su huella. No se enviar?.';

  @override
  String get queueUnreadable =>
      'No se pudo guardar o leer la copia. La operaci?n se conserva.';

  @override
  String get queueVerifying => 'Verificando recepci?n en el servidor';

  @override
  String get queueWaitingConnection => 'Esperando conexi?n verificada';

  @override
  String get queuePaused =>
      'Env?o pausado. Se requiere una acci?n para continuar.';

  @override
  String get queueAwaitingAuthorization =>
      'Guardado localmente. Esperando autorizaci?n de env?o.';

  @override
  String get queueReadyToResume =>
      'Preparado para reanudar con tu autorizaci?n.';

  @override
  String queueRetryAfter(String date, String time) {
    return 'Error recuperable. Puedes reintentar a partir de $date, $time.';
  }

  @override
  String get queuePause => 'Pausar env?o';
}
