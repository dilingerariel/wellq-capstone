import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uuid/uuid.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/data/uploads.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'package:wellq_mobile/domain/extraction_draft.dart';
import 'package:wellq_mobile/application/patient_controller.dart';

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
            if (e.status != 404 &&
                !(e.status == 409 && e.code == 'EXTRACTION_NOT_READY')) {
              rethrow;
            }
          }
          await Future<void>.delayed(const Duration(seconds: 1));
        }
        expect(extraction?['status'], 'awaiting_confirmation');
        final draft = ExtractionDraft(extraction!);
        draft.markers.single.value =
            '90.0'; // Same synthetic value, raw transcription edit.
        draft.reportDate = '2026-11-08';
        final body = draft.body('confirm', true);
        final key = const Uuid().v4();
        final confirmed = await api.json(
          'PATCH',
          '/api/v1/clinical-tests/${op.examId}/extraction',
          session: s,
          body: body,
          key: key,
        );
        expect(confirmed['status'], 'confirmed');
        expect(
          ((confirmed['panels'] as List).single['markers'] as List)
              .single['value_raw'],
          '90.0',
        );
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
  test(
    'real offline queue, SQLite restart, lost PUT reply and explicit recovery',
    () async {
      final root = await Directory.systemTemp.createTemp(
        'wellq-phase2-real-offline-',
      );
      final file = File('${root.path}/queue.sqlite');
      var disk = LocalStore(NativeDatabase(file));
      var wire = InterruptedWire();
      var storage = InterruptedWire()..losePutReply = true;
      var api = ApiClient(client: wire, storageClient: storage);
      var controller = PatientController(
        api,
        LoopbackIdentity(api, enabled: true),
        disk,
        root,
      );
      await controller.connect();
      final owner = controller.session!;
      wire.offline = true;
      await controller.refresh();
      expect(controller.online, isFalse);
      await controller.queue(
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC REAL OFFLINE',
        '2026-11-08',
      );
      final original = controller.operations.single;
      expect(original.uploadId, isNull);
      controller.dispose();
      await disk.close();
      disk = LocalStore(NativeDatabase(file));
      final cold = (await disk.pending(owner.scope)).single;
      expect(cold.serialize(), original.serialize());
      expect(cold.phase, 'queued');
      wire = InterruptedWire();
      storage = InterruptedWire()..losePutReply = true;
      api = ApiClient(client: wire, storageClient: storage);
      controller = PatientController(
        api,
        LoopbackIdentity(api, enabled: true),
        disk,
        root,
      );
      await controller.connect();
      expect(controller.session!.scope, owner.scope);
      await controller.reconcile();
      expect(
        wire.writes,
        0,
      ); // Reads and host identity only; no upload auto-replay.
      await controller.resume(controller.operations.single);
      final interrupted = (await disk.pending(owner.scope)).single;
      expect(interrupted.phase, 'bytes_pending');
      expect(interrupted.canDelete, isFalse);
      expect(storage.puts, 1);
      controller.dispose();
      await disk.close();
      disk = LocalStore(NativeDatabase(file));
      wire = InterruptedWire();
      storage = InterruptedWire();
      api = ApiClient(client: wire, storageClient: storage);
      controller = PatientController(
        api,
        LoopbackIdentity(api, enabled: true),
        disk,
        root,
      );
      try {
        await controller.connect();
        await controller.reconcile();
        expect(wire.writes, 0);
        final op = controller.operations.single;
        expect(op.id, original.id);
        expect(op.initiateKey, original.initiateKey);
        expect(op.completeKey, original.completeKey);
        await controller.resume(op);
        for (var i = 0; i < 90 && !controller.operations.single.finished; i++) {
          await Future<void>.delayed(const Duration(seconds: 1));
          await controller.reconcile();
        }
        final done = controller.operations.single;
        expect(done.phase, 'confirmed');
        expect(done.canDelete, isTrue);
        expect(done.examId, interrupted.examId);
        expect(storage.puts, 1);
        final ext = await controller.extraction(done.examId!);
        expect(
          ext['status'],
          isNot('confirmed'),
        ); // No human confirmation was replayed.
        expect(done.serialize(), isNot(contains(owner.token)));
        expect(done.serialize(), isNot(contains('signed_url')));
      } finally {
        controller.dispose();
        await disk.close();
      }
    },
    skip: !const bool.fromEnvironment('WELLQ_LIVE'),
    timeout: const Timeout(Duration(minutes: 4)),
  );
}

class InterruptedWire extends http.BaseClient {
  final inner = http.Client();
  bool offline = false, losePutReply = false;
  int writes = 0, puts = 0;
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    if (offline) throw const SocketException('Controlled local outage');
    if (request.method != 'GET' && request.url.path.startsWith('/api/')) {
      writes++;
    }
    if (request.method == 'PUT') puts++;
    final result = await inner.send(request);
    if (request.method == 'PUT' && losePutReply) {
      losePutReply = false;
      await result.stream.drain<void>();
      throw http.ClientException('Controlled lost PUT reply');
    }
    return result;
  }

  @override
  void close() {
    inner.close();
    super.close();
  }
}
