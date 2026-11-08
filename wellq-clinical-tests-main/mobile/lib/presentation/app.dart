import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:file_picker/file_picker.dart';
import 'package:uuid/uuid.dart';

import '../application/patient_controller.dart';
import '../domain/models.dart';

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
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
        ),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
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
      ListView(padding: const EdgeInsets.all(20), children: children);
  Widget heading(String title, String subtitle) => Padding(
    padding: const EdgeInsets.only(bottom: 20),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(
            context,
          ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
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
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          color: Theme.of(context).colorScheme.secondaryContainer,
          child: Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              Icon(
                c.online ? Icons.cloud_done_outlined : Icons.cloud_off_outlined,
                size: 20,
              ),
              Text(c.online ? 'FastAPI conectado' : 'Conexión no verificada'),
              const Text(AppCopy.warning),
            ],
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
              : switch (tab) {
                  0 => dashboard(),
                  1 => exams(),
                  2 => UploadScreen(
                    c: c,
                    queued: () => setState(() => tab = 3),
                  ),
                  3 => pending(),
                  _ => settings(),
                },
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
                              icon: Icon(icons[i]),
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
              ? NavigationBar(
                  selectedIndex: tab,
                  labelBehavior:
                      NavigationDestinationLabelBehavior.onlyShowSelected,
                  onDestinationSelected: (v) => setState(() => tab = v),
                  destinations: [
                    for (var i = 0; i < 5; i++)
                      NavigationDestination(
                        icon: Icon(icons[i]),
                        label: labels[i],
                      ),
                  ],
                )
              : null,
        );
      },
    );
  }

  Widget welcome() => page([
    const SizedBox(height: 24),
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
      'Consulta tus exámenes y acompaña cada paso de su carga.',
    ),
    const Text(
      'Primera fase móvil. Identidad, IA, antivirus y almacenamiento sintéticos. No uses información médica real.',
    ),
    const SizedBox(height: 24),
    FilledButton.icon(
      onPressed: c.busy ? null : c.connect,
      icon: const Icon(Icons.login),
      label: const Text('Conectar paciente sintético'),
    ),
    const SizedBox(height: 16),
    const Text(
      'Requiere WellQ encendido en el host. No existe login productivo en esta versión.',
    ),
  ]);
  Widget dashboard() => page([
    heading('Hola, paciente', 'Documentos claros, bajo tu control.'),
    Card.filled(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.favorite_outline, size: 32),
            const SizedBox(height: 12),
            Text(
              'Un lugar para tus exámenes',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            const Text(
              'Carga el PDF sintético, revisa sus datos y confirma. La confirmación humana no es una validación clínica.',
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () => setState(() => tab = 2),
              child: const Text('Cargar documento'),
            ),
          ],
        ),
      ),
    ),
    const SizedBox(height: 16),
    Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        Chip(label: Text('${c.exams.length} exámenes en esta vista')),
        Chip(
          label: Text(
            '${c.operations.where((o) => !o.finished).length} pendientes locales',
          ),
        ),
      ],
    ),
    const SizedBox(height: 16),
    const Text(
      'No se muestran scores ni interpretaciones clínicas en el móvil.',
    ),
    TextButton(
      onPressed: () => setState(() => tab = 1),
      child: const Text('Ver mis exámenes'),
    ),
  ]);
  Widget exams() => page([
    heading(
      'Mis exámenes',
      c.online
          ? 'Lectura autorizada de FastAPI'
          : 'Última lectura disponible. No confirma cambios del servidor.',
    ),
    if (c.exams.isEmpty)
      const Padding(
        padding: EdgeInsets.all(24),
        child: Text(
          'Sin exámenes en esta vista. Actualiza o carga el PDF sintético.',
        ),
      ),
    for (final exam in c.exams)
      Card(
        child: ListTile(
          contentPadding: const EdgeInsets.all(16),
          leading: const Icon(Icons.description_outlined),
          title: Text(exam.title),
          subtitle: Text('${exam.date}\n${phaseLabel(exam.status)}'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => open(exam),
        ),
      ),
    if (c.cursor != null)
      OutlinedButton(
        onPressed: c.busy ? null : () => c.refresh(more: true),
        child: const Text('Cargar más'),
      ),
    TextButton(
      onPressed: c.busy ? null : c.refresh,
      child: const Text('Actualizar listado'),
    ),
  ]);
  Widget pending() => page([
    heading(
      'Operaciones pendientes',
      'Drift conserva identificadores y bytes sintéticos. Reconectar solo consulta estados.',
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
              Text('Intentos: ${op.attempts} · Versión local: ${op.version}'),
              if (op.error != null)
                const Text(
                  'El último intento no terminó. Consulta el estado antes de reintentar.',
                ),
              if (op.canDelete)
                const Text(
                  'FastAPI verificó el documento. La copia local se conserva.',
                ),
              const SizedBox(height: 8),
              if (!op.finished && op.phase != 'conflict')
                FilledButton(
                  onPressed: c.busy ? null : () => c.resume(op),
                  child: const Text('Enviar o reintentar explícitamente'),
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
    heading('Tu espacio', 'Preferencias y límites de esta fase.'),
    ListTile(
      leading: const Icon(Icons.palette_outlined),
      title: const Text('Cambiar tema claro / oscuro'),
      onTap: widget.toggle,
    ),
    const ListTile(
      leading: Icon(Icons.lock_outline),
      title: Text('Identidad sintética'),
      subtitle: Text(
        'Tokens solo en RAM. Sin contraseñas ni firma JWT en Dart.',
      ),
    ),
    const ListTile(
      leading: Icon(Icons.storage_outlined),
      title: Text('SQLite de pruebas'),
      subtitle: Text(
        'Solo el PDF sintético incluido. Sin persistencia clínica productiva.',
      ),
    ),
    const ListTile(
      leading: Icon(Icons.picture_as_pdf_outlined),
      title: Text('PDF productivo bloqueado'),
      subtitle: Text('No hay exportaciones ni scores en esta fase móvil.'),
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

Future<bool> ask(BuildContext context, String title, String text) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: SingleChildScrollView(child: Text(text)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Volver'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Confirmar acción'),
          ),
        ],
      ),
    ) ??
    false;

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
  @override
  void dispose() {
    title.dispose();
    date.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(20),
    children: [
      Text(
        'Nuevo documento',
        style: Theme.of(context).textTheme.headlineMedium,
      ),
      const SizedBox(height: 8),
      const Text(
        'Solo se admite el PDF sintético incluido, también si lo eliges desde Archivos. Su SHA-256 se verifica antes de copiarlo.',
      ),
      const SizedBox(height: 16),
      OutlinedButton.icon(
        onPressed: () async {
          final data = await rootBundle.load('assets/synthetic.pdf');
          if (mounted) setState(() => bytes = data.buffer.asUint8List());
        },
        icon: const Icon(Icons.science_outlined),
        label: const Text('Usar PDF sintético incluido'),
      ),
      TextButton.icon(
        onPressed: () async {
          final r = await FilePicker.pickFiles(
            type: FileType.custom,
            allowedExtensions: ['pdf'],
          );
          if (r.isNotEmpty) {
            final length = await r.single.length();
            if (length == null || length > 20 * 1024 * 1024) {
              if (mounted) setState(() => error = 'El archivo excede 20 MiB.');
              return;
            }
            final selected = await r.single.readAsBytes();
            if (mounted) setState(() => bytes = selected);
          }
        },
        icon: const Icon(Icons.attach_file),
        label: const Text('Seleccionar PDF de prueba'),
      ),
      if (bytes != null) Text('PDF seleccionado · ${bytes!.length} bytes'),
      const SizedBox(height: 16),
      TextField(
        controller: title,
        maxLength: 200,
        decoration: const InputDecoration(labelText: 'Título del documento'),
      ),
      const SizedBox(height: 12),
      TextField(
        controller: date,
        keyboardType: TextInputType.datetime,
        decoration: const InputDecoration(
          labelText: 'Fecha del examen (AAAA-MM-DD)',
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
      const Text(
        'Guardar no envía el archivo. Inicia el envío explícitamente en Pendientes. Nunca se elimina el original.',
      ),
    ],
  );
}

class ExamScreen extends StatefulWidget {
  const ExamScreen({super.key, required this.c, required this.exam});
  final PatientController c;
  final Exam exam;
  @override
  State<ExamScreen> createState() => _ExamScreenState();
}

class _ExamScreenState extends State<ExamScreen> {
  Json? detail, extraction, frozen;
  String? error, key;
  bool loading = true,
      identity = false,
      checked = false,
      sending = false,
      conflict = false;
  final fields =
      <String, (TextEditingController, TextEditingController, Json)>{};
  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    for (final f in fields.values) {
      f.$1.dispose();
      f.$2.dispose();
    }
    super.dispose();
  }

  Future<void> load() async {
    try {
      final d = await widget.c.detail(widget.exam.id);
      if (!mounted) return;
      setState(() => detail = d);
      final x = await widget.c.extraction(widget.exam.id);
      if (!mounted) return;
      for (final f in fields.values) {
        f.$1.dispose();
        f.$2.dispose();
      }
      fields.clear();
      for (final p in x['panels'] as List) {
        for (final item in (p as Map)['markers'] as List) {
          final m = Map<String, dynamic>.from(item as Map);
          fields[m['marker_code'] as String] = (
            TextEditingController(text: m['value_raw'] as String),
            TextEditingController(text: m['unit_raw'] as String),
            m,
          );
        }
      }
      setState(() {
        extraction = x;
        loading = false;
        error = null;
        frozen = null;
        key = null;
        conflict = false;
        identity = false;
        checked = false;
      });
    } on ApiFailure catch (e) {
      if (mounted) {
        setState(() {
          loading = false;
          error = e.status == 404
              ? 'La extracción aún no está disponible. Consulta nuevamente.'
              : e.message;
        });
      }
    }
  }

  Future<void> submit(String action) async {
    if (sending) return;
    final body =
        frozen ??
        {
          'action': action,
          'extraction_id': extraction!['extraction_id'],
          'document_edits': {'identity_confirmed': identity},
          'acknowledged_marker_codes': fields.keys.toList(),
          'marker_edits': [
            for (final e in fields.entries)
              if (e.value.$1.text != e.value.$3['value_raw'] ||
                  e.value.$2.text != e.value.$3['unit_raw'])
                {
                  'op': 'update',
                  'marker_code': e.key,
                  'value_raw': e.value.$1.text,
                  'unit_raw': e.value.$2.text,
                },
          ],
        };
    if (frozen == null) {
      final yes = await ask(
        context,
        action == 'discard' ? '¿Descartar propuesta?' : 'Revisar confirmación',
        '${fields.entries.map((e) => '${e.key}: ${e.value.$1.text} ${e.value.$2.text}').join('\n')}\n\nConfirmación humana. No es validación clínica.',
      );
      if (!yes || !mounted) return;
      frozen = body;
      key = const Uuid().v4();
    }
    setState(() => sending = true);
    try {
      final result = await widget.c.confirm(widget.exam.id, frozen!, key!);
      if (mounted) {
        setState(() {
          extraction = result;
          error = null;
          frozen = null;
        });
      }
    } on ApiFailure catch (e) {
      if (mounted) {
        setState(() {
          error = e.message;
          conflict = e.conflict;
          if (e.status == 422) {
            frozen = null;
            key = null;
          }
        });
      }
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final editable = extraction?['status'] == 'awaiting_confirmation';
    return Scaffold(
      appBar: AppBar(title: const Text('Detalle del examen')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Text(
              detail?['title'] as String? ?? widget.exam.title,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            Text(detail?['test_date'] as String? ?? widget.exam.date),
            Text(detail?['status'] as String? ?? widget.exam.status),
            const SizedBox(height: 12),
            const Text(AppCopy.warning),
            if (loading) const LinearProgressIndicator(),
            if (error != null)
              Semantics(
                liveRegion: true,
                child: Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (extraction != null) ...[
              const SizedBox(height: 20),
              Text('Extracción: ${extraction!['status']}'),
              const Text(
                'Coteja la propuesta con el PDF sintético original. No es un diagnóstico.',
              ),
              for (final e in fields.entries)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(e.value.$3['raw_name'] as String),
                        const SizedBox(height: 12),
                        TextField(
                          controller: e.value.$1,
                          enabled: editable && frozen == null,
                          decoration: InputDecoration(
                            labelText: 'Valor ${e.key}',
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: e.value.$2,
                          enabled: editable && frozen == null,
                          decoration: InputDecoration(
                            labelText: 'Unidad ${e.key}',
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              if (editable) ...[
                CheckboxListTile(
                  value: identity,
                  onChanged: frozen == null
                      ? (v) => setState(() => identity = v ?? false)
                      : null,
                  title: const Text(
                    'He comprobado que este documento me corresponde.',
                  ),
                ),
                CheckboxListTile(
                  value: checked,
                  onChanged: frozen == null
                      ? (v) => setState(() => checked = v ?? false)
                      : null,
                  title: const Text(
                    'He cotejado valores, unidades y campos de baja confianza.',
                  ),
                ),
                FilledButton(
                  onPressed: identity && checked && !sending && !conflict
                      ? () => submit('confirm')
                      : null,
                  child: Text(
                    frozen == null
                        ? 'Revisar y confirmar datos'
                        : 'Reintentar el mismo envío',
                  ),
                ),
                TextButton(
                  onPressed: !sending && frozen == null
                      ? () => submit('discard')
                      : null,
                  child: const Text('Descartar propuesta'),
                ),
              ],
              if (!editable)
                const Text(
                  'Estado determinado por FastAPI. No equivale a validación profesional.',
                ),
            ],
            const SizedBox(height: 16),
            OutlinedButton(
              onPressed: sending
                  ? null
                  : () async {
                      if (frozen != null) {
                        if (!await ask(
                          context,
                          '¿Consultar estado actual?',
                          'Se descartará el borrador. La lectura mostrará si FastAPI recibió la confirmación; no se reenviará ninguna mutación.',
                        )) {
                          return;
                        }
                      }
                      await load();
                    },
              child: const Text('Consultar propuesta actual'),
            ),
          ],
        ),
      ),
    );
  }
}
