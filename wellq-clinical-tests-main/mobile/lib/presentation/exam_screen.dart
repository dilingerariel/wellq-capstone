import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../application/patient_controller.dart';
import '../domain/models.dart';
import '../domain/extraction_draft.dart';
import '../domain/patient_labels.dart';
import '../domain/patient_dates.dart';
import 'patient_widgets.dart';
import 'patient_dialogs.dart';
import 'synthetic_pdf_screen.dart';

class ExamScreen extends StatefulWidget {
  const ExamScreen({super.key, required this.c, required this.exam});
  final PatientController c;
  final Exam exam;
  @override
  State<ExamScreen> createState() => _ExamScreenState();
}

class _ExamScreenState extends State<ExamScreen> {
  Json? detail, extraction, frozen;
  ExtractionDraft? draft;
  String? error, key, latestStatus;
  bool loading = true,
      identity = false,
      checked = false,
      sending = false,
      conflict = false,
      hasDocument = false;
  bool get editable =>
      extraction?['status'] == 'awaiting_confirmation' &&
      widget.c.session?.permissions.contains('extractions:confirm') == true;
  Future<void> load() async {
    var detailRead = false;
    setState(() => loading = true);
    try {
      final d = await widget.c.detail(widget.exam.id);
      detailRead = true;
      if (!mounted) return;
      final local = await widget.c.document(widget.exam.id);
      if (!mounted) return;
      setState(() {
        detail = d;
        hasDocument = local != null;
      });
      if (['rejected', 'failed'].contains(d['status'])) {
        setState(() {
          extraction = null;
          draft = null;
          frozen = null;
          key = null;
          error = null;
          conflict = false;
          latestStatus = null;
          identity = false;
          checked = false;
        });
        return;
      }
      final x = await widget.c.extraction(widget.exam.id);
      final review = ExtractionDraft(x);
      if (!mounted) return;
      setState(() {
        extraction = x;
        draft = review;
        frozen = null;
        key = null;
        conflict = false;
        latestStatus = null;
        identity = false;
        checked = false;
        error = null;
      });
    } on ApiFailure catch (e) {
      if (mounted) {
        setState(() {
          if (draft != null) conflict = true;
          error = e.status == 404
              ? detailRead
                    ? 'La extracción aún no está disponible. Consulta nuevamente.'
                    : 'El examen no está disponible o ya no existe en esta vista.'
              : e.message;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          if (draft != null) conflict = true;
          error = 'No se pudo leer la propuesta. Consulta nuevamente.';
        });
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> submit(String action) async {
    if (sending || loading || conflict || !editable) return;
    try {
      if (frozen == null) {
        final body = draft!.body(action, identity);
        final yes = await ask(
          context,
          action == 'discard'
              ? '¿Descartar propuesta?'
              : 'Revisar confirmación',
          action == 'discard'
              ? 'Se descartará esta propuesta. No se elimina el documento.'
              : '${draft!.summary}\n\nOriginal → revisión. Confirmación humana, sin validación clínica.',
        );
        if (!yes || !mounted) return;
        frozen = body;
        key = const Uuid().v4();
      }
      setState(() => sending = true);
      final result = await widget.c.confirm(widget.exam.id, frozen!, key!);
      if (!mounted) return;
      setState(() {
        extraction = result;
        draft = ExtractionDraft(result);
        frozen = null;
        key = null;
        error = null;
      });
      // Refresh reads after an explicit, successful mutation. Never replay it.
      await widget.c.refresh();
      final current = await widget.c.detail(widget.exam.id);
      if (mounted) setState(() => detail = current);
    } on FormatException catch (e) {
      if (mounted) setState(() => error = e.message);
    } on ApiFailure catch (e) {
      if (!mounted) return;
      setState(() {
        error = e.message;
        conflict = e.conflict;
        if (e.status == 422) {
          frozen = null;
          key = null;
        }
      });
      if (e.conflict) {
        try {
          final current = await widget.c.extraction(widget.exam.id);
          if (mounted) {
            setState(
              () => latestStatus = extractionLabel(current['status'] as String),
            );
          }
        } on ApiFailure {
          /* Keep the blocked draft; no silent replacement. */
        }
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => error =
              'Operación interrumpida. Consulta el estado antes de reintentar.',
        );
      }
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  Widget field(
    String label,
    String initial,
    ValueChanged<String> change, {
    TextInputType? keyboard,
    String code = 'document',
  }) => LabeledField(
    key: ValueKey(
      '${extraction?['extraction_id']}/${draft.hashCode}/$code/$label',
    ),
    label: label,
    child: TextFormField(
      key: ValueKey('review/$code/$label'),
      initialValue: initial,
      enabled: editable && !loading && !sending && frozen == null && !conflict,
      keyboardType: keyboard,
      decoration: InputDecoration(
        hintText: keyboard == TextInputType.datetime ? 'AAAA-MM-DD' : null,
        isDense: true,
        border: const OutlineInputBorder(),
        contentPadding: const EdgeInsets.all(12),
      ),
      onChanged: change,
    ),
  );
  Widget marker(MarkerDraft m) => Card.outlined(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(m.name, style: Theme.of(context).textTheme.titleMedium),
          if (m.lowConfidence)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text(
                'Baja confianza: coteja este marcador con el documento original.',
              ),
            ),
          if (editable) ...[
            LayoutBuilder(
              builder: (context, box) {
                final value = field(
                  'Valor',
                  m.value,
                  (v) => m.value = v,
                  code: m.code,
                );
                final unit = field(
                  'Unidad',
                  m.unit,
                  (v) => m.unit = v,
                  code: m.code,
                );
                return box.maxWidth >= 280 &&
                        MediaQuery.textScalerOf(context).scale(14) <= 19
                    ? Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(child: value),
                          const SizedBox(width: 12),
                          Expanded(child: unit),
                        ],
                      )
                    : Column(children: [value, unit]);
              },
            ),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: const Text('Referencia del documento'),
              children: [
                field(
                  'Límite inferior',
                  m.low,
                  (v) => m.low = v,
                  code: m.code,
                  keyboard: const TextInputType.numberWithOptions(
                    decimal: true,
                    signed: true,
                  ),
                ),
                field(
                  'Límite superior',
                  m.high,
                  (v) => m.high = v,
                  code: m.code,
                  keyboard: const TextInputType.numberWithOptions(
                    decimal: true,
                    signed: true,
                  ),
                ),
                field(
                  'Unidad de referencia',
                  m.referenceUnit,
                  (v) => m.referenceUnit = v,
                  code: m.code,
                ),
                field(
                  'Texto de referencia',
                  m.referenceText,
                  (v) => m.referenceText = v,
                  code: m.code,
                ),
              ],
            ),
          ] else ...[
            const SizedBox(height: 8),
            Text('${m.value} ${m.unit}'),
            if (m.low.isNotEmpty ||
                m.high.isNotEmpty ||
                m.referenceText.isNotEmpty)
              Text(
                'Referencia del documento: ${m.low} – ${m.high} ${m.referenceUnit} ${m.referenceText}',
              ),
          ],
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Detalle del examen')),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            detail?['title'] as String? ?? widget.exam.title,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text(
            clinicalDate(detail?['test_date'] as String? ?? widget.exam.date),
          ),
          Text(examLabel(detail?['status'] as String? ?? widget.exam.status)),
          Text(
            'Revisión profesional: ${(detail?['review'] as Map?)?['status'] == 'reviewed' ? 'completada' : 'pendiente o no informada'}',
          ),
          if (testTypeLabel(
                detail?['test_type'] as String? ?? widget.exam.testType,
              )
              case final String type)
            Text(type),
          if (detail?['file'] case final Map file) ...[
            if (file['name'] case final String name) Text('Archivo: $name'),
            if (file['size_bytes'] case final num size)
              Text('Tamaño: ${size.toInt()} bytes'),
          ],
          if (detail?['notes'] case final String notes)
            if (notes.isNotEmpty) Text('Tus notas: $notes'),
          if ([
            'initiated',
            'object_uploaded',
            'processing',
          ].contains(detail?['status']))
            const Text(
              'El documento aún no termina de procesarse. Consulta el estado; no necesitas cargarlo otra vez.',
            ),
          if (['rejected', 'failed'].contains(detail?['status']))
            const Text(
              'Este documento no está disponible para confirmar. Se conserva la copia local; consulta el estado antes de preparar otro.',
            ),
          const SizedBox(height: 12),
          Text(
            'Entorno sintético · Sin uso clínico',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          if (hasDocument)
            OutlinedButton.icon(
              icon: const Icon(Icons.picture_as_pdf_outlined),
              label: const Text('Ver documento'),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => SyntheticPdfScreen(
                    load: () async {
                      final bytes = await widget.c.document(widget.exam.id);
                      if (bytes == null) {
                        throw const FormatException('Document unavailable');
                      }
                      return verifiedSyntheticBytes(bytes);
                    },
                  ),
                ),
              ),
            ),
          if (!hasDocument && !loading)
            const Text(
              'No hay una copia sintética verificada en este dispositivo. No se descargan documentos arbitrarios.',
            ),
          if (loading || sending) const LinearProgressIndicator(),
          if (error != null)
            Semantics(
              liveRegion: true,
              child: Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (latestStatus != null)
            Text(
              'Estado actual del servidor: $latestStatus. Revisa la propuesta actual antes de continuar.',
            ),
          if (extraction != null) ...[
            if (!editable && draft!.collectionDate.isNotEmpty)
              Text('Fecha de muestra: ${clinicalDate(draft!.collectionDate)}'),
            if (!editable && draft!.reportDate.isNotEmpty)
              Text('Fecha de informe: ${clinicalDate(draft!.reportDate)}'),
            const SizedBox(height: 20),
            Text(
              extractionLabel(extraction!['status'] as String),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (editable)
              const Text(
                'Coteja la propuesta con el PDF sintético original. No es un diagnóstico.',
              )
            else if (extraction!['status'] == 'confirmed') ...[
              const Text(
                'La confirmación ya fue recibida. Puede faltar la revisión profesional.',
              ),
              if ((extraction!['confirmation'] as Map?)?['confirmed_at']
                  case final String date)
                Text('Confirmado: ${confirmationTime(date)}'),
            ] else
              const Text(
                'Consulta el estado del examen. No se requiere una nueva confirmación.',
              ),
            for (final panel in draft!.markers.map((m) => m.panel).toSet()) ...[
              Padding(
                padding: const EdgeInsets.only(top: 16, bottom: 8),
                child: Text(
                  panel,
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
              for (final m in draft!.markers.where((m) => m.panel == panel))
                marker(m),
            ],
            if (editable) ...[
              ExpansionTile(
                title: const Text('Fechas del documento'),
                children: [
                  field(
                    'Fecha de muestra',
                    draft!.collectionDate,
                    (v) => draft!.collectionDate = v,
                    keyboard: TextInputType.datetime,
                  ),
                  field(
                    'Fecha de informe',
                    draft!.reportDate,
                    (v) => draft!.reportDate = v,
                    keyboard: TextInputType.datetime,
                  ),
                ],
              ),
              CheckboxListTile(
                value: identity,
                onChanged: frozen == null && !sending && !conflict
                    ? (v) => setState(() => identity = v ?? false)
                    : null,
                title: const Text(
                  'He comprobado que este documento me corresponde.',
                ),
              ),
              CheckboxListTile(
                value: checked,
                onChanged: frozen == null && !sending && !conflict
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
                      ? 'Revisar y confirmar'
                      : 'Reintentar el mismo envío',
                ),
              ),
              TextButton(
                onPressed: !sending && frozen == null && !conflict
                    ? () => submit('discard')
                    : null,
                child: const Text('Descartar propuesta'),
              ),
            ] else
              const Text(
                'Estado determinado por FastAPI. No equivale a validación profesional.',
              ),
          ],
          const SizedBox(height: 16),
          OutlinedButton(
            onPressed: sending || loading
                ? null
                : () async {
                    if (draft != null &&
                        editable &&
                        !await ask(
                          context,
                          '¿Consultar estado actual?',
                          'Se descartará el borrador y se consultará la propuesta vigente. No se reenviará ninguna mutación.',
                        )) {
                      return;
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
