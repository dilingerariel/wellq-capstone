import 'dart:io';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:wellq_mobile/application/patient_controller.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/data/uploads.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'foundation_test.dart' show patient, FixedIdentity, response;

class UnavailableIdentity implements IdentityAdapter {
  @override
  Future<Session> connect() async => throw const ApiFailure(0, 'NETWORK');
  @override
  void signOut() {}
}

void main() {
  test(
    'A/B: offline queue survives controller/SQLite restart and reconnect reads only',
    () async {
      final root = await Directory.systemTemp.createTemp(
        'wellq-phase2-offline-',
      );
      final file = File('${root.path}/persistent.sqlite');
      final s = patient();
      var writes = 0;
      var store = LocalStore(NativeDatabase(file));
      var c = PatientController(
        ApiClient(
          client: MockClient(
            (_) async => throw const SocketException('offline'),
          ),
        ),
        FixedIdentity(s),
        store,
        root,
      )..session = s;
      await c.refresh();
      expect(c.online, isFalse);
      await c.queue(
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC OFFLINE',
        '2026-11-08',
      );
      final before = c.operations.single;
      expect(before.phase, 'queued');
      expect(before.uploadId, isNull);
      c.dispose();
      await store.close();
      // Reopen file while the API and identity authority remain unavailable.
      store = LocalStore(NativeDatabase(file));
      c = PatientController(ApiClient(), UnavailableIdentity(), store, root);
      await c.connect();
      expect(c.session, isNull);
      expect(c.operations, isEmpty);
      final disk = (await store.pending(s.scope)).single;
      expect(disk.serialize(), before.serialize());
      expect(await store.pending(patient('other').scope), isEmpty);
      expect(
        await FileVault(root).resolve(disk.file).readAsBytes(),
        await File('assets/synthetic.pdf').readAsBytes(),
      );
      c.dispose();
      c = PatientController(
        ApiClient(
          client: MockClient((r) async {
            if (r.method != 'GET') writes++;
            return response({'items': [], 'next_cursor': null});
          }),
        ),
        FixedIdentity(s),
        store,
        root,
      );
      await c.connect();
      await c.reconcile();
      expect(writes, 0);
      expect(c.operations.single.id, before.id);
      expect(c.operations.single.initiateKey, before.initiateKey);
      expect(c.operations.single.completeKey, before.completeKey);
      expect(c.operations.single.serialize(), isNot(contains(s.token)));
      c.dispose();
      await store.close();
    },
  );
  test(
    'C: successful PUT with lost reply survives restart and reuses immutable keys',
    () async {
      final root = await Directory.systemTemp.createTemp('wellq-phase2-cut-');
      final file = File('${root.path}/queue.sqlite');
      var store = LocalStore(NativeDatabase(file));
      final s = patient();
      var puts = 0, completions = 0, refreshes = 0;
      final api = ApiClient(
        client: MockClient((r) async {
          if (r.url.path.endsWith('/initiate')) {
            return response({
              'upload_id': 'u',
              'clinical_test_id': 'exam',
              'upload': descriptor,
            });
          }
          if (r.url.path.endsWith('/status')) {
            return response({
              'status': 'initiated',
              'local_file_can_be_deleted': false,
            });
          }
          if (r.url.path.endsWith('/refresh-url')) {
            refreshes++;
            return response({'upload': descriptor});
          }
          if (r.url.path.endsWith('/complete')) {
            completions++;
            return response({});
          }
          throw StateError('Unexpected request');
        }),
        storageClient: MockClient((r) async {
          puts++;
          if (puts == 1) {
            throw http.ClientException('Response lost after object stored');
          }
          return http.Response('', 412); // Immutable object may already exist.
        }),
      );
      var repo = UploadRepository(api, store, FileVault(root));
      final op = await repo.queue(
        s,
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC CUT',
        '2026-11-08',
        () {},
      );
      await expectLater(repo.resume(op, s, () {}), throwsA(isA<ApiFailure>()));
      expect(op.phase, 'bytes_pending');
      expect(op.canDelete, isFalse);
      await store.close();
      store = LocalStore(NativeDatabase(file));
      await store.recover();
      final recovered = (await store.pending(s.scope)).single;
      repo = UploadRepository(api, store, FileVault(root));
      await repo.resume(recovered, s, () {});
      expect(recovered.id, op.id);
      expect(recovered.initiateKey, op.initiateKey);
      expect(recovered.completeKey, op.completeKey);
      expect(refreshes, 1);
      expect(puts, 2);
      expect(completions, 1);
      expect(recovered.phase, 'processing');
      expect(recovered.canDelete, isFalse); // 412 is never a confirmed upload.
      api.close();
      await store.close();
    },
  );
  test(
    'D/E: expiration blocks HTTP, preserves pending, and scopes identity switches',
    () async {
      final root = await Directory.systemTemp.createTemp(
        'wellq-phase2-expiry-',
      );
      final store = LocalStore(NativeDatabase.memory());
      final first = patient();
      final identity = FixedIdentity(first);
      var requests = 0;
      final api = ApiClient(
        client: MockClient((r) async {
          requests++;
          if (r.url.path.endsWith('/denied')) return response({}, 401);
          return response({'items': [], 'next_cursor': null});
        }),
      );
      final c = PatientController(api, identity, store, root)..session = first;
      await c.queue(
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC OWNER',
        '2026-11-08',
      );
      final saved = c.operations.single;
      await c.failure(const ApiFailure(401, 'SESSION_EXPIRED'));
      expect(c.connectionLabel, 'Sesión expirada');
      expect(c.session, isNull);
      expect((await store.pending(first.scope)).single.id, saved.id);
      await c.connect();
      expect(c.operations.single.id, saved.id);
      identity.session = patient('two');
      await c.connect();
      expect(c.operations, isEmpty);
      expect(c.exams, isEmpty);
      expect((await store.pending(first.scope)).single.id, saved.id);
      await expectLater(
        c.uploads.resume(saved, identity.session, () {}),
        throwsA(isA<ApiFailure>()),
      );
      final count = requests;
      final expired = Session.fromJson({
        'accessToken': 'synthetic-expired-test',
        'resourceId': first.patient,
        'tenantId': first.tenant,
        'role': 'patient',
        'permissions': ['clinical:read'],
        'expiresAt':
            DateTime.now()
                .add(const Duration(seconds: 1))
                .millisecondsSinceEpoch ~/
            1000,
      });
      await Future<void>.delayed(const Duration(milliseconds: 1100));
      await expectLater(
        api.json('GET', '/never-sent', session: expired),
        throwsA(isA<ApiFailure>().having((e) => e.status, 'status', 401)),
      );
      expect(requests, count);
      c.dispose();
      await store.close();
    },
  );
  test(
    'expiration timer clears private memory but retains outbox for reauthorization',
    () async {
      final root = await Directory.systemTemp.createTemp('wellq-phase2-timer-');
      final store = LocalStore(NativeDatabase.memory());
      final s = patient();
      final identity = FixedIdentity(s);
      var mutations = 0;
      final api = ApiClient(
        client: MockClient((r) async {
          if (r.method != 'GET') mutations++;
          return response({'items': [], 'next_cursor': null});
        }),
      );
      final c = PatientController(api, identity, store, root)..session = s;
      await c.queue(
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC EXPIRY',
        '2026-11-08',
      );
      identity.session = Session.fromJson({
        'accessToken': 'synthetic-short-lived-test',
        'resourceId': s.patient,
        'tenantId': s.tenant,
        'role': 'patient',
        'permissions': s.permissions.toList(),
        'expiresAt':
            DateTime.now()
                .add(const Duration(seconds: 2))
                .millisecondsSinceEpoch ~/
            1000,
      });
      await c.connect();
      await Future<void>.delayed(const Duration(milliseconds: 2100));
      expect(c.session, isNull);
      expect(c.operations, isEmpty);
      expect(c.exams, isEmpty);
      expect(c.connectionLabel, 'Sesión expirada');
      expect(await store.pending(s.scope), hasLength(1));
      identity.session = patient();
      await c.connect();
      expect(c.operations, hasLength(1));
      expect(mutations, 0);
      c.dispose();
      await store.close();
    },
  );
  test(
    'viewer source is owner-scoped, associated with the exam and hash verified',
    () async {
      final root = await Directory.systemTemp.createTemp(
        'wellq-phase2-document-',
      );
      final store = LocalStore(NativeDatabase.memory());
      final c = PatientController(
        ApiClient(),
        FixedIdentity(patient()),
        store,
        root,
      )..session = patient();
      await c.queue(
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC PDF',
        '2026-11-08',
      );
      final op = c.operations.single..examId = 'owned-exam';
      await store.save(op);
      expect(await c.document('owned-exam'), isNotNull);
      expect(await c.document('unrelated'), isNull);
      c.session = patient('other');
      expect(await c.document('owned-exam'), isNull);
      c.session = patient();
      await c.uploads.vault.resolve(op.file).writeAsBytes([
        0,
      ]); // Corrupt only this test's private fixture copy.
      expect(await c.document('owned-exam'), isNull);
      c.dispose();
      await store.close();
    },
  );
}

final descriptor = {
  'signed_url':
      'http://127.0.0.1:8765/object/quarantine/clinical-tests/synthetic',
  'required_headers': {'x-goog-if-generation-match': '0'},
};
