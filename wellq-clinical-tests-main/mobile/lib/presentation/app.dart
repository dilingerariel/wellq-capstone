import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:file_picker/file_picker.dart';

import '../application/patient_controller.dart';
import '../domain/models.dart';
import '../domain/patient_labels.dart';
import '../domain/patient_dates.dart';
import 'patient_widgets.dart';
import 'synthetic_pdf_screen.dart';
import 'exam_screen.dart';
import 'patient_dialogs.dart';
import 'exam_list.dart';
export 'exam_screen.dart';

// Centralized patient copy; Material widgets already localize to Spanish.
class AppCopy {
  static const brand = 'WellQ';
  static const warning = 'Solo datos sintéticos • Sin uso clínico';
}

class WellQApp extends StatefulWidget {
  const WellQApp({super.key, required this.controller});
  final PatientController controller;
  @override
  State<WellQApp> createState() => _WellQAppState();
}

class _WellQAppState extends State<WellQApp> {
  ThemeMode mode = ThemeMode.system;
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.controller,
    builder: (context, _) => MaterialApp(
      key: ValueKey(
        '${widget.controller.session?.scope}/${widget.controller.generation}',
      ),
      debugShowCheckedModeBanner: false,
      title: AppCopy.brand,
      locale: const Locale('es'),
      supportedLocales: const [Locale('es')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
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
        toggle: () => setState(
          () =>
              mode = mode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark,
        ),
      ),
    ),
  );
}

class PatientShell extends StatefulWidget {
  const PatientShell({super.key, required this.c, required this.toggle});
  final PatientController c;
  final VoidCallback toggle;
  @override
  State<PatientShell> createState() => _PatientShellState();
}

class _PatientShellState extends State<PatientShell>
    with WidgetsBindingObserver {
  int tab = 0;
  PatientController get c => widget.c;
  static const labels = [
    'Inicio',
    'Exámenes',
    'Cargar',
    'Pendientes',
    'Ajustes',
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
    if (state == AppLifecycleState.resumed && c.session != null && !c.busy) {
      c.reconcile();
    }
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
                  c.connectionLabel,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                Text(
                  'Entorno sintético',
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w600),
                ),
                if (signed && !c.online)
                  TextButton(
                    onPressed: c.busy ? null : c.reconcile,
                    child: const Text('Comprobar conexión'),
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
                c.message!,
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
                tooltip: 'Cambiar tema',
                onPressed: widget.toggle,
                icon: const Icon(Icons.brightness_6_outlined),
              ),
              if (signed)
                IconButton(
                  tooltip: 'Actualizar lecturas',
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

  Widget welcome() => page([
    const SizedBox(height: 12),
    const Align(
      alignment: Alignment.centerLeft,
      child: CircleAvatar(
        radius: 34,
        child: Icon(Icons.health_and_safety_outlined, size: 38),
      ),
    ),
    const SizedBox(height: 24),
    heading(
      'Tu salud, en orden',
      'Conecta el perfil de prueba para continuar.',
    ),
    const Text(
      'Tu cola local se conserva. Después de reiniciar necesitas verificar el mismo perfil para abrirla.',
    ),
    const SizedBox(height: 24),
    FilledButton.icon(
      onPressed: c.busy ? null : c.connect,
      icon: const Icon(Icons.login),
      label: const Text('Conectar paciente sintético'),
    ),
    const SizedBox(height: 16),
    const Text(
      'Requiere WellQ disponible. Solo datos sintéticos; sin uso clínico.',
    ),
  ]);
  Widget dashboard() => page([
    heading('Hola, paciente', 'Tus documentos, a mano.'),
    FilledButton.icon(
      onPressed: () => setState(() => tab = 2),
      icon: const Icon(Icons.add),
      label: const Text('Cargar documento'),
    ),
    const SizedBox(height: 16),
    Card.outlined(
      child: Column(
        children: [
          ListTile(
            leading: const Icon(Icons.folder_open_outlined),
            title: const Text('Mis exámenes'),
            subtitle: Text('${c.exams.length} en la vista actual'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => setState(() => tab = 1),
          ),
          ListTile(
            leading: const Icon(Icons.sync_outlined),
            title: const Text('Pendientes de envío'),
            subtitle: Text(
              '${c.operations.where((o) => !o.finished).length} operaciones locales',
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => setState(() => tab = 3),
          ),
        ],
      ),
    ),
    const SizedBox(height: 16),
    Text(
      'Exámenes recientes en esta vista',
      style: Theme.of(context).textTheme.titleMedium,
    ),
    const SizedBox(height: 8),
    if (c.exams.isEmpty)
      const Text(
        'Aún no hay exámenes. Carga el documento sintético para comenzar.',
      ),
    for (final exam in c.exams.take(3)) examCard(exam),
    if (c.exams.isNotEmpty)
      const Text('Abre un examen para consultar si requiere tu confirmación.'),
    TextButton(
      onPressed: () => setState(() => tab = 1),
      child: const Text('Ver mis exámenes'),
    ),
  ]);
  Widget examCard(Exam exam) => Card.outlined(
    child: ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      minLeadingWidth: 24,
      horizontalTitleGap: 12,
      leading: const Icon(Icons.description_outlined),
      title: Text(
        exam.title.trim().isEmpty ? 'Examen sin título' : exam.title,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${clinicalDate(exam.date)}${testTypeLabel(exam.testType) == null ? '' : ' · ${testTypeLabel(exam.testType)}'}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            Text(
              examLabel(exam.status, review: exam.reviewStatus),
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
    heading(
      'Operaciones pendientes',
      'Tus documentos guardados. Tú decides cuándo enviarlos.',
    ),
    OutlinedButton.icon(
      onPressed: c.busy ? null : c.reconcile,
      icon: const Icon(Icons.sync),
      label: const Text('Consultar estados y conexión'),
    ),
    if (c.operations.isEmpty)
      const Padding(
        padding: EdgeInsets.all(24),
        child: Text(
          'Sin operaciones locales. Puedes preparar un documento aunque se interrumpa la red.',
        ),
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
              Text(phaseLabel(op.phase)),
              Text('Intentos de envío: ${op.attempts}'),
              Text(
                pendingHelp(
                  op.phase,
                  error: op.error,
                  retryScheduled: op.payload['retry_at'] != null,
                ),
              ),
              if (op.canDelete)
                const Text('Documento verificado. La copia local se conserva.'),
              const SizedBox(height: 8),
              if (op.canResume)
                FilledButton(
                  onPressed: c.busy ? null : () => c.resume(op),
                  child: Text(
                    op.attempts == 0 ? 'Enviar documento' : 'Reintentar envío',
                  ),
                ),
              if (op.examId != null)
                TextButton(
                  onPressed: () =>
                      open(Exam(op.examId!, op.title, '', 'processing')),
                  child: const Text('Abrir examen y extracción'),
                ),
            ],
          ),
        ),
      ),
  ]);
  Widget settings() => page([
    heading('Tu espacio', 'Preferencias de la aplicación.'),
    ListTile(
      leading: const Icon(Icons.palette_outlined),
      title: const Text('Cambiar tema claro / oscuro'),
      onTap: widget.toggle,
    ),
    const ListTile(
      leading: Icon(Icons.person_outline),
      title: Text('Sesión de paciente'),
      subtitle: Text('Perfil sintético de desarrollo. Sin uso clínico.'),
    ),
    ListTile(
      leading: const Icon(Icons.sync_outlined),
      title: const Text('Estado de sincronización'),
      subtitle: Text(
        '${c.operations.where((o) => !o.finished).length} pendientes locales · ${c.connectionLabel}',
      ),
      onTap: () => setState(() => tab = 3),
    ),
    const ExpansionTile(
      title: Text('Información de desarrollo'),
      leading: Icon(Icons.code_outlined),
      children: [
        ListTile(
          title: Text('Identidad sintética'),
          subtitle: Text('Tokens en RAM; firma RS256 solo en el host.'),
        ),
        ListTile(
          title: Text('Persistencia de pruebas'),
          subtitle: Text(
            'Drift/SQLite sin datos clínicos reales. Solo PDF sintético verificado.',
          ),
        ),
        ListTile(
          title: Text('PDF productivo bloqueado'),
          subtitle: Text(
            'Sin exportaciones, scores ni proveedores productivos.',
          ),
        ),
      ],
    ),
    FilledButton.tonal(
      onPressed: () async {
        final yes = await ask(
          context,
          '¿Cerrar sesión?',
          'Se borrarán caché y operaciones locales de esta identidad. Los archivos originales, las copias y los documentos del servidor se conservan.',
        );
        if (yes) await c.logout();
      },
      child: const Text('Cerrar sesión'),
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
        if (mounted) setState(() => error = 'El archivo excede 20 MiB.');
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
        setState(
          () => error =
              'Solo se admite una copia íntegra del PDF sintético incluido.',
        );
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => error =
              'No se pudo abrir el selector. Puedes usar el PDF sintético incluido.',
        );
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
      Text('Nuevo documento', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      const Text(
        'Usa el PDF sintético de prueba. No selecciones documentos médicos reales.',
      ),
      const SizedBox(height: 16),
      OutlinedButton.icon(
        onPressed: () async {
          final data = await rootBundle.load('assets/synthetic.pdf');
          if (mounted) setState(() => bytes = data.buffer.asUint8List());
        },
        icon: const Icon(Icons.science_outlined),
        label: const Text('Usar PDF de prueba'),
      ),
      TextButton.icon(
        onPressed: selectPdf,
        icon: const Icon(Icons.attach_file),
        label: const Text('Seleccionar PDF de prueba'),
      ),
      if (bytes != null) ...[
        Text('PDF seleccionado · ${bytes!.length} bytes'),
        TextButton.icon(
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => SyntheticPdfScreen(
                load: () async => verifiedSyntheticBytes(bytes!),
              ),
            ),
          ),
          icon: const Icon(Icons.picture_as_pdf_outlined),
          label: const Text('Ver documento'),
        ),
      ],
      const SizedBox(height: 16),
      LabeledField(
        label: 'Título del documento',
        child: TextField(
          controller: title,
          maxLength: 200,
          decoration: const InputDecoration(),
        ),
      ),
      LabeledField(
        label: 'Fecha del examen',
        child: TextField(
          controller: date,
          keyboardType: TextInputType.datetime,
          decoration: const InputDecoration(hintText: 'AAAA-MM-DD'),
        ),
      ),
      const Padding(
        padding: EdgeInsets.only(top: 4),
        child: Text(
          'Fecha registrada del examen; puede diferir de la fecha de muestra del PDF.',
        ),
      ),
      CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        value: synthetic,
        onChanged: (v) => setState(() => synthetic = v ?? false),
        title: const Text('Confirmo que solo uso datos sintéticos.'),
      ),
      CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        value: consent,
        onChanged: (v) => setState(() => consent = v ?? false),
        title: const Text('Autorizo el procesamiento sintético del documento.'),
      ),
      if (error != null)
        Text(
          error!,
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
                    () => error =
                        widget.c.message ?? 'No se guardó la operación.',
                  );
                }
              },
        icon: const Icon(Icons.save_outlined),
        label: const Text('Guardar en pendientes'),
      ),
      const SizedBox(height: 12),
      const Text('Guardar no envía el archivo ni elimina el original.'),
    ],
  );
}
