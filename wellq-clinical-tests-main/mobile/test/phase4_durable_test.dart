import 'dart:async';
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

import 'foundation_test.dart' show FixedIdentity, patient, response;

const signed = {
  'signed_url': 'http://127.0.0.1:8765/object/quarantine/clinical-tests/phase4',
  'expires_at': '2099-01-01T00:00:00Z',
  'required_headers': {'x-goog-if-generation-match': '0'},
};
const remote = {'upload_id': 'u4', 'clinical_test_id': 'e4'};
void active() {}

class InterruptedVault extends FileVault {
  InterruptedVault(super.root, {required this.complete});
  final bool complete;

  @override
  Future<void> stage(PendingUpload op, List<int> bytes) async {
    await super.stage(op, complete ? bytes : bytes.take(9).toList());
    throw const FileSystemException('Simulated interrupted write');
  }
}

class FullVault extends FileVault {
  FullVault(super.root);

  @override
  Future<void> stage(PendingUpload op, List<int> bytes) async {
    throw const FileSystemException('No space left', '', OSError('ENOSPC', 28));
  }
}

void main() {
  late Directory root;
  late LocalStore store;
  late List<int> pdf;
  late Session owner;
  late ApiClient api;
  late DateTime now;

  setUp(() async {
    root = await Directory.systemTemp.createTemp('wellq-phase4-');
    store = LocalStore(NativeDatabase(File('${root.path}/queue.sqlite')));
    pdf = await File('assets/synthetic.pdf').readAsBytes();
    owner = patient();
    now = DateTime.now();
    api = ApiClient(client: MockClient((_) async => fail('Unexpected HTTP')));
  });
  tearDown(() async {
    api.close();
    await store.close();
    // Only the fresh test-owned directory created above.
    await root.delete(recursive: true);
  });

  UploadRepository repo([FileVault? vault]) => UploadRepository(
    api,
    store,
    vault ?? FileVault(root),
    clock: () => now,
    jitter: (max) => max - 1,
  );
  Future<PendingUpload> queue(UploadRepository repository) =>
      repository.queue(owner, pdf, 'SYNTHETIC PHASE 4', '2026-11-08', active);

  test(
    'v1 migration preserves the serialized rows, IDs, states, attempts and PDF bytes',
    () async {
      final original = await queue(repo());
      final saved = original.serialize();
      final other = await repo().queue(
        patient('other'),
        pdf,
        'OTHER SYNTHETIC',
        '2026-11-08',
        active,
      );
      other.phase = 'confirmed';
      other.attempts = 2;
      other.canDelete = true;
      await store.close();
      final path = File('${root.path}/legacy.sqlite');
      store = LocalStore(
        NativeDatabase(
          path,
          setup: (db) {
            db.execute(
              'CREATE TABLE operations (id TEXT PRIMARY KEY, scope TEXT NOT NULL, data TEXT NOT NULL, running INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL)',
            );
            db.execute(
              'CREATE INDEX operations_scope ON operations(scope, created_at)',
            );
            db.execute(
              'CREATE TABLE exam_cache (scope TEXT PRIMARY KEY, data TEXT NOT NULL)',
            );
            db.execute('PRAGMA user_version=1');
            for (final item in [original, other]) {
              db.execute('INSERT INTO operations VALUES (?,?,?,?,?)', [
                item.id,
                item.scope,
                item.serialize(),
                1,
                7,
              ]);
            }
          },
        ),
      );
      final restored = (await store.pending(owner.scope)).single;
      expect(restored.serialize(), saved);
      expect(restored.attempts, 0);
      expect(
        (await store.pending(other.scope)).single.serialize(),
        other.serialize(),
      );
      expect(await FileVault(root).resolve(original.file).readAsBytes(), pdf);
      expect(
        (await store.customSelect('PRAGMA user_version').getSingle()).read<int>(
          'user_version',
        ),
        2,
      );
      expect(await store.claim(owner.scope, restored.id), isFalse);
      await store.recover();
      expect(await store.claim(owner.scope, restored.id, lease: 'new'), isTrue);
      await store.release(owner.scope, restored.id, lease: 'old');
      expect(
        await store.claim(owner.scope, restored.id, lease: 'different'),
        isFalse,
      );
      expect((await store.pending(owner.scope)).single.serialize(), saved);
    },
  );

  for (final complete in [true, false]) {
    test(
      'restart recovers only verified staging (complete=$complete)',
      () async {
        final vault = InterruptedVault(root, complete: complete);
        final saved = await queue(repo(vault));
        final staged = vault.staged(saved);
        expect(await staged.exists(), isTrue);
        await store.close();
        store = LocalStore(NativeDatabase(File('${root.path}/queue.sqlite')));
        await store.recover();
        expect(await repo().recoverFiles(owner, active), 0);
        final restored = (await store.pending(owner.scope)).single;
        expect(restored.id, saved.id);
        expect(restored.initiate, saved.initiate);
        expect(restored.initiateKey, saved.initiateKey);
        expect(restored.completeKey, saved.completeKey);
        expect(restored.phase, 'queued');
        expect(restored.attempts, 0);
        expect(restored.fileIssue, complete ? null : 'incomplete');
        expect(await staged.exists(), !complete);
        expect(await vault.resolve(saved.file).exists(), complete);
        if (complete) {
          expect(await vault.resolve(saved.file).readAsBytes(), pdf);
        }
      },
    );
  }

  test('ENOSPC retains the row and never initiates an upload', () async {
    final upload = await queue(repo(FullVault(root)));
    expect(upload.fileIssue, 'unreadable');
    expect(upload.attempts, 0);
    expect(await repo().recoverFiles(owner, active), 0);
    final restored = (await store.pending(owner.scope)).single;
    expect(restored.fileIssue, 'missing');
    await repo().resume(restored, owner, active);
    expect(restored.attempts, 0);
    expect(restored.id, upload.id);
  });

  test(
    'orphan and corrupt file remain in place, without affecting another scope',
    () async {
      final repository = repo();
      final upload = await queue(repository);
      final other = await repository.queue(
        patient('other'),
        pdf,
        'OTHER SYNTHETIC',
        '2026-11-08',
        active,
      );
      final orphan = File(
        '${root.path}/uploads/00000000-0000-0000-0000-000000000000.pdf.part',
      );
      await orphan.writeAsBytes([1, 2]);
      final file = repository.vault.resolve(upload.file);
      await file.writeAsBytes([3]);
      expect(await repository.recoverFiles(owner, active), 1);
      final current = (await store.pending(owner.scope)).single;
      expect(current.fileIssue, 'corrupt');
      expect(current.canResume, isFalse);
      expect(await orphan.readAsBytes(), [1, 2]);
      expect(await file.readAsBytes(), [3]);
      expect(
        (await store.pending(other.scope)).single.serialize(),
        other.serialize(),
      );
    },
  );

  for (final cut in ['initiate', 'renew', 'put', 'complete']) {
    test('lost response after $cut recovers the same logical upload', () async {
      var completed = false, objectStored = false, lost = false;
      final keys = <String, Set<String>>{};
      final initiated = <String>{};
      var objectCreates = 0, completes = 0;
      void interrupt(String stage) {
        if (!lost && cut == stage) {
          lost = true;
          throw http.ClientException('Synthetic lost reply');
        }
      }

      api.close();
      api = ApiClient(
        client: MockClient((r) async {
          final route = r.url.pathSegments.last;
          if (r.method == 'POST') {
            keys
                .putIfAbsent(route, () => {})
                .add(r.headers['Idempotency-Key']!);
          }
          switch (route) {
            case 'initiate':
              initiated.add(r.body);
              interrupt('initiate');
              return response({
                ...remote,
                'upload': cut == 'renew'
                    ? {...signed, 'expires_at': '2000-01-01T00:00:00Z'}
                    : signed,
              });
            case 'status':
              return response({
                ...remote,
                'status': completed ? 'processing' : 'initiated',
              });
            case 'refresh-url':
              interrupt('renew');
              return response({'upload_id': 'u4', 'upload': signed});
            case 'complete':
              expect(objectStored, isTrue);
              if (!completed) completes++;
              completed = true;
              interrupt('complete');
              return response({...remote, 'status': 'processing'});
          }
          fail('Unexpected endpoint');
        }),
        storageClient: MockClient((r) async {
          expect(r.headers['Authorization'], isNull);
          expect(r.headers['x-goog-if-generation-match'], '0');
          if (objectStored) return http.Response('', 412);
          objectCreates++;
          objectStored = true;
          interrupt('put');
          return http.Response('', 200);
        }),
      );
      final original = await queue(repo());
      await expectLater(
        repo().resume(original, owner, active),
        throwsA(isA<ApiFailure>()),
      );
      expect(lost, isTrue);
      expect(original.retryAt, greaterThan(now.millisecondsSinceEpoch));
      if (cut == 'complete') expect(original.phase, 'complete_pending');
      await store.close();
      store = LocalStore(NativeDatabase(File('${root.path}/queue.sqlite')));
      await store.recover();
      await repo().recoverFiles(owner, active);
      final recovered = (await store.pending(owner.scope)).single;
      expect(recovered.id, original.id);
      expect(recovered.initiate, original.initiate);
      expect(recovered.initiateKey, original.initiateKey);
      expect(recovered.completeKey, original.completeKey);
      expect(recovered.attempts, 1, reason: 'No replay at startup');
      now = DateTime.fromMillisecondsSinceEpoch(recovered.retryAt);
      await repo().resume(recovered, owner, active);
      expect(recovered.phase, 'processing');
      expect(recovered.canDelete, isFalse);
      expect(initiated, hasLength(1));
      expect(objectCreates, 1);
      expect(completes, 1);
      expect(keys.values.every((set) => set.length == 1), isTrue);
      expect(recovered.retryAt, 0);
      expect(await FileVault(root).resolve(recovered.file).readAsBytes(), pdf);
    });
  }

  test(
    '429 Retry-After dominates jitter, 503 backs off and conflict is terminal for writes',
    () async {
      var sends = 0;
      api.close();
      api = ApiClient(
        client: MockClient((_) async {
          sends++;
          return switch (sends) {
            1 => http.Response('{}', 429, headers: {'retry-after': '70'}),
            2 => http.Response('{}', 503),
            _ => response({
              'detail': {'code': 'UPLOAD_CONFLICT'},
            }, 409),
          };
        }),
      );
      final repository = repo();
      final op = await queue(repository);
      Future<void> failAttempt() => expectLater(
        repository.resume(op, owner, active),
        throwsA(isA<ApiFailure>()),
      );
      await failAttempt();
      expect(
        op.retryAt,
        now.add(const Duration(seconds: 70)).millisecondsSinceEpoch,
      );
      await failAttempt();
      expect(sends, 1);
      expect(op.attempts, 1);
      now = DateTime.fromMillisecondsSinceEpoch(op.retryAt);
      await failAttempt();
      expect(
        op.retryAt,
        now.add(const Duration(seconds: 5)).millisecondsSinceEpoch,
      );
      now = DateTime.fromMillisecondsSinceEpoch(op.retryAt);
      await failAttempt();
      expect(op.phase, 'conflict');
      await failAttempt();
      expect(sends, 3);
    },
  );

  test(
    'cancel fences a late response; a concurrent attempt cannot start',
    () async {
      final entered = Completer<void>(), lateReply = Completer<http.Response>();
      var calls = 0;
      api.close();
      api = ApiClient(
        client: MockClient((_) async {
          calls++;
          entered.complete();
          return lateReply.future;
        }),
      );
      final repository = repo();
      final op = await queue(repository);
      final cancel = UploadCancellation();
      final attempt = repository.resume(
        op,
        owner,
        active,
        cancellation: cancel,
      );
      final paused = expectLater(
        attempt,
        throwsA(
          isA<ApiFailure>().having((e) => e.code, 'code', 'UPLOAD_PAUSED'),
        ),
      );
      await entered.future;
      await repository.resume(op, owner, active);
      expect(calls, 1);
      cancel.cancel();
      await paused;
      lateReply.complete(response({...remote, 'upload': signed}));
      await Future<void>.delayed(Duration.zero);
      final saved = (await store.pending(owner.scope)).single;
      expect(saved.uploadId, isNull);
      expect(saved.phase, 'queued');
      expect(saved.error, 'UPLOAD_PAUSED');
      expect(saved.attempts, 1);
    },
  );

  test(
    'same patient in another tenant and revoked write grant cannot send',
    () async {
      final repository = repo();
      final op = await queue(repository);
      Session identity(String tenant, List<String> permissions) =>
          Session.fromJson({
            'accessToken': 'synthetic-fixture',
            'role': 'patient',
            'resourceId': owner.patient,
            'tenantId': tenant,
            'permissions': permissions,
            'expiresAt': owner.expires.millisecondsSinceEpoch ~/ 1000,
          });
      for (final candidate in [
        patient('other'),
        identity('synthetic-local-other', ['clinical:read', 'clinical:write']),
        identity(owner.tenant, ['clinical:read']),
      ]) {
        await expectLater(
          repository.resume(op, candidate, active),
          throwsA(isA<ApiFailure>()),
        );
      }
      expect((await store.pending(owner.scope)).single.attempts, 0);
    },
  );

  test(
    'logout retains the private row and file but locks visibility to the owner',
    () async {
      final op = await queue(repo());
      api.close();
      api = ApiClient(
        client: MockClient((r) async {
          expect(r.method, 'GET');
          return response({'items': [], 'next_cursor': null});
        }),
      );
      final identity = FixedIdentity(owner);
      final controller = PatientController(api, identity, store, root);
      await controller.connect();
      expect(controller.operations.single.id, op.id);
      await controller.logout();
      expect(controller.operations, isEmpty);
      expect(controller.session, isNull);
      expect((await store.pending(owner.scope)).single.attempts, 0);
      expect(await FileVault(root).resolve(op.file).readAsBytes(), pdf);
      identity.session = patient('other');
      await controller.connect();
      expect(controller.operations, isEmpty);
      controller.dispose();
    },
  );
}
