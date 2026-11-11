import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_es.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('es'),
  ];

  /// No description provided for @syntheticWarning.
  ///
  /// In es, this message translates to:
  /// **'Solo datos sintéticos • Sin uso clínico'**
  String get syntheticWarning;

  /// No description provided for @syntheticEnvironment.
  ///
  /// In es, this message translates to:
  /// **'Entorno sintético'**
  String get syntheticEnvironment;

  /// No description provided for @syntheticNoClinical.
  ///
  /// In es, this message translates to:
  /// **'Entorno sintético · Sin uso clínico'**
  String get syntheticNoClinical;

  /// No description provided for @noClinicalUse.
  ///
  /// In es, this message translates to:
  /// **'Sin uso clínico'**
  String get noClinicalUse;

  /// No description provided for @productionBlocked.
  ///
  /// In es, this message translates to:
  /// **'WellQ: modo productivo bloqueado. Solo debug con datos sinteticos.'**
  String get productionBlocked;

  /// No description provided for @home.
  ///
  /// In es, this message translates to:
  /// **'Inicio'**
  String get home;

  /// No description provided for @exams.
  ///
  /// In es, this message translates to:
  /// **'Exámenes'**
  String get exams;

  /// No description provided for @upload.
  ///
  /// In es, this message translates to:
  /// **'Cargar'**
  String get upload;

  /// No description provided for @pending.
  ///
  /// In es, this message translates to:
  /// **'Pendientes'**
  String get pending;

  /// No description provided for @settings.
  ///
  /// In es, this message translates to:
  /// **'Ajustes'**
  String get settings;

  /// No description provided for @docsCaption.
  ///
  /// In es, this message translates to:
  /// **'Docs.'**
  String get docsCaption;

  /// No description provided for @queueCaption.
  ///
  /// In es, this message translates to:
  /// **'Cola'**
  String get queueCaption;

  /// No description provided for @changeTheme.
  ///
  /// In es, this message translates to:
  /// **'Cambiar tema'**
  String get changeTheme;

  /// No description provided for @refreshReadings.
  ///
  /// In es, this message translates to:
  /// **'Actualizar lecturas'**
  String get refreshReadings;

  /// No description provided for @checkConnection.
  ///
  /// In es, this message translates to:
  /// **'Comprobar conexión'**
  String get checkConnection;

  /// No description provided for @welcomeTitle.
  ///
  /// In es, this message translates to:
  /// **'Tu salud, en orden'**
  String get welcomeTitle;

  /// No description provided for @welcomeSubtitle.
  ///
  /// In es, this message translates to:
  /// **'Conecta el perfil de prueba para continuar.'**
  String get welcomeSubtitle;

  /// No description provided for @welcomeQueue.
  ///
  /// In es, this message translates to:
  /// **'Tu cola local se conserva. Después de reiniciar necesitas verificar el mismo perfil para abrirla.'**
  String get welcomeQueue;

  /// No description provided for @connectSynthetic.
  ///
  /// In es, this message translates to:
  /// **'Conectar paciente sintético'**
  String get connectSynthetic;

  /// No description provided for @welcomeRequires.
  ///
  /// In es, this message translates to:
  /// **'Requiere WellQ disponible. Solo datos sintéticos; sin uso clínico.'**
  String get welcomeRequires;

  /// No description provided for @helloPatient.
  ///
  /// In es, this message translates to:
  /// **'Hola, paciente'**
  String get helloPatient;

  /// No description provided for @documentsAtHand.
  ///
  /// In es, this message translates to:
  /// **'Tus documentos, a mano.'**
  String get documentsAtHand;

  /// No description provided for @uploadDocument.
  ///
  /// In es, this message translates to:
  /// **'Cargar documento'**
  String get uploadDocument;

  /// No description provided for @myExams.
  ///
  /// In es, this message translates to:
  /// **'Mis exámenes'**
  String get myExams;

  /// No description provided for @pendingUploads.
  ///
  /// In es, this message translates to:
  /// **'Pendientes de envío'**
  String get pendingUploads;

  /// No description provided for @recentExams.
  ///
  /// In es, this message translates to:
  /// **'Exámenes recientes en esta vista'**
  String get recentExams;

  /// No description provided for @noExamsYet.
  ///
  /// In es, this message translates to:
  /// **'Aún no hay exámenes. Carga el documento sintético para comenzar.'**
  String get noExamsYet;

  /// No description provided for @openExamHint.
  ///
  /// In es, this message translates to:
  /// **'Abre un examen para consultar si requiere tu confirmación.'**
  String get openExamHint;

  /// No description provided for @viewMyExams.
  ///
  /// In es, this message translates to:
  /// **'Ver mis exámenes'**
  String get viewMyExams;

  /// No description provided for @untitledExam.
  ///
  /// In es, this message translates to:
  /// **'Examen sin título'**
  String get untitledExam;

  /// No description provided for @pendingOperations.
  ///
  /// In es, this message translates to:
  /// **'Operaciones pendientes'**
  String get pendingOperations;

  /// No description provided for @pendingSubtitle.
  ///
  /// In es, this message translates to:
  /// **'Tus documentos guardados. Tú decides cuándo enviarlos.'**
  String get pendingSubtitle;

  /// No description provided for @checkStatesConnection.
  ///
  /// In es, this message translates to:
  /// **'Consultar estados y conexión'**
  String get checkStatesConnection;

  /// No description provided for @noLocalOperations.
  ///
  /// In es, this message translates to:
  /// **'Sin operaciones locales. Puedes preparar un documento aunque se interrumpa la red.'**
  String get noLocalOperations;

  /// No description provided for @verifiedLocalCopy.
  ///
  /// In es, this message translates to:
  /// **'Documento verificado. La copia local se conserva.'**
  String get verifiedLocalCopy;

  /// No description provided for @sendDocument.
  ///
  /// In es, this message translates to:
  /// **'Enviar documento'**
  String get sendDocument;

  /// No description provided for @retryUpload.
  ///
  /// In es, this message translates to:
  /// **'Reintentar envío'**
  String get retryUpload;

  /// No description provided for @openExamExtraction.
  ///
  /// In es, this message translates to:
  /// **'Abrir examen y extracción'**
  String get openExamExtraction;

  /// No description provided for @yourSpace.
  ///
  /// In es, this message translates to:
  /// **'Tu espacio'**
  String get yourSpace;

  /// No description provided for @appPreferences.
  ///
  /// In es, this message translates to:
  /// **'Preferencias de la aplicación.'**
  String get appPreferences;

  /// No description provided for @changeAppearance.
  ///
  /// In es, this message translates to:
  /// **'Cambiar tema claro / oscuro'**
  String get changeAppearance;

  /// No description provided for @patientSession.
  ///
  /// In es, this message translates to:
  /// **'Sesión de paciente'**
  String get patientSession;

  /// No description provided for @syntheticProfile.
  ///
  /// In es, this message translates to:
  /// **'Perfil sintético de desarrollo. Sin uso clínico.'**
  String get syntheticProfile;

  /// No description provided for @syncStatus.
  ///
  /// In es, this message translates to:
  /// **'Estado de sincronización'**
  String get syncStatus;

  /// No description provided for @developmentInfo.
  ///
  /// In es, this message translates to:
  /// **'Información de desarrollo'**
  String get developmentInfo;

  /// No description provided for @syntheticIdentity.
  ///
  /// In es, this message translates to:
  /// **'Identidad sintética'**
  String get syntheticIdentity;

  /// No description provided for @tokensRam.
  ///
  /// In es, this message translates to:
  /// **'Tokens en RAM; firma RS256 solo en el host.'**
  String get tokensRam;

  /// No description provided for @testPersistence.
  ///
  /// In es, this message translates to:
  /// **'Persistencia de pruebas'**
  String get testPersistence;

  /// No description provided for @syntheticDrift.
  ///
  /// In es, this message translates to:
  /// **'Drift/SQLite sin datos clínicos reales. Solo PDF sintético verificado.'**
  String get syntheticDrift;

  /// No description provided for @productionPdfBlocked.
  ///
  /// In es, this message translates to:
  /// **'PDF productivo bloqueado'**
  String get productionPdfBlocked;

  /// No description provided for @noProductionProviders.
  ///
  /// In es, this message translates to:
  /// **'Sin exportaciones, scores ni proveedores productivos.'**
  String get noProductionProviders;

  /// No description provided for @logoutQuestion.
  ///
  /// In es, this message translates to:
  /// **'¿Cerrar sesión?'**
  String get logoutQuestion;

  /// No description provided for @logoutWarning.
  ///
  /// In es, this message translates to:
  /// **'Se cerrar? el acceso y se limpiar? la cach?. La cola y los archivos privados se conservan para esta identidad.'**
  String get logoutWarning;

  /// No description provided for @logout.
  ///
  /// In es, this message translates to:
  /// **'Cerrar sesión'**
  String get logout;

  /// No description provided for @newDocument.
  ///
  /// In es, this message translates to:
  /// **'Nuevo documento'**
  String get newDocument;

  /// No description provided for @syntheticPdfOnly.
  ///
  /// In es, this message translates to:
  /// **'Usa el PDF sintético de prueba. No selecciones documentos médicos reales.'**
  String get syntheticPdfOnly;

  /// No description provided for @useTestPdf.
  ///
  /// In es, this message translates to:
  /// **'Usar PDF de prueba'**
  String get useTestPdf;

  /// No description provided for @selectTestPdf.
  ///
  /// In es, this message translates to:
  /// **'Seleccionar PDF de prueba'**
  String get selectTestPdf;

  /// No description provided for @viewDocument.
  ///
  /// In es, this message translates to:
  /// **'Ver documento'**
  String get viewDocument;

  /// No description provided for @documentTitle.
  ///
  /// In es, this message translates to:
  /// **'Título del documento'**
  String get documentTitle;

  /// No description provided for @examDate.
  ///
  /// In es, this message translates to:
  /// **'Fecha del examen'**
  String get examDate;

  /// No description provided for @isoDateHint.
  ///
  /// In es, this message translates to:
  /// **'AAAA-MM-DD'**
  String get isoDateHint;

  /// No description provided for @examDateHint.
  ///
  /// In es, this message translates to:
  /// **'Fecha registrada del examen; puede diferir de la fecha de muestra del PDF.'**
  String get examDateHint;

  /// No description provided for @confirmSyntheticOnly.
  ///
  /// In es, this message translates to:
  /// **'Confirmo que solo uso datos sintéticos.'**
  String get confirmSyntheticOnly;

  /// No description provided for @authorizeSyntheticProcessing.
  ///
  /// In es, this message translates to:
  /// **'Autorizo el procesamiento sintético del documento.'**
  String get authorizeSyntheticProcessing;

  /// No description provided for @savePending.
  ///
  /// In es, this message translates to:
  /// **'Guardar en pendientes'**
  String get savePending;

  /// No description provided for @saveDoesNotSend.
  ///
  /// In es, this message translates to:
  /// **'Guardar no envía el archivo ni elimina el original.'**
  String get saveDoesNotSend;

  /// No description provided for @fileTooLarge.
  ///
  /// In es, this message translates to:
  /// **'El archivo excede 20 MiB.'**
  String get fileTooLarge;

  /// No description provided for @syntheticIntegrityOnly.
  ///
  /// In es, this message translates to:
  /// **'Solo se admite una copia íntegra del PDF sintético incluido.'**
  String get syntheticIntegrityOnly;

  /// No description provided for @pickerUnavailable.
  ///
  /// In es, this message translates to:
  /// **'No se pudo abrir el selector. Puedes usar el PDF sintético incluido.'**
  String get pickerUnavailable;

  /// No description provided for @operationNotSaved.
  ///
  /// In es, this message translates to:
  /// **'No se guardó la operación.'**
  String get operationNotSaved;

  /// No description provided for @back.
  ///
  /// In es, this message translates to:
  /// **'Volver'**
  String get back;

  /// No description provided for @confirmAction.
  ///
  /// In es, this message translates to:
  /// **'Confirmar acción'**
  String get confirmAction;

  /// No description provided for @documentsStatusSubtitle.
  ///
  /// In es, this message translates to:
  /// **'Tus documentos y su estado actual.'**
  String get documentsStatusSubtitle;

  /// No description provided for @lastAvailableReading.
  ///
  /// In es, this message translates to:
  /// **'Última lectura disponible. No confirma cambios del servidor.'**
  String get lastAvailableReading;

  /// No description provided for @searchScope.
  ///
  /// In es, this message translates to:
  /// **'Búsqueda y orden: documentos cargados. Estado y tipo: servidor.'**
  String get searchScope;

  /// No description provided for @searchLoadedTitles.
  ///
  /// In es, this message translates to:
  /// **'Buscar en títulos cargados'**
  String get searchLoadedTitles;

  /// No description provided for @clearSearch.
  ///
  /// In es, this message translates to:
  /// **'Limpiar búsqueda'**
  String get clearSearch;

  /// No description provided for @filterSort.
  ///
  /// In es, this message translates to:
  /// **'Filtrar y ordenar'**
  String get filterSort;

  /// No description provided for @serverStatus.
  ///
  /// In es, this message translates to:
  /// **'Estado en el servidor'**
  String get serverStatus;

  /// No description provided for @all.
  ///
  /// In es, this message translates to:
  /// **'Todos'**
  String get all;

  /// No description provided for @serverType.
  ///
  /// In es, this message translates to:
  /// **'Tipo en el servidor'**
  String get serverType;

  /// No description provided for @removeServerFilters.
  ///
  /// In es, this message translates to:
  /// **'Quitar filtros del servidor'**
  String get removeServerFilters;

  /// No description provided for @loadedDocumentOrder.
  ///
  /// In es, this message translates to:
  /// **'Orden de documentos cargados'**
  String get loadedDocumentOrder;

  /// No description provided for @newestFirst.
  ///
  /// In es, this message translates to:
  /// **'Más recientes'**
  String get newestFirst;

  /// No description provided for @oldestFirst.
  ///
  /// In es, this message translates to:
  /// **'Más antiguos'**
  String get oldestFirst;

  /// No description provided for @allStatuses.
  ///
  /// In es, this message translates to:
  /// **'todos los estados'**
  String get allStatuses;

  /// No description provided for @allTypes.
  ///
  /// In es, this message translates to:
  /// **'todos los tipos'**
  String get allTypes;

  /// No description provided for @noMatches.
  ///
  /// In es, this message translates to:
  /// **'Sin coincidencias entre los documentos cargados. Puedes cargar más páginas o cambiar la búsqueda.'**
  String get noMatches;

  /// No description provided for @noReading.
  ///
  /// In es, this message translates to:
  /// **'No hay una lectura disponible. Verifica la conexión y consulta nuevamente.'**
  String get noReading;

  /// No description provided for @noFilteredDocuments.
  ///
  /// In es, this message translates to:
  /// **'No hay documentos para estos filtros. Puedes quitarlos o actualizar.'**
  String get noFilteredDocuments;

  /// No description provided for @noExamsView.
  ///
  /// In es, this message translates to:
  /// **'Sin exámenes en esta vista. Actualiza o carga el PDF sintético.'**
  String get noExamsView;

  /// No description provided for @morePagesHint.
  ///
  /// In es, this message translates to:
  /// **'Hay más páginas del servidor; aún no se buscaron sus títulos.'**
  String get morePagesHint;

  /// No description provided for @loadMore.
  ///
  /// In es, this message translates to:
  /// **'Cargar más'**
  String get loadMore;

  /// No description provided for @refreshList.
  ///
  /// In es, this message translates to:
  /// **'Actualizar listado'**
  String get refreshList;

  /// No description provided for @examDetail.
  ///
  /// In es, this message translates to:
  /// **'Detalle del examen'**
  String get examDetail;

  /// No description provided for @reviewCompleted.
  ///
  /// In es, this message translates to:
  /// **'completada'**
  String get reviewCompleted;

  /// No description provided for @reviewPendingUnknown.
  ///
  /// In es, this message translates to:
  /// **'pendiente o no informada'**
  String get reviewPendingUnknown;

  /// No description provided for @stillProcessing.
  ///
  /// In es, this message translates to:
  /// **'El documento aún no termina de procesarse. Consulta el estado; no necesitas cargarlo otra vez.'**
  String get stillProcessing;

  /// No description provided for @documentCannotConfirm.
  ///
  /// In es, this message translates to:
  /// **'Este documento no está disponible para confirmar. Se conserva la copia local; consulta el estado antes de preparar otro.'**
  String get documentCannotConfirm;

  /// No description provided for @noVerifiedCopy.
  ///
  /// In es, this message translates to:
  /// **'No hay una copia sintética verificada en este dispositivo. No se descargan documentos arbitrarios.'**
  String get noVerifiedCopy;

  /// No description provided for @extractionUnavailable.
  ///
  /// In es, this message translates to:
  /// **'La extracción aún no está disponible. Consulta nuevamente.'**
  String get extractionUnavailable;

  /// No description provided for @examUnavailable.
  ///
  /// In es, this message translates to:
  /// **'El examen no está disponible o ya no existe en esta vista.'**
  String get examUnavailable;

  /// No description provided for @proposalReadFailed.
  ///
  /// In es, this message translates to:
  /// **'No se pudo leer la propuesta. Consulta nuevamente.'**
  String get proposalReadFailed;

  /// No description provided for @discardQuestion.
  ///
  /// In es, this message translates to:
  /// **'¿Descartar propuesta?'**
  String get discardQuestion;

  /// No description provided for @reviewConfirmation.
  ///
  /// In es, this message translates to:
  /// **'Revisar confirmación'**
  String get reviewConfirmation;

  /// No description provided for @discardWarning.
  ///
  /// In es, this message translates to:
  /// **'Se descartará esta propuesta. No se elimina el documento.'**
  String get discardWarning;

  /// No description provided for @lowConfidenceHint.
  ///
  /// In es, this message translates to:
  /// **'Baja confianza: coteja este marcador con el documento original.'**
  String get lowConfidenceHint;

  /// No description provided for @valueLabel.
  ///
  /// In es, this message translates to:
  /// **'Valor'**
  String get valueLabel;

  /// No description provided for @unitLabel.
  ///
  /// In es, this message translates to:
  /// **'Unidad'**
  String get unitLabel;

  /// No description provided for @documentReference.
  ///
  /// In es, this message translates to:
  /// **'Referencia del documento'**
  String get documentReference;

  /// No description provided for @lowerLimit.
  ///
  /// In es, this message translates to:
  /// **'Límite inferior'**
  String get lowerLimit;

  /// No description provided for @upperLimit.
  ///
  /// In es, this message translates to:
  /// **'Límite superior'**
  String get upperLimit;

  /// No description provided for @referenceUnit.
  ///
  /// In es, this message translates to:
  /// **'Unidad de referencia'**
  String get referenceUnit;

  /// No description provided for @referenceText.
  ///
  /// In es, this message translates to:
  /// **'Texto de referencia'**
  String get referenceText;

  /// No description provided for @compareProposal.
  ///
  /// In es, this message translates to:
  /// **'Coteja la propuesta con el PDF sintético original. No es un diagnóstico.'**
  String get compareProposal;

  /// No description provided for @confirmationReceived.
  ///
  /// In es, this message translates to:
  /// **'La confirmación ya fue recibida. Puede faltar la revisión profesional.'**
  String get confirmationReceived;

  /// No description provided for @noNewConfirmation.
  ///
  /// In es, this message translates to:
  /// **'Consulta el estado del examen. No se requiere una nueva confirmación.'**
  String get noNewConfirmation;

  /// No description provided for @documentDates.
  ///
  /// In es, this message translates to:
  /// **'Fechas del documento'**
  String get documentDates;

  /// No description provided for @collectionDateLabel.
  ///
  /// In es, this message translates to:
  /// **'Fecha de muestra'**
  String get collectionDateLabel;

  /// No description provided for @reportDateLabel.
  ///
  /// In es, this message translates to:
  /// **'Fecha de informe'**
  String get reportDateLabel;

  /// No description provided for @identityAcknowledgement.
  ///
  /// In es, this message translates to:
  /// **'He comprobado que este documento me corresponde.'**
  String get identityAcknowledgement;

  /// No description provided for @valuesAcknowledgement.
  ///
  /// In es, this message translates to:
  /// **'He cotejado valores, unidades y campos de baja confianza.'**
  String get valuesAcknowledgement;

  /// No description provided for @reviewConfirm.
  ///
  /// In es, this message translates to:
  /// **'Revisar y confirmar'**
  String get reviewConfirm;

  /// No description provided for @retrySameSubmission.
  ///
  /// In es, this message translates to:
  /// **'Reintentar el mismo envío'**
  String get retrySameSubmission;

  /// No description provided for @discardProposal.
  ///
  /// In es, this message translates to:
  /// **'Descartar propuesta'**
  String get discardProposal;

  /// No description provided for @serverDeterminesStatus.
  ///
  /// In es, this message translates to:
  /// **'Estado determinado por FastAPI. No equivale a validación profesional.'**
  String get serverDeterminesStatus;

  /// No description provided for @checkCurrentQuestion.
  ///
  /// In es, this message translates to:
  /// **'¿Consultar estado actual?'**
  String get checkCurrentQuestion;

  /// No description provided for @checkCurrentWarning.
  ///
  /// In es, this message translates to:
  /// **'Se descartará el borrador y se consultará la propuesta vigente. No se reenviará ninguna mutación.'**
  String get checkCurrentWarning;

  /// No description provided for @checkCurrentProposal.
  ///
  /// In es, this message translates to:
  /// **'Consultar propuesta actual'**
  String get checkCurrentProposal;

  /// No description provided for @syntheticDocument.
  ///
  /// In es, this message translates to:
  /// **'Documento sintético'**
  String get syntheticDocument;

  /// No description provided for @zoomOut.
  ///
  /// In es, this message translates to:
  /// **'Alejar documento'**
  String get zoomOut;

  /// No description provided for @zoomIn.
  ///
  /// In es, this message translates to:
  /// **'Acercar documento'**
  String get zoomIn;

  /// No description provided for @pdfOpenFailed.
  ///
  /// In es, this message translates to:
  /// **'No se puede abrir el documento: falta el archivo o su integridad no coincide.'**
  String get pdfOpenFailed;

  /// No description provided for @pdfRenderFailed.
  ///
  /// In es, this message translates to:
  /// **'No se pudo representar el PDF sintético.'**
  String get pdfRenderFailed;

  /// No description provided for @statusReviewed.
  ///
  /// In es, this message translates to:
  /// **'Con revisión profesional'**
  String get statusReviewed;

  /// No description provided for @statusReady.
  ///
  /// In es, this message translates to:
  /// **'Pendiente de revisión profesional'**
  String get statusReady;

  /// No description provided for @statusValidated.
  ///
  /// In es, this message translates to:
  /// **'Revisión profesional completada'**
  String get statusValidated;

  /// No description provided for @statusRejected.
  ///
  /// In es, this message translates to:
  /// **'Revisión no aprobada'**
  String get statusRejected;

  /// No description provided for @statusProcessing.
  ///
  /// In es, this message translates to:
  /// **'Procesando documento'**
  String get statusProcessing;

  /// No description provided for @statusPendingUpload.
  ///
  /// In es, this message translates to:
  /// **'Carga pendiente'**
  String get statusPendingUpload;

  /// No description provided for @statusReceived.
  ///
  /// In es, this message translates to:
  /// **'Documento recibido'**
  String get statusReceived;

  /// No description provided for @statusDeleted.
  ///
  /// In es, this message translates to:
  /// **'Examen eliminado'**
  String get statusDeleted;

  /// No description provided for @statusFailed.
  ///
  /// In es, this message translates to:
  /// **'No se pudo procesar'**
  String get statusFailed;

  /// No description provided for @statusUnknown.
  ///
  /// In es, this message translates to:
  /// **'Estado por consultar'**
  String get statusUnknown;

  /// No description provided for @typeBlood.
  ///
  /// In es, this message translates to:
  /// **'Examen de sangre'**
  String get typeBlood;

  /// No description provided for @typeUrine.
  ///
  /// In es, this message translates to:
  /// **'Examen de orina'**
  String get typeUrine;

  /// No description provided for @typeImaging.
  ///
  /// In es, this message translates to:
  /// **'Imagen médica'**
  String get typeImaging;

  /// No description provided for @typePathology.
  ///
  /// In es, this message translates to:
  /// **'Anatomía patológica'**
  String get typePathology;

  /// No description provided for @typeOther.
  ///
  /// In es, this message translates to:
  /// **'Otro documento'**
  String get typeOther;

  /// No description provided for @extractionAwaiting.
  ///
  /// In es, this message translates to:
  /// **'Esperando tu confirmación'**
  String get extractionAwaiting;

  /// No description provided for @extractionConfirmed.
  ///
  /// In es, this message translates to:
  /// **'Datos confirmados'**
  String get extractionConfirmed;

  /// No description provided for @extractionPreparing.
  ///
  /// In es, this message translates to:
  /// **'Preparando propuesta'**
  String get extractionPreparing;

  /// No description provided for @extractionFailed.
  ///
  /// In es, this message translates to:
  /// **'No se pudo extraer la información'**
  String get extractionFailed;

  /// No description provided for @extractionUnreadable.
  ///
  /// In es, this message translates to:
  /// **'Documento ilegible'**
  String get extractionUnreadable;

  /// No description provided for @extractionDiscarded.
  ///
  /// In es, this message translates to:
  /// **'Propuesta descartada'**
  String get extractionDiscarded;

  /// No description provided for @extractionRejected.
  ///
  /// In es, this message translates to:
  /// **'Propuesta no aprobada'**
  String get extractionRejected;

  /// No description provided for @extractionNotApplicable.
  ///
  /// In es, this message translates to:
  /// **'Sin propuesta de resultados'**
  String get extractionNotApplicable;

  /// No description provided for @uploadQueued.
  ///
  /// In es, this message translates to:
  /// **'Pendiente de envío'**
  String get uploadQueued;

  /// No description provided for @uploadBytesPending.
  ///
  /// In es, this message translates to:
  /// **'Archivo pendiente'**
  String get uploadBytesPending;

  /// No description provided for @uploadCompletePending.
  ///
  /// In es, this message translates to:
  /// **'Recepción pendiente'**
  String get uploadCompletePending;

  /// No description provided for @uploadVerified.
  ///
  /// In es, this message translates to:
  /// **'Documento verificado'**
  String get uploadVerified;

  /// No description provided for @uploadRejected.
  ///
  /// In es, this message translates to:
  /// **'Documento rechazado'**
  String get uploadRejected;

  /// No description provided for @uploadFailed.
  ///
  /// In es, this message translates to:
  /// **'Procesamiento fallido'**
  String get uploadFailed;

  /// No description provided for @uploadConflict.
  ///
  /// In es, this message translates to:
  /// **'Requiere revisar el estado actual'**
  String get uploadConflict;

  /// No description provided for @pendingConflictHelp.
  ///
  /// In es, this message translates to:
  /// **'Consulta estados antes de continuar. No prepares otra carga para resolver este conflicto.'**
  String get pendingConflictHelp;

  /// No description provided for @pendingProcessingHelp.
  ///
  /// In es, this message translates to:
  /// **'El servidor recibió la carga. Consulta estados; no necesitas enviarla otra vez.'**
  String get pendingProcessingHelp;

  /// No description provided for @pendingRejectedHelp.
  ///
  /// In es, this message translates to:
  /// **'El servidor rechazó el documento. La copia local se conserva; no se reenvía automáticamente.'**
  String get pendingRejectedHelp;

  /// No description provided for @pendingFailedHelp.
  ///
  /// In es, this message translates to:
  /// **'El procesamiento falló. Consulta el detalle antes de preparar otra operación.'**
  String get pendingFailedHelp;

  /// No description provided for @pendingVerifiedHelp.
  ///
  /// In es, this message translates to:
  /// **'La recepción fue verificada; abre el examen para consultar su extracción y confirmación.'**
  String get pendingVerifiedHelp;

  /// No description provided for @pendingHashHelp.
  ///
  /// In es, this message translates to:
  /// **'La copia no coincide con su hash. No se enviará; conserva el original y revisa la operación.'**
  String get pendingHashHelp;

  /// No description provided for @pendingRetryHelp.
  ///
  /// In es, this message translates to:
  /// **'Espera el intervalo indicado por el servidor antes de reintentar explícitamente.'**
  String get pendingRetryHelp;

  /// No description provided for @pendingInterruptedHelp.
  ///
  /// In es, this message translates to:
  /// **'El último intento no terminó. Consulta estados y luego reintenta explícitamente; se conserva la identidad de la carga.'**
  String get pendingInterruptedHelp;

  /// No description provided for @pendingLocalHelp.
  ///
  /// In es, this message translates to:
  /// **'Guardado solo en este dispositivo. El envío requiere tu acción explícita.'**
  String get pendingLocalHelp;

  /// No description provided for @errorExtractionNotReady.
  ///
  /// In es, this message translates to:
  /// **'El documento sigue preparando la propuesta. Consulta nuevamente.'**
  String get errorExtractionNotReady;

  /// No description provided for @errorOffline.
  ///
  /// In es, this message translates to:
  /// **'Sin conexión verificada. Tu operación sigue pendiente.'**
  String get errorOffline;

  /// No description provided for @errorSession.
  ///
  /// In es, this message translates to:
  /// **'La sesión venció. Vuelve a conectar el perfil sintético.'**
  String get errorSession;

  /// No description provided for @errorStorageAuth.
  ///
  /// In es, this message translates to:
  /// **'Autorización del archivo vencida. Reintenta explícitamente.'**
  String get errorStorageAuth;

  /// No description provided for @errorDenied.
  ///
  /// In es, this message translates to:
  /// **'No tienes permiso para esta operación.'**
  String get errorDenied;

  /// No description provided for @errorConflict.
  ///
  /// In es, this message translates to:
  /// **'Conflicto: consulta el estado actual antes de continuar.'**
  String get errorConflict;

  /// No description provided for @errorValidation.
  ///
  /// In es, this message translates to:
  /// **'Revisa los campos y el consentimiento del documento.'**
  String get errorValidation;

  /// No description provided for @errorRateLimit.
  ///
  /// In es, this message translates to:
  /// **'Límite temporal. Espera antes de reintentar.'**
  String get errorRateLimit;

  /// No description provided for @errorService.
  ///
  /// In es, this message translates to:
  /// **'Servicio no disponible. No se ha confirmado éxito.'**
  String get errorService;

  /// No description provided for @errorUnknown.
  ///
  /// In es, this message translates to:
  /// **'No se pudo completar la operación.'**
  String get errorUnknown;

  /// No description provided for @operationInterrupted.
  ///
  /// In es, this message translates to:
  /// **'Operación interrumpida. Consulta el estado antes de reintentar.'**
  String get operationInterrupted;

  /// No description provided for @sessionExpired.
  ///
  /// In es, this message translates to:
  /// **'Sesión expirada'**
  String get sessionExpired;

  /// No description provided for @accessUnauthorized.
  ///
  /// In es, this message translates to:
  /// **'Acceso no autorizado'**
  String get accessUnauthorized;

  /// No description provided for @verifying.
  ///
  /// In es, this message translates to:
  /// **'Verificando'**
  String get verifying;

  /// No description provided for @connected.
  ///
  /// In es, this message translates to:
  /// **'Conectado'**
  String get connected;

  /// No description provided for @connectionUnverified.
  ///
  /// In es, this message translates to:
  /// **'Sin conexión verificada'**
  String get connectionUnverified;

  /// No description provided for @dateUnavailable.
  ///
  /// In es, this message translates to:
  /// **'Fecha no disponible'**
  String get dateUnavailable;

  /// No description provided for @timeUnavailable.
  ///
  /// In es, this message translates to:
  /// **'Hora no disponible'**
  String get timeUnavailable;

  /// No description provided for @referenceFinite.
  ///
  /// In es, this message translates to:
  /// **'Revisa los límites de referencia: usa números finitos.'**
  String get referenceFinite;

  /// No description provided for @referenceOrder.
  ///
  /// In es, this message translates to:
  /// **'El límite inferior debe ser menor que el superior.'**
  String get referenceOrder;

  /// No description provided for @markerFieldsRequired.
  ///
  /// In es, this message translates to:
  /// **'Completa valor y unidad de los marcadores editados.'**
  String get markerFieldsRequired;

  /// No description provided for @reviewDatesInvalid.
  ///
  /// In es, this message translates to:
  /// **'Revisa las fechas (AAAA-MM-DD). La API no permite vaciar una fecha existente.'**
  String get reviewDatesInvalid;

  /// No description provided for @referenceOriginal.
  ///
  /// In es, this message translates to:
  /// **'Referencia original'**
  String get referenceOriginal;

  /// No description provided for @referenceRevised.
  ///
  /// In es, this message translates to:
  /// **'Referencia revisada'**
  String get referenceRevised;

  /// No description provided for @withoutDate.
  ///
  /// In es, this message translates to:
  /// **'sin fecha'**
  String get withoutDate;

  /// No description provided for @panelUnnamed.
  ///
  /// In es, this message translates to:
  /// **'Panel sin nombre'**
  String get panelUnnamed;

  /// No description provided for @language.
  ///
  /// In es, this message translates to:
  /// **'Idioma'**
  String get language;

  /// No description provided for @languageHint.
  ///
  /// In es, this message translates to:
  /// **'Se guarda en este dispositivo, incluso sin conexión.'**
  String get languageHint;

  /// No description provided for @spanish.
  ///
  /// In es, this message translates to:
  /// **'Español'**
  String get spanish;

  /// No description provided for @english.
  ///
  /// In es, this message translates to:
  /// **'English'**
  String get english;

  /// No description provided for @languageSaveFailed.
  ///
  /// In es, this message translates to:
  /// **'No se pudo guardar el idioma. Inténtalo nuevamente.'**
  String get languageSaveFailed;

  /// No description provided for @loadingDocument.
  ///
  /// In es, this message translates to:
  /// **'Cargando documento'**
  String get loadingDocument;

  /// No description provided for @lightTheme.
  ///
  /// In es, this message translates to:
  /// **'Tema claro'**
  String get lightTheme;

  /// No description provided for @darkTheme.
  ///
  /// In es, this message translates to:
  /// **'Tema oscuro'**
  String get darkTheme;

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'{count, plural, one{{count} en la vista actual} other{{count} en la vista actual}}'**
  String currentViewCount(int count);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'{count, plural, one{{count} operación local} other{{count} operaciones locales}}'**
  String localOperationsCount(int count);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'Intentos de envío: {count}'**
  String attemptCount(int count);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'{count, plural, one{1 pendiente local} other{{count} pendientes locales}} ? {connection}'**
  String pendingConnection(int count, String connection);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'PDF seleccionado · {count} bytes'**
  String selectedPdf(int count);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'Filtro del servidor: {status} · {type}'**
  String serverFilter(String status, String type);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'{visible} de {loaded} documentos cargados en esta consulta.'**
  String resultCount(int visible, int loaded);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'Referencia del documento: {low} – {high} {unit} {text}'**
  String referenceDescription(
    String low,
    String high,
    String unit,
    String text,
  );

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'Revisión profesional: {status}'**
  String professionalReview(String status);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'Archivo: {name}'**
  String fileName(String name);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'Tamaño: {count} bytes'**
  String fileSize(int count);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'Tus notas: {notes}'**
  String patientNotes(String notes);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'Estado actual del servidor: {status}. Revisa la propuesta actual antes de continuar.'**
  String currentServerState(String status);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'Fecha de muestra: {date}'**
  String sampleDate(String date);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'Fecha de informe: {date}'**
  String reportDate(String date);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'Confirmado: {date}'**
  String confirmedOn(String date);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'{count, plural, one{{count} página} other{{count} páginas}}'**
  String pagesCount(int count);

  /// Patient presentation only; preserve raw clinical data and API identifiers.
  ///
  /// In es, this message translates to:
  /// **'{summary}\n\nOriginal → revisión. Confirmación humana, sin validación clínica.'**
  String submissionSummary(String summary);

  /// No description provided for @errorNotFound.
  ///
  /// In es, this message translates to:
  /// **'Documento no encontrado.'**
  String get errorNotFound;

  /// No description provided for @queueSending.
  ///
  /// In es, this message translates to:
  /// **'Enviando operaci?n'**
  String get queueSending;

  /// No description provided for @queueMissing.
  ///
  /// In es, this message translates to:
  /// **'Falta la copia privada. La operaci?n se conserva.'**
  String get queueMissing;

  /// No description provided for @queueIncomplete.
  ///
  /// In es, this message translates to:
  /// **'Copia interrumpida. Los datos disponibles se conservan.'**
  String get queueIncomplete;

  /// No description provided for @queueCorrupt.
  ///
  /// In es, this message translates to:
  /// **'La copia no coincide con su huella. No se enviar?.'**
  String get queueCorrupt;

  /// No description provided for @queueUnreadable.
  ///
  /// In es, this message translates to:
  /// **'No se pudo guardar o leer la copia. La operaci?n se conserva.'**
  String get queueUnreadable;

  /// No description provided for @queueVerifying.
  ///
  /// In es, this message translates to:
  /// **'Verificando recepci?n en el servidor'**
  String get queueVerifying;

  /// No description provided for @queueWaitingConnection.
  ///
  /// In es, this message translates to:
  /// **'Esperando conexi?n verificada'**
  String get queueWaitingConnection;

  /// No description provided for @queuePaused.
  ///
  /// In es, this message translates to:
  /// **'Env?o pausado. Se requiere una acci?n para continuar.'**
  String get queuePaused;

  /// No description provided for @queueAwaitingAuthorization.
  ///
  /// In es, this message translates to:
  /// **'Guardado localmente. Esperando autorizaci?n de env?o.'**
  String get queueAwaitingAuthorization;

  /// No description provided for @queueReadyToResume.
  ///
  /// In es, this message translates to:
  /// **'Preparado para reanudar con tu autorizaci?n.'**
  String get queueReadyToResume;

  /// No description provided for @queueRetryAfter.
  ///
  /// In es, this message translates to:
  /// **'Error recuperable. Puedes reintentar a partir de {date}, {time}.'**
  String queueRetryAfter(String date, String time);

  /// No description provided for @queuePause.
  ///
  /// In es, this message translates to:
  /// **'Pausar env?o'**
  String get queuePause;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'es'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'es':
      return AppLocalizationsEs();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
