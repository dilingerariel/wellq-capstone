import 'dart:io';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uuid/uuid.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/data/uploads.dart';
import 'package:wellq_mobile/domain/models.dart';

// Native Dart HTTP + real loopback/FastAPI/Mongo. Not an Android execution.
void main() {
  test(
    'real patient list, private PDF copy, signed PUT, workers, human confirmation and explicit replay',
    () async {
      final api = ApiClient();
      final root = await Directory.systemTemp.createTemp(
        'wellq-mobile-live-synthetic-',
      );
      final db = LocalStore(
        NativeDatabase(File('${root.path}/synthetic.sqlite')),
      );
      try {
        final s = await LoopbackIdentity(api, enabled: true).connect();
        await api.ready();
        final first = ExamPage.fromJson(
          await api.json('GET', '/api/v1/clinical-tests', session: s),
        );
        expect(first.items, isNotEmpty);
        final repo = UploadRepository(api, db, FileVault(root));
        final date = DateTime.now().toIso8601String().substring(0, 10);
        final op = await repo.queue(
          s,
          await File('assets/synthetic.pdf').readAsBytes(),
          'SYNTHETIC MOBILE LIVE ${const Uuid().v4()}',
          date,
          () {},
        );
        await repo.resume(op, s, () {});
        expect(op.phase, 'processing');
        expect(op.canDelete, isFalse);
        for (var i = 0; i < 90 && !op.finished; i++) {
          await Future<void>.delayed(const Duration(seconds: 1));
          await repo.reconcile(op, s, () {});
        }
        expect(op.phase, 'confirmed');
        expect(op.canDelete, isTrue);
        Json? extraction;
        for (var i = 0; i < 60; i++) {
          try {
            extraction = await api.json(
              'GET',
              '/api/v1/clinical-tests/${op.examId}/extraction',
              session: s,
            );
            if (extraction['status'] == 'awaiting_confirmation') break;
          } on ApiFailure catch (e) {
            if (e.status != 404) rethrow;
          }
          await Future<void>.delayed(const Duration(seconds: 1));
        }
        expect(extraction?['status'], 'awaiting_confirmation');
        final body = {
          'extraction_id': extraction!['extraction_id'],
          'action': 'confirm',
          'document_edits': {'identity_confirmed': true},
        };
        final key = const Uuid().v4();
        final confirmed = await api.json(
          'PATCH',
          '/api/v1/clinical-tests/${op.examId}/extraction',
          session: s,
          body: body,
          key: key,
        );
        expect(confirmed['status'], 'confirmed');
        final replay = await api.json(
          'PATCH',
          '/api/v1/clinical-tests/${op.examId}/extraction',
          session: s,
          body: body,
          key: key,
        );
        expect(replay['extraction_id'], confirmed['extraction_id']);
        final detail = await api.json(
          'GET',
          '/api/v1/clinical-tests/${op.examId}',
          session: s,
        );
        expect(detail['patient_id'], s.patient);
        expect(await FileVault(root).resolve(op.file).exists(), isTrue);
        expect((await db.pending(s.scope)).single.id, op.id);
        await expectLater(
          api.json(
            'GET',
            '/api/v1/patients/synthetic-local-unrelated/clinical-tests',
            session: s,
          ),
          throwsA(isA<ApiFailure>().having((e) => e.status, 'denied', 403)),
        );
      } finally {
        api.close();
        await db.close();
      }
    },
    skip: !const bool.fromEnvironment('WELLQ_LIVE'),
    timeout: const Timeout(Duration(minutes: 4)),
  );
}
