import '../l10n/localized_copy.dart';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../application/patient_controller.dart';
import '../domain/models.dart';
import '../domain/extraction_draft.dart';
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
  String? localDocumentHash;
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
      final local = await widget.c.documentWithIntegrity(widget.exam.id);
      if (!mounted) return;
      setState(() {
        detail = d;
        hasDocument = local != null;
        localDocumentHash = local?.sha256;
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
      Json x;
      try {
        x = await widget.c.extraction(widget.exam.id);
      } on ApiFailure catch (e) {
        if (e.code != 'EXTRACTION_NOT_READY' &&
            e.code != 'EXTRACTION_PROCESSING_FAILED') {
          rethrow;
        }
        if (!mounted) return;
        setState(() {
          extraction = null;
          draft = null;
          frozen = null;
          key = null;
          conflict = false;
          error = 'errorExtractionNotReady';
        });
        return;
      }
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
                    ? 'extractionUnavailable'
                    : 'examUnavailable'
              : e.message;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          if (draft != null) conflict = true;
          error = 'proposalReadFailed';
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
              ? context.l10n.discardQuestion
              : context.l10n.reviewConfirmation,
          action == 'discard'
              ? context.l10n.discardWarning
              : context.l10n.submissionSummary(
                  draft!.summaryWith(context.l10n.safeMessage),
                ),
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
            setState(() => latestStatus = current['status'] as String);
          }
        } on ApiFailure {
          /* Keep the blocked draft; no silent replacement. */
        }
      }
    } catch (_) {
      if (mounted) {
        setState(() => error = 'operationInterrupted');
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
    required String fieldId,
  }) => LabeledField(
    key: ValueKey(
      '${extraction?['extraction_id']}/${draft.hashCode}/$code/$fieldId',
    ),
    label: label,
    child: TextFormField(
      key: ValueKey('review/$code/$fieldId'),
      initialValue: initial,
      enabled: editable && !loading && !sending && frozen == null && !conflict,
      keyboardType: keyboard,
      decoration: InputDecoration(
        hintText: keyboard == TextInputType.datetime
            ? context.l10n.isoDateHint
            : null,
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
            Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text(context.l10n.lowConfidenceHint),
            ),
          if (editable) ...[
            LayoutBuilder(
              builder: (context, box) {
                final value = field(
                  context.l10n.valueLabel,
                  m.value,
                  (v) => m.value = v,
                  code: m.code,
                  fieldId: 'value',
                );
                final unit = field(
                  context.l10n.unitLabel,
                  m.unit,
                  (v) => m.unit = v,
                  code: m.code,
                  fieldId: 'unit',
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
              title: Text(context.l10n.documentReference),
              children: [
                field(
                  context.l10n.lowerLimit,
                  m.low,
                  (v) => m.low = v,
                  code: m.code,
                  keyboard: const TextInputType.numberWithOptions(
                    decimal: true,
                    signed: true,
                  ),
                  fieldId: 'reference-low',
                ),
                field(
                  context.l10n.upperLimit,
                  m.high,
                  (v) => m.high = v,
                  code: m.code,
                  keyboard: const TextInputType.numberWithOptions(
                    decimal: true,
                    signed: true,
                  ),
                  fieldId: 'reference-high',
                ),
                field(
                  context.l10n.referenceUnit,
                  m.referenceUnit,
                  (v) => m.referenceUnit = v,
                  code: m.code,
                  fieldId: 'reference-unit',
                ),
                field(
                  context.l10n.referenceText,
                  m.referenceText,
                  (v) => m.referenceText = v,
                  code: m.code,
                  fieldId: 'reference-text',
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
                context.l10n.referenceDescription(
                  m.low,
                  m.high,
                  m.referenceUnit,
                  m.referenceText,
                ),
              ),
          ],
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(context.l10n.examDetail)),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            detail?['title'] as String? ?? widget.exam.title,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text(
            localizedClinicalDate(
              context,
              detail?['test_date'] as String? ?? widget.exam.date,
            ),
          ),
          Text(
            localizedExamLabel(
              context,
              detail?['status'] as String? ?? widget.exam.status,
            ),
          ),
          Text(
            context.l10n.professionalReview(
              (detail?['review'] as Map?)?['status'] == 'reviewed'
                  ? context.l10n.reviewCompleted
                  : context.l10n.reviewPendingUnknown,
            ),
          ),
          if (detail?['review'] case final Map review)
            if (review['status'] == 'reviewed')
              if (review['patient_message'] case final String message)
                if (message.trim().isNotEmpty)
                  OutlinedButton.icon(
                    icon: const Icon(Icons.assignment_turned_in_outlined),
                    label: Text(context.l10n.viewReviewResult),
                    onPressed: () => showDialog<void>(
                      context: context,
                      builder: (dialogContext) => AlertDialog(
                        title: Text(context.l10n.reviewResultTitle),
                        content: SingleChildScrollView(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(context.l10n.reviewResultLabel),
                              const SizedBox(height: 8),
                              SelectableText(message),
                            ],
                          ),
                        ),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.of(dialogContext).pop(),
                            child: Text(context.l10n.closeResult),
                          ),
                        ],
                      ),
                    ),
                  ),
          if (localizedTestTypeLabel(
                context,
                detail?['test_type'] as String? ?? widget.exam.testType,
              )
              case final String type)
            Text(type),
          if (detail?['file'] case final Map file) ...[
            if (file['name'] case final String name)
              Text(context.l10n.fileName(name)),
            if (file['size_bytes'] case final num size)
              Text(context.l10n.fileSize(size.toInt())),
          ],
          if (detail?['notes'] case final String notes)
            if (notes.isNotEmpty) Text(context.l10n.patientNotes(notes)),
          if ([
            'initiated',
            'object_uploaded',
            'processing',
          ].contains(detail?['status']))
            Text(context.l10n.stillProcessing),
          if (['rejected', 'failed'].contains(detail?['status']))
            Text(context.l10n.documentCannotConfirm),
          const SizedBox(height: 12),
          Text(
            context.l10n.syntheticNoClinical,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          if (hasDocument)
            OutlinedButton.icon(
              icon: const Icon(Icons.picture_as_pdf_outlined),
              label: Text(context.l10n.viewDocument),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => SyntheticPdfScreen(
                    expectedSha256: localDocumentHash!,
                    load: () async {
                      final bytes = await widget.c.document(widget.exam.id);
                      if (bytes == null) {
                        throw const FormatException('Document unavailable');
                      }
                      return verifiedSyntheticBytes(
                        bytes,
                        expectedSha256: localDocumentHash!,
                      );
                    },
                  ),
                ),
              ),
            ),
          if (!hasDocument && !loading) Text(context.l10n.noVerifiedCopy),
          if (loading || sending) const LinearProgressIndicator(),
          if (error != null)
            Semantics(
              liveRegion: true,
              child: Text(
                context.l10n.safeMessage(error!),
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (latestStatus != null)
            Text(
              context.l10n.currentServerState(
                localizedExtractionLabel(context, latestStatus!),
              ),
            ),
          if (extraction != null) ...[
            if (!editable && draft!.collectionDate.isNotEmpty)
              Text(
                context.l10n.sampleDate(
                  localizedClinicalDate(context, draft!.collectionDate),
                ),
              ),
            if (!editable && draft!.reportDate.isNotEmpty)
              Text(
                context.l10n.reportDate(
                  localizedClinicalDate(context, draft!.reportDate),
                ),
              ),
            const SizedBox(height: 20),
            Text(
              localizedExtractionLabel(
                context,
                extraction!['status'] as String,
              ),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (editable)
              Text(context.l10n.compareProposal)
            else if (extraction!['status'] == 'confirmed') ...[
              Text(context.l10n.confirmationReceived),
              if ((extraction!['confirmation'] as Map?)?['confirmed_at']
                  case final String date)
                Text(
                  context.l10n.confirmedOn(
                    localizedConfirmationTime(context, date),
                  ),
                ),
            ] else
              Text(context.l10n.noNewConfirmation),
            for (final panel in draft!.markers.map((m) => m.panel).toSet()) ...[
              Padding(
                padding: const EdgeInsets.only(top: 16, bottom: 8),
                child: Text(
                  panel.isEmpty ? context.l10n.panelUnnamed : panel,
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
              for (final m in draft!.markers.where((m) => m.panel == panel))
                marker(m),
            ],
            if (editable) ...[
              ExpansionTile(
                title: Text(context.l10n.documentDates),
                children: [
                  field(
                    context.l10n.collectionDateLabel,
                    draft!.collectionDate,
                    (v) => draft!.collectionDate = v,
                    keyboard: TextInputType.datetime,
                    fieldId: 'collection-date',
                  ),
                  field(
                    context.l10n.reportDateLabel,
                    draft!.reportDate,
                    (v) => draft!.reportDate = v,
                    keyboard: TextInputType.datetime,
                    fieldId: 'report-date',
                  ),
                ],
              ),
              CheckboxListTile(
                value: identity,
                onChanged: frozen == null && !sending && !conflict
                    ? (v) => setState(() => identity = v ?? false)
                    : null,
                title: Text(context.l10n.identityAcknowledgement),
              ),
              CheckboxListTile(
                value: checked,
                onChanged: frozen == null && !sending && !conflict
                    ? (v) => setState(() => checked = v ?? false)
                    : null,
                title: Text(context.l10n.valuesAcknowledgement),
              ),
              FilledButton(
                onPressed: identity && checked && !sending && !conflict
                    ? () => submit('confirm')
                    : null,
                child: Text(
                  frozen == null
                      ? context.l10n.reviewConfirm
                      : context.l10n.retrySameSubmission,
                ),
              ),
              TextButton(
                onPressed: !sending && frozen == null && !conflict
                    ? () => submit('discard')
                    : null,
                child: Text(context.l10n.discardProposal),
              ),
            ] else
              Text(context.l10n.serverDeterminesStatus),
          ],
          const SizedBox(height: 16),
        ],
      ),
    ),
  );
}
