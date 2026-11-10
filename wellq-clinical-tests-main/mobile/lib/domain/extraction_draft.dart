import 'dart:convert';
import 'models.dart';

// Editable raw transcription only. No conversion, interpretation or diagnosis.
class MarkerDraft {
  MarkerDraft(this.original, this.panel, this.flagged)
    : value = original['value_raw'] as String? ?? '',
      unit = original['unit_raw'] as String? ?? '',
      low = '${(original['reference'] as Map?)?['low'] ?? ''}',
      high = '${(original['reference'] as Map?)?['high'] ?? ''}',
      referenceUnit = (original['reference'] as Map?)?['unit'] as String? ?? '',
      referenceText =
          (original['reference'] as Map?)?['text_raw'] as String? ?? '';
  final Json original;
  final String panel;
  final bool flagged;
  String value, unit, low, high, referenceUnit, referenceText;
  String get code => original['marker_code'] as String;
  String get name => original['raw_name'] as String? ?? code;
  bool get lowConfidence =>
      flagged ||
      (original['confidence'] as Map? ?? {}).values.any(
        (v) => v is num && v < .9,
      );
  Json? get reference {
    final old = original['reference'] as Map?;
    if (low.isEmpty &&
        high.isEmpty &&
        referenceUnit.isEmpty &&
        referenceText.isEmpty &&
        old == null) {
      return null;
    }
    double? number(String text) {
      if (text.isEmpty) return null;
      final v = double.tryParse(text);
      if (v == null || !v.isFinite) {
        throw const FormatException('referenceFinite');
      }
      return v;
    }

    final l = number(low), h = number(high);
    if (l != null && h != null && l >= h) {
      throw const FormatException('referenceOrder');
    }
    return {
      'low': l,
      'high': h,
      'unit': referenceUnit.isEmpty ? null : referenceUnit,
      'text_raw': referenceText.isEmpty ? null : referenceText,
      'source': old?['source'] ?? 'document',
    };
  }

  Json? edit() {
    final old = MarkerDraft(original, panel, flagged);
    final changedReference =
        [low, high, referenceUnit, referenceText].join('\u0000') !=
        [
          old.low,
          old.high,
          old.referenceUnit,
          old.referenceText,
        ].join('\u0000');
    if (value == old.value && unit == old.unit && !changedReference) {
      return null;
    }
    if (value.trim().isEmpty || unit.trim().isEmpty) {
      throw const FormatException('markerFieldsRequired');
    }
    return {
      'op': 'update',
      'marker_code': code,
      'value_raw': value,
      'unit_raw': unit,
      if (changedReference) 'reference': reference,
    };
  }

  String summaryWith(String Function(String) label) {
    final old = MarkerDraft(original, panel, flagged);
    return '$name: ${old.value} ${old.unit} → $value $unit'
        '${[low, high, referenceUnit, referenceText].join() != [old.low, old.high, old.referenceUnit, old.referenceText].join() ? '\n${label('referenceOriginal')}: ${old.low} – ${old.high} ${old.referenceUnit} ${old.referenceText}\n${label('referenceRevised')}: $low – $high $referenceUnit $referenceText' : ''}';
  }

  String get summary => summaryWith((key) => key);
}

class ExtractionDraft {
  ExtractionDraft(Json data) : original = jsonDecode(jsonEncode(data)) as Json {
    final flags = (original['flags'] as List? ?? []).whereType<Map>();
    for (final p in original['panels'] as List? ?? []) {
      for (final m in (p as Map)['markers'] as List? ?? []) {
        final marker = Map<String, dynamic>.from(m as Map);
        final code = marker['marker_code'] as String;
        if (markers.any((m) => m.code == code)) {
          throw const ApiFailure(502, 'AMBIGUOUS_MARKER_CODES');
        }
        markers.add(
          MarkerDraft(
            marker,
            p['panel_name_raw'] as String? ?? '',
            flags.any(
              (f) => f['code'] == 'low_confidence' && f['marker_code'] == code,
            ),
          ),
        );
      }
    }
    collectionDate = document['collection_date'] as String? ?? '';
    reportDate = document['report_date'] as String? ?? '';
  }
  final Json original;
  final markers = <MarkerDraft>[];
  late String collectionDate, reportDate;
  Map get document => original['document'] as Map? ?? {};
  Json body(String action, bool identity) {
    if (action == 'discard') {
      return {'action': action, 'extraction_id': original['extraction_id']};
    }
    final edits = <String, dynamic>{'identity_confirmed': identity};
    for (final entry in {
      'collection_date': collectionDate,
      'report_date': reportDate,
    }.entries) {
      final old = document[entry.key] as String? ?? '';
      if (entry.value != old) {
        final parsed = DateTime.tryParse(entry.value);
        if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(entry.value) ||
            parsed == null ||
            parsed.toIso8601String().substring(0, 10) != entry.value) {
          throw const FormatException('reviewDatesInvalid');
        }
        edits[entry.key] = entry.value;
      }
    }
    return {
      'action': action,
      'extraction_id': original['extraction_id'],
      'document_edits': edits,
      'acknowledged_marker_codes': markers.map((m) => m.code).toList(),
      'marker_edits': [
        for (final m in markers)
          if (m.edit() case final Json edit) edit,
      ],
    };
  }

  String get summary => summaryWith((key) => key);
  String summaryWith(String Function(String) label) => [
    for (final m in markers) m.summaryWith(label),
    if (collectionDate != (document['collection_date'] ?? ''))
      "${label('collectionDateLabel')}: ${document['collection_date'] ?? label('withoutDate')} → $collectionDate",
    if (reportDate != (document['report_date'] ?? ''))
      "${label('reportDateLabel')}: ${document['report_date'] ?? label('withoutDate')} → $reportDate",
  ].join('\n');
}
