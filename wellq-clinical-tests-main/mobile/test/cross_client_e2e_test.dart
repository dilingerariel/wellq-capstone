import 'dart:convert';
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uuid/uuid.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/data/uploads.dart';
import 'package:wellq_mobile/domain/extraction_draft.dart';
import 'package:wellq_mobile/domain/models.dart';

// Opt-in, real clients and real HTTP. The orchestrator owns the fresh stack,
// loopback transport and manifest. Never point this at the user's installation.
void main() {
  test(
    'same synthetic exam crosses Flutter, FastAPI and React',
    () async {
      final path = Platform.environment['WELLQ_CROSS_MANIFEST'];
      final stage = Platform.environment['WELLQ_CROSS_STAGE'];
      expect(path != null && ['upload', 'verify'].contains(stage), isTrue);
      final manifest = File(path!);
      final info = jsonDecode(await manifest.readAsString()) as Json;
      expect(info['synthetic_only'], true);
      expect(info['project'], startsWith('wellq-int-'));
      final root = await Directory.systemTemp.createTemp('wellq-cross-client-');
      final store = LocalStore(
        NativeDatabase(File('${root.path}/queue.sqlite')),
      );
      final api = ApiClient();
      try {
        final session = await LoopbackIdentity(api, enabled: true).connect();
        expect(
          session.tenant == info['tenant'] &&
              session.patient == info['patient'],
          isTrue,
        );
        if (stage == 'upload') {
          expect(info.containsKey('clinical_test_id'), isFalse);
          final repo = UploadRepository(api, store, FileVault(root));
          final op = await repo.queue(
            session,
            await File('assets/synthetic.pdf').readAsBytes(),
            'SYNTHETIC CROSS CLIENT ${info['run']}',
            DateTime.now().toIso8601String().substring(0, 10),
            () {},
          );
          expect(op.attempts, 0);
          await repo.resume(op, session, () {});
          for (var i = 0; i < 90 && !op.finished; i++) {
            await Future<void>.delayed(const Duration(seconds: 1));
            await repo.reconcile(op, session, () {});
          }
          expect(op.phase, 'confirmed');
          Json? proposal;
          for (var i = 0; i < 60; i++) {
            try {
              final value = await api.json(
                'GET',
                '/api/v1/clinical-tests/${op.examId}/extraction',
                session: session,
              );
              if (value['status'] == 'awaiting_confirmation') {
                proposal = value;
                break;
              }
            } on ApiFailure catch (error) {
              if (error.status != 404 &&
                  !(error.status == 409 &&
                      error.code == 'EXTRACTION_NOT_READY')) {
                rethrow;
              }
            }
            await Future<void>.delayed(const Duration(seconds: 1));
          }
          expect(proposal, isNotNull);
          final body = ExtractionDraft(proposal!).body('confirm', true);
          final key = const Uuid().v4();
          final confirmed = await api.json(
            'PATCH',
            '/api/v1/clinical-tests/${op.examId}/extraction',
            session: session,
            body: body,
            key: key,
          );
          expect(confirmed['status'], 'confirmed');
          final replay = await api.json(
            'PATCH',
            '/api/v1/clinical-tests/${op.examId}/extraction',
            session: session,
            body: body,
            key: key,
          );
          expect(replay['extraction_id'], confirmed['extraction_id']);
          final doc = await api.json(
            'GET',
            '/api/v1/clinical-tests/${op.examId}',
            session: session,
          );
          expect(
            doc['patient_id'] == session.patient &&
                doc['clinical_test_id'] == op.examId,
            isTrue,
          );
          info.addAll({
            'clinical_test_id': op.examId,
            'upload_id': op.uploadId,
            'client_upload_id': op.id,
            'extraction_id': confirmed['extraction_id'],
            'clinical_version': doc['clinical_version'],
            'patient_confirmed': true,
            'title': op.title,
            'attempts': op.attempts,
          });
          // Synthetic identifiers only. No JWT, URLs, notes or credentials.
          await manifest.writeAsString(jsonEncode(info), flush: true);
        } else {
          expect(info['react_validated'], true);
          final id = info['clinical_test_id'] as String;
          final doc = await api.json(
            'GET',
            '/api/v1/clinical-tests/$id',
            session: session,
          );
          final ext = await api.json(
            'GET',
            '/api/v1/clinical-tests/$id/extraction',
            session: session,
          );
          expect(doc['clinical_test_id'], id);
          expect(doc['patient_id'] == session.patient, isTrue);
          expect((doc['review'] as Map)['status'], 'reviewed');
          expect(ext['extraction_id'], info['extraction_id']);
          expect(ext['status'], 'clinically_validated');
          final view = jsonEncode([doc, ext]);
          expect(view.contains('SYNTHETIC CROSS PRIVATE'), isFalse);
          info['patient_observed_final'] = true;
          await manifest.writeAsString(jsonEncode(info), flush: true);
        }
      } finally {
        api.close();
        await store.close();
        // Keep only this run's synthetic files until its owner reviews cleanup.
      }
    },
    skip: !const bool.fromEnvironment('WELLQ_CROSS_E2E'),
    timeout: const Timeout(Duration(minutes: 5)),
  );
}
