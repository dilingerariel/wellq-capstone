// Pure Dart contract checks, independent of the native Flutter widget runner.
// Does not replace Flutter tests, controller tests or Android verification.
import 'dart:convert';
import 'dart:io';
import 'package:wellq_mobile/domain/exam_query.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'package:wellq_mobile/domain/extraction_draft.dart';

void main() {
  var passed = 0;
  void check(bool ok, String name) {
    if (!ok) {
      throw StateError('Domain contract failed: $name');
    }
    passed++;
  }

  final contract =
      jsonDecode(File('contracts.patient.json').readAsStringSync()) as Json;
  final operation = contract['paths']['/api/v1/clinical-tests']['get'] as Json;
  final params = (operation['parameters'] as List)
      .map((e) => e['name'])
      .toSet();
  check(
    params.containsAll(['status', 'test_type', 'cursor']),
    'existing patient query contract',
  );
  final schemas = contract['schemas'] as Json;
  check(
    ExamFilters.statuses.every(
      (s) => (schemas['UploadStatus']['enum'] as List).contains(s),
    ),
    'upload filter enum',
  );
  check(
    ExamFilters.types.every(
      (s) => (schemas['TestType']['enum'] as List).contains(s),
    ),
    'type filter enum',
  );
  check(
    const ExamFilters().path() == '/api/v1/clinical-tests',
    'unfiltered route',
  );
  final query = Uri.parse(
    const ExamFilters(
      status: 'processing',
      type: 'blood_test',
    ).path(cursor: '+/=&'),
  ).queryParameters;
  check(
    query['cursor'] == '+/=&' &&
        query['status'] == 'processing' &&
        query['test_type'] == 'blood_test',
    'opaque cursor and filters',
  );
  var denied = false;
  try {
    const ExamFilters(status: 'reviewed').path();
  } on ApiFailure {
    denied = true;
  }
  check(denied, 'professional state cannot be used as upload filter');
  const recent = Exam(
    'one',
    'SYNTHETIC Alfa sangre',
    '2026-11-09',
    'processing',
  );
  const old = Exam('two', 'SYNTHETIC Beta', '2026-11-08', 'ready_for_review');
  final loaded = [old, recent];
  check(
    searchLoadedExams(loaded, '  synthetic SANGRE ').single.id == 'one',
    'loaded title search',
  );
  check(
    searchLoadedExams(loaded, 'unloaded document').isEmpty,
    'no invented matches',
  );
  check(searchLoadedExams(loaded, '').first.id == 'one', 'newest first');
  check(
    searchLoadedExams(loaded, '', oldestFirst: true).first.id == 'two',
    'oldest loaded first',
  );
  check(loaded.first.id == 'two', 'source list not mutated');
  final op = PendingUpload(
    'synthetic-operation',
    'synthetic-local-test/synthetic-local-patient-test',
    {'title': 'SYNTHETIC fixture'},
    phase: 'processing',
  );
  check(!op.canResume && !op.finished, 'processing requires reads');
  op.phase = 'conflict';
  check(!op.canResume, 'conflict cannot resend');
  op.phase = 'queued';
  check(op.canResume, 'explicit queued send allowed');
  check(
    PendingUpload.deserialize(op.serialize()).serialize() == op.serialize(),
    'existing Drift JSON roundtrip',
  );
  for (final entry in {
    'initiated': 'bytes_pending',
    'object_uploaded': 'object_uploaded',
    'processing': 'processing',
    'rejected': 'rejected',
    'failed': 'failed',
    'ready_for_review': 'confirmed',
  }.entries) {
    check(
      verifiedUploadPhase({
            'status': entry.key,
            'local_file_can_be_deleted': true,
          }) ==
          entry.value,
      'actual upload status ${entry.key}',
    );
  }
  for (final status in ['confirmed', 'unrecognized', 'ready_for_review']) {
    var rejected = false;
    try {
      verifiedUploadPhase({
        'status': status,
        'local_file_can_be_deleted': status != 'ready_for_review',
      });
    } on ApiFailure {
      rejected = true;
    }
    check(rejected, 'incoherent upload response $status rejected');
  }
  final draft = ExtractionDraft({
    'extraction_id': 'synthetic-proposal',
    'status': 'awaiting_confirmation',
    'document': {},
    'panels': [],
  });
  check(
    draft.body('confirm', false)['document_edits']['identity_confirmed'] ==
        false,
    'body cannot invent human identity acknowledgment',
  );
  stdout.writeln(
    '$passed pure Dart domain checks passed; widget/controller/Android suites are separate.',
  );
}
