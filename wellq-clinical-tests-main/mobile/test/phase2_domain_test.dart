import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:wellq_mobile/domain/extraction_draft.dart';
import 'package:wellq_mobile/domain/patient_labels.dart';
import 'package:wellq_mobile/presentation/synthetic_pdf_screen.dart';

Map<String, dynamic> proposal() => {
  'extraction_id': 'proposal-version-1',
  'status': 'awaiting_confirmation',
  'document': {'collection_date': '2026-11-08'},
  'flags': [
    {'code': 'low_confidence', 'marker_code': 'glucose'},
  ],
  'panels': [
    {
      'panel_name_raw': 'SYNTHETIC panel',
      'markers': [
        {
          'marker_code': 'glucose',
          'raw_name': 'SYNTHETIC glucose',
          'value_raw': '90',
          'unit_raw': 'mg/dL',
          'reference': {
            'low': 70.0,
            'high': 100.0,
            'unit': 'mg/dL',
            'source': 'document',
            'text_raw': 'SYNTHETIC reference',
          },
        },
      ],
    },
  ],
};

void main() {
  test(
    'patient labels distinguish extraction, examination and upload states',
    () {
      expect(
        examLabel('ready_for_review'),
        'Pendiente de revisión profesional',
      );
      expect(
        extractionLabel('awaiting_confirmation'),
        'Esperando tu confirmación',
      );
      expect(extractionLabel('confirmed'), 'Datos confirmados');
      expect(uploadLabel('confirmed'), 'Documento verificado');
      expect(
        examLabel('ready_for_review', review: 'reviewed'),
        'Con revisión profesional',
      );
      expect(testTypeLabel('blood_test'), 'Examen de sangre');
      expect(testTypeLabel('unknown'), isNull);
      for (final label in [
        examLabel('UNKNOWN_PRIVATE'),
        extractionLabel('UNKNOWN_PRIVATE'),
        uploadLabel('UNKNOWN_PRIVATE'),
      ]) {
        expect(label, 'Estado por consultar');
      }
      for (final state in [
        'queued',
        'extracting',
        'extraction_failed',
        'unreadable',
        'discarded',
        'rejected',
        'not_applicable',
        'clinically_validated',
      ]) {
        expect(extractionLabel(state), isNot(state));
      }
    },
  );
  test(
    'authorized transcription edits preserve original, panel and identifiers',
    () {
      final original = proposal();
      final snapshot = jsonEncode(original);
      final draft = ExtractionDraft(original);
      final m = draft.markers.single;
      expect(m.lowConfidence, isTrue);
      expect(m.panel, 'SYNTHETIC panel');
      expect(draft.body('confirm', true)['marker_edits'], isEmpty);
      m.value = '91';
      m.low = '71';
      draft.reportDate = '2026-11-08';
      final body = draft.body('confirm', true);
      expect(body['extraction_id'], 'proposal-version-1');
      expect(body['acknowledged_marker_codes'], ['glucose']);
      expect(body['document_edits'], {
        'identity_confirmed': true,
        'report_date': '2026-11-08',
      });
      final edit = (body['marker_edits'] as List).single as Map;
      expect(edit['op'], 'update');
      expect(edit['value_raw'], '91');
      expect(edit['unit_raw'], 'mg/dL');
      expect((edit['reference'] as Map)['low'], 71.0);
      expect(draft.summary, contains('90 mg/dL → 91 mg/dL'));
      expect(draft.summary, contains('Referencia original'));
      expect(jsonEncode(original), snapshot);
      expect(draft.body('discard', false), {
        'action': 'discard',
        'extraction_id': 'proposal-version-1',
      });
    },
  );
  test(
    'invalid reference, missing value and invalid dates block submission',
    () {
      final d = ExtractionDraft(proposal());
      final m = d.markers.single;
      m.value = '';
      expect(() => d.body('confirm', true), throwsFormatException);
      m.value = '90';
      m.low = 'NaN';
      expect(() => d.body('confirm', true), throwsFormatException);
      m.low = '110';
      expect(() => d.body('confirm', true), throwsFormatException);
      m.low = '70';
      d.collectionDate = '2026-02-31';
      expect(() => d.body('confirm', true), throwsFormatException);
      d.collectionDate = '';
      expect(() => d.body('confirm', true), throwsFormatException);
    },
  );
  test(
    'ambiguous duplicate marker codes are rejected instead of overwritten',
    () {
      final data = proposal();
      (data['panels'] as List).add((data['panels'] as List).first);
      expect(() => ExtractionDraft(data), throwsA(anything));
    },
  );
  test(
    'synthetic viewer refuses altered, arbitrary and missing files',
    () async {
      final bytes = await File('assets/synthetic.pdf').readAsBytes();
      expect(verifiedSyntheticBytes(bytes), bytes);
      expect(
        () => verifiedSyntheticBytes(bytes.sublist(1)),
        throwsFormatException,
      );
      expect(
        () => verifiedSyntheticBytes(utf8.encode('%PDF patient data')),
        throwsFormatException,
      );
      await expectLater(
        File('assets/does-not-exist.pdf').readAsBytes(),
        throwsA(isA<FileSystemException>()),
      );
    },
  );
}
