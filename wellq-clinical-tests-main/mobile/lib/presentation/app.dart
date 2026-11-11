import '../l10n/localized_copy.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../application/language_controller.dart';
import 'language_selector.dart';
import 'package:file_picker/file_picker.dart';

import '../application/patient_controller.dart';
import '../domain/models.dart';
import 'patient_widgets.dart';
import 'synthetic_pdf_screen.dart';
import 'exam_screen.dart';
import 'patient_dialogs.dart';
import 'exam_list.dart';
export 'exam_screen.dart';

// Brand is a proper name; patient-facing copy is generated from ARB resources.
class AppCopy {
  static const brand = 'WellQ';
  static const warningId = 'syntheticWarning';
}

class WellQApp extends StatefulWidget {
  const WellQApp({super.key, required this.controller, this.language});
  final PatientController controller;
  final LanguageController? language;
  @override
  State<WellQApp> createState() => _WellQAppState();
}

class _WellQAppState extends State<WellQApp> {
  ThemeMode mode = ThemeMode.system;
  late final LanguageController language =
      widget.language ?? LanguageController();
  @override
  void dispose() {
    if (widget.language == null) language.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: Listenable.merge([widget.controller, language]),
    builder: (context, _) => MaterialApp(
      key: ValueKey(
        '${widget.controller.session?.scope}/${widget.controller.generation}',
      ),
      debugShowCheckedModeBanner: false,
      title: AppCopy.brand,
      locale: language.locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff006d68)),
        scaffoldBackgroundColor: const Color(0xfff4f8f7),
        appBarTheme: const AppBarTheme(foregroundColor: Color(0xff15374a)),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
          isDense: true,
          contentPadding: EdgeInsets.all(12),
        ),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
          isDense: true,
          contentPadding: EdgeInsets.all(12),
        ),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xff57c9bf),
          brightness: Brightness.dark,
        ),
      ),
      themeMode: mode,
      home: PatientShell(
        c: widget.controller,
        language: language,
        toggle: () => setState(
          () =>
              mode = mode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark,
        ),
      ),
    ),
  );
}

class PatientShell extends StatefulWidget {
  const PatientShell({
    super.key,
    required this.c,
    required this.toggle,
    required this.language,
  });
  final PatientController c;
  final VoidCallback toggle;
  final LanguageController language;
  @override
  State<PatientShell> createState() => _PatientShellState();
}

class _PatientShellState extends State<PatientShell>
    with WidgetsBindingObserver {
  int tab = 0;
  PatientController get c => widget.c;
  List<String> get labels => [
    context.l10n.home,
    context.l10n.exams,
    context.l10n.upload,
    context.l10n.pending,
    context.l10n.settings,
  ];
  static const icons = [
    Icons.space_dashboard_outlined,
    Icons.folder_open_outlined,
    Icons.upload_file_outlined,
    Icons.sync_outlined,
    Icons.settings_outlined,
  ];
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    c.setForeground(state == AppLifecycleState.resumed);
    if (state == AppLifecycleState.resumed && c.session != null && !c.busy) {
      c.reconcile();
    }
  }

  String queueStatus(PendingUpload op) {
    final l = context.l10n;
    if (c.sendingId == op.id) return l.queueSending;
    if (op.fileIssue != null) {
      return switch (op.fileIssue) {
        'missing' => l.queueMissing,
        'incomplete' => l.queueIncomplete,
        'corrupt' => l.queueCorrupt,
        _ => l.queueUnreadable,
      };
    }
    if (op.phase == 'processing' || op.phase == 'object_uploaded') {
      return l.queueVerifying;
    }
    if (op.finished || op.phase == 'conflict') {
      return localizedPhaseLabel(context, op.phase);
    }
    if (op.error == 'UPLOAD_PAUSED') return l.queuePaused;
    if (op.retryAt > DateTime.now().millisecondsSinceEpoch) {
      final date = DateTime.fromMillisecondsSinceEpoch(op.retryAt);
      final format = MaterialLocalizations.of(context);
      return l.queueRetryAfter(
        format.formatShortDate(date),
        format.formatTimeOfDay(TimeOfDay.fromDateTime(date)),
      );
    }
    if (!c.online) return l.queueWaitingConnection;
    return op.attempts == 0
        ? l.queueAwaitingAuthorization
        : l.queueReadyToResume;
  }

  Widget page(List<Widget> children) =>
      ListView(padding: const EdgeInsets.all(16), children: children);
  Widget heading(String title, String subtitle) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(
            context,
          ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 4),
        Text(subtitle),
      ],
    ),
  );
  void open(Exam exam) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => ExamScreen(c: c, exam: exam),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final signed = c.session != null;
    final content = Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
          child: Semantics(
            liveRegion: true,
            child: Wrap(
              spacing: 8,
              runSpacing: 2,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Icon(
                  c.online && !c.busy
                      ? Icons.cloud_done_outlined
                      : Icons.cloud_off_outlined,
                  size: 16,
                ),
                Text(
                  context.l10n.safeMessage(c.connectionLabel),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                Text(
                  context.l10n.syntheticEnvironment,
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w600),
                ),
                if (signed && !c.online)
                  TextButton(
                    onPressed: c.busy ? null : c.reconcile,
                    child: Text(context.l10n.checkConnection),
                  ),
              ],
            ),
          ),
        ),
        if (c.busy) const LinearProgressIndicator(),
        if (c.message != null)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Semantics(
              liveRegion: true,
              child: Text(
                context.l10n.safeMessage(c.message!),
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          ),
        Expanded(
          child: !signed
              ? welcome()
              : IndexedStack(
                  index: tab,
                  children: [
                    dashboard(),
                    exams(),
                    UploadScreen(c: c, queued: () => setState(() => tab = 3)),
                    pending(),
                    settings(),
                  ],
                ),
        ),
      ],
    );
    return LayoutBuilder(
      builder: (context, box) {
        final wide = box.maxWidth >= 700 && box.maxHeight >= 600;
        return Scaffold(
          appBar: AppBar(
            title: const Text(
              'WellQ',
              style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: -1),
            ),
            actions: [
              IconButton(
                tooltip: context.l10n.changeTheme,
                onPressed: widget.toggle,
                icon: const Icon(Icons.brightness_6_outlined),
              ),
              if (signed)
                IconButton(
                  tooltip: context.l10n.refreshReadings,
                  onPressed: c.busy ? null : c.refresh,
                  icon: const Icon(Icons.refresh),
                ),
            ],
          ),
          body: SafeArea(
            child: wide && signed
                ? Row(
                    children: [
                      NavigationRail(
                        selectedIndex: tab,
                        labelType: NavigationRailLabelType.all,
                        onDestinationSelected: (v) => setState(() => tab = v),
                        destinations: [
                          for (var i = 0; i < 5; i++)
                            NavigationRailDestination(
                              icon: Icon(
                                icons[i],
                                key: ValueKey('patient-tab/$i'),
                              ),
                              label: Text(labels[i]),
                            ),
                        ],
                      ),
                      Expanded(child: content),
                    ],
                  )
                : content,
          ),
          bottomNavigationBar: !wide && signed
              ? PatientNavigation(
                  selected: tab,
                  onSelected: (v) => setState(() => tab = v),
                )
              : null,
        );
      },
    );
  }

  Widget welcome() {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final l = context.l10n;
    return page([
      Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Card.outlined(
              margin: EdgeInsets.zero,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(24),
                side: BorderSide(color: colors.outlineVariant),
              ),
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        DecoratedBox(
                          decoration: BoxDecoration(
                            color: colors.primaryContainer,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Icon(
                              Icons.monitor_heart_outlined,
                              size: 28,
                              color: colors.onPrimaryContainer,
                            ),
                          ),
                        ),
                        Text(
                          AppCopy.brand,
                          style: theme.textTheme.headlineMedium?.copyWith(
                            fontWeight: FontWeight.w800,
                            letterSpacing: -1,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      l.patientSession,
                      style: theme.textTheme.labelLarge?.copyWith(
                        color: colors.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 28),
                    Semantics(
                      header: true,
                      child: Text(
                        l.welcomeTitle,
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      l.welcomeSubtitle,
                      style: theme.textTheme.bodyLarge?.copyWith(
                        color: colors.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 20),
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: colors.secondaryContainer,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        l.syntheticWarning,
                        style: theme.textTheme.labelLarge?.copyWith(
                          color: colors.onSecondaryContainer,
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      onPressed: c.busy ? null : c.connect,
                      style: FilledButton.styleFrom(
                        minimumSize: const Size(0, 52),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 16,
                        ),
                      ),
                      icon: const Icon(Icons.login, size: 20),
                      label: Text(
                        l.connectSynthetic,
                        textAlign: TextAlign.center,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      l.welcomeRequires,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colors.onSurfaceVariant,
                      ),
                    ),
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 12),
                      child: Divider(),
                    ),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          Icons.lock_outline,
                          size: 20,
                          color: colors.onSurfaceVariant,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            l.welcomeQueue,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: colors.onSurfaceVariant,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    ExpansionTile(
                      tilePadding: EdgeInsets.zero,
                      title: Text(l.settings),
                      children: [LanguageSelector(language: widget.language)],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    ]);
  }

  Widget dashboard() => page([
    Card.filled(
      margin: EdgeInsets.zero,
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              header: true,
              child: heading(
                context.l10n.helloPatient,
                context.l10n.documentsAtHand,
              ),
            ),
            const SizedBox(height: 4),
            FilledButton.icon(
              onPressed: () => setState(() => tab = 2),
              style: FilledButton.styleFrom(
                minimumSize: const Size(0, 52),
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 14,
                ),
              ),
              icon: const Icon(Icons.upload_file_outlined),
              label: Text(
                context.l10n.uploadDocument,
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ),
      ),
    ),
    const SizedBox(height: 16),
    Card.outlined(
      margin: EdgeInsets.zero,
      child: Column(
        children: [
          ListTile(
            leading: const Icon(Icons.folder_open_outlined),
            title: Text(context.l10n.myExams),
            subtitle: Text(context.l10n.currentViewCount(c.exams.length)),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => setState(() => tab = 1),
          ),
          const Divider(height: 1, indent: 16, endIndent: 16),
          ListTile(
            leading: const Icon(Icons.sync_outlined),
            title: Text(context.l10n.pendingUploads),
            subtitle: Text(
              context.l10n.localOperationsCount(
                c.operations.where((o) => !o.finished).length,
              ),
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => setState(() => tab = 3),
          ),
        ],
      ),
    ),
    const SizedBox(height: 24),
    Semantics(
      header: true,
      child: Text(
        context.l10n.recentExams,
        style: Theme.of(
          context,
        ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
      ),
    ),
    const SizedBox(height: 8),
    if (c.exams.isEmpty)
      Card.outlined(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                Icons.folder_open_outlined,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                size: 28,
              ),
              const SizedBox(height: 12),
              Text(context.l10n.noExamsYet),
            ],
          ),
        ),
      ),
    for (final exam in c.exams.take(3)) examCard(exam),
    if (c.exams.isNotEmpty) Text(context.l10n.openExamHint),
    TextButton(
      onPressed: () => setState(() => tab = 1),
      child: Text(context.l10n.viewMyExams),
    ),
  ]);
  Widget examCard(Exam exam) => Card.outlined(
    child: ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      minLeadingWidth: 24,
      horizontalTitleGap: 12,
      leading: const Icon(Icons.description_outlined),
      title: Text(
        exam.title.trim().isEmpty ? context.l10n.untitledExam : exam.title,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${localizedClinicalDate(context, exam.date)}${localizedTestTypeLabel(context, exam.testType) == null ? '' : ' · ${localizedTestTypeLabel(context, exam.testType)}'}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            Text(
              localizedExamLabel(
                context,
                exam.status,
                review: exam.reviewStatus,
              ),
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: Theme.of(context).colorScheme.primary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => open(exam),
    ),
  );
  Widget exams() => ExamList(c: c, card: examCard);
  Widget pending() => page([
    heading(context.l10n.pendingOperations, context.l10n.pendingSubtitle),
    OutlinedButton.icon(
      onPressed: c.busy ? null : c.reconcile,
      icon: const Icon(Icons.sync),
      label: Text(context.l10n.checkStatesConnection),
    ),
    if (c.operations.isEmpty)
      Padding(
        padding: EdgeInsets.all(24),
        child: Text(context.l10n.noLocalOperations),
      ),
    for (final op in c.operations)
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(op.title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Semantics(liveRegion: true, child: Text(queueStatus(op))),
              Text(context.l10n.attemptCount(op.attempts)),
              Text(
                localizedPendingHelp(
                  context,
                  op.phase,
                  error: op.error,
                  retryScheduled: op.payload['retry_at'] != null,
                ),
              ),
              if (op.canDelete) Text(context.l10n.verifiedLocalCopy),
              const SizedBox(height: 8),
              if (c.sendingId == op.id)
                OutlinedButton(
                  onPressed: c.pauseUpload,
                  child: Text(context.l10n.queuePause),
                )
              else if (op.canResume &&
                  c.session?.permissions.contains('clinical:write') == true)
                FilledButton(
                  onPressed: c.busy ? null : () => c.resume(op),
                  child: Text(
                    op.attempts == 0
                        ? context.l10n.sendDocument
                        : context.l10n.retryUpload,
                  ),
                ),
              if (op.examId != null)
                TextButton(
                  onPressed: () =>
                      open(Exam(op.examId!, op.title, '', 'processing')),
                  child: Text(context.l10n.openExamExtraction),
                ),
            ],
          ),
        ),
      ),
  ]);
  Widget settings() => page([
    heading(context.l10n.yourSpace, context.l10n.appPreferences),
    LanguageSelector(language: widget.language),
    ListTile(
      leading: const Icon(Icons.palette_outlined),
      title: Text(context.l10n.changeAppearance),
      onTap: widget.toggle,
    ),
    ListTile(
      leading: Icon(Icons.person_outline),
      title: Text(context.l10n.patientSession),
      subtitle: Text(context.l10n.syntheticProfile),
    ),
    ListTile(
      leading: const Icon(Icons.sync_outlined),
      title: Text(context.l10n.syncStatus),
      subtitle: Text(
        context.l10n.pendingConnection(
          c.operations.where((o) => !o.finished).length,
          context.l10n.safeMessage(c.connectionLabel),
        ),
      ),
      onTap: () => setState(() => tab = 3),
    ),
    ExpansionTile(
      title: Text(context.l10n.developmentInfo),
      leading: Icon(Icons.code_outlined),
      children: [
        ListTile(
          title: Text(context.l10n.syntheticIdentity),
          subtitle: Text(context.l10n.tokensRam),
        ),
        ListTile(
          title: Text(context.l10n.testPersistence),
          subtitle: Text(context.l10n.syntheticDrift),
        ),
        ListTile(
          title: Text(context.l10n.productionPdfBlocked),
          subtitle: Text(context.l10n.noProductionProviders),
        ),
      ],
    ),
    FilledButton.tonal(
      onPressed: () async {
        final yes = await ask(
          context,
          context.l10n.logoutQuestion,
          context.l10n.logoutWarning,
        );
        if (yes) await c.logout();
      },
      child: Text(context.l10n.logout),
    ),
  ]);
}

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key, required this.c, required this.queued});
  final PatientController c;
  final VoidCallback queued;
  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  final title = TextEditingController(text: 'SYNTHETIC MOBILE SAMPLE'),
      date = TextEditingController(
        text: DateTime.now().toIso8601String().substring(0, 10),
      );
  List<int>? bytes;
  bool consent = false, synthetic = false;
  String? error;
  Future<void> selectPdf() async {
    try {
      final files = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf'],
      );
      if (files.isEmpty) return;
      final size = await files.single.length();
      if (size == null || size > 20 * 1024 * 1024) {
        if (mounted) setState(() => error = 'fileTooLarge');
        return;
      }
      final selected = verifiedSyntheticBytes(await files.single.readAsBytes());
      if (mounted) {
        setState(() {
          bytes = selected;
          error = null;
        });
      }
    } on FormatException {
      if (mounted) {
        setState(() => error = 'syntheticIntegrityOnly');
      }
    } catch (_) {
      if (mounted) {
        setState(() => error = 'pickerUnavailable');
      }
    }
  }

  @override
  void dispose() {
    title.dispose();
    date.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text(
        context.l10n.newDocument,
        style: Theme.of(context).textTheme.titleMedium,
      ),
      const SizedBox(height: 8),
      Text(context.l10n.syntheticPdfOnly),
      const SizedBox(height: 16),
      OutlinedButton.icon(
        onPressed: () async {
          final data = await rootBundle.load('assets/synthetic.pdf');
          if (mounted) setState(() => bytes = data.buffer.asUint8List());
        },
        icon: const Icon(Icons.science_outlined),
        label: Text(context.l10n.useTestPdf),
      ),
      TextButton.icon(
        onPressed: selectPdf,
        icon: const Icon(Icons.attach_file),
        label: Text(context.l10n.selectTestPdf),
      ),
      if (bytes != null) ...[
        Text(context.l10n.selectedPdf(bytes!.length)),
        TextButton.icon(
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => SyntheticPdfScreen(
                load: () async => verifiedSyntheticBytes(bytes!),
              ),
            ),
          ),
          icon: const Icon(Icons.picture_as_pdf_outlined),
          label: Text(context.l10n.viewDocument),
        ),
      ],
      const SizedBox(height: 16),
      LabeledField(
        label: context.l10n.documentTitle,
        child: TextField(
          controller: title,
          maxLength: 200,
          decoration: const InputDecoration(),
        ),
      ),
      LabeledField(
        label: context.l10n.examDate,
        child: TextField(
          controller: date,
          keyboardType: TextInputType.datetime,
          decoration: InputDecoration(hintText: context.l10n.isoDateHint),
        ),
      ),
      Padding(
        padding: EdgeInsets.only(top: 4),
        child: Text(context.l10n.examDateHint),
      ),
      CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        value: synthetic,
        onChanged: (v) => setState(() => synthetic = v ?? false),
        title: Text(context.l10n.confirmSyntheticOnly),
      ),
      CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        value: consent,
        onChanged: (v) => setState(() => consent = v ?? false),
        title: Text(context.l10n.authorizeSyntheticProcessing),
      ),
      if (error != null)
        Text(
          context.l10n.safeMessage(error!),
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      FilledButton.icon(
        onPressed: bytes == null || !synthetic || !consent || widget.c.busy
            ? null
            : () async {
                final before = widget.c.operations.length;
                await widget.c.queue(bytes!, title.text, date.text);
                if (!mounted) return;
                if (widget.c.operations.length > before) {
                  widget.queued();
                } else {
                  setState(
                    () => error = widget.c.message ?? 'operationNotSaved',
                  );
                }
              },
        icon: const Icon(Icons.save_outlined),
        label: Text(context.l10n.savePending),
      ),
      const SizedBox(height: 12),
      Text(context.l10n.saveDoesNotSend),
    ],
  );
}
