import 'dart:async';
import 'dart:convert';
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

Session patient([String suffix = 'one']) => Session.fromJson({
  'accessToken': 'synthetic-test-only',
  'resourceId': 'synthetic-local-patient-$suffix',
  'tenantId': 'synthetic-local-tenant',
  'role': 'patient',
  'permissions': ['clinical:read', 'clinical:write', 'extractions:confirm'],
  'expiresAt':
      DateTime.now().add(const Duration(minutes: 10)).millisecondsSinceEpoch ~/
      1000,
});

class FixedIdentity implements IdentityAdapter {
  FixedIdentity(this.session);
  Session session;
  @override
  Future<Session> connect() async => session;
  @override
  void signOut() {}
}

http.Response response(Object data, [int status = 200]) => http.Response(
  jsonEncode(data),
  status,
  headers: {'content-type': 'application/json'},
);
void main() {
  late Directory root;
  late LocalStore db;
  setUp(() async {
    root = await Directory.systemTemp.createTemp('wellq-synthetic-test-');
    db = LocalStore(NativeDatabase.memory());
  });
  tearDown(() async {
    await db.close();
  }); // Retain fixture files; never delete selected originals.
  test(
    'Drift survives restart, recovers lease, and isolates tenants/patients',
    () async {
      await db.close();
      final file = File('${root.path}/outbox.sqlite');
      db = LocalStore(NativeDatabase(file));
      final s = patient(), other = patient('two');
      final api = ApiClient();
      final repo = UploadRepository(api, db, FileVault(root));
      final op = await repo.queue(
        s,
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC',
        '2026-11-08',
        () {},
      );
      expect(await db.claim(s.scope, op.id), isTrue);
      expect(await db.claim(s.scope, op.id), isFalse);
      await db.cache(s.scope, [
        const Exam('test', 'SYNTHETIC', '2026-11-08', 'processing'),
      ]);
      await db.close();
      db = LocalStore(NativeDatabase(file));
      await db.recover();
      final saved = (await db.pending(s.scope)).single;
      expect(saved.initiateKey, op.initiateKey);
      expect(saved.initiate, op.initiate);
      expect(saved.completeKey, op.completeKey);
      expect(await db.claim(s.scope, op.id), isTrue);
      expect(await db.pending(other.scope), isEmpty);
      expect(await db.cached(other.scope), isEmpty);
      expect(await FileVault(root).resolve(saved.file).exists(), isTrue);
      expect(saved.serialize(), isNot(contains('synthetic-test-only')));
      expect(saved.serialize(), isNot(contains('signed_url')));
      await db.clearCache(s.scope);
      expect((await db.pending(s.scope)).single.id, op.id);
      expect(await db.cached(s.scope), isEmpty);
      api.close();
    },
  );
  test(
    'only reviewed synthetic PDF can be persisted; path escape rejected',
    () async {
      final api = ApiClient();
      final repo = UploadRepository(api, db, FileVault(root));
      await expectLater(
        repo.queue(
          patient(),
          utf8.encode('%PDF real patient'),
          'SYNTHETIC',
          '2026-11-08',
          () {},
        ),
        throwsA(
          isA<ApiFailure>().having(
            (e) => e.code,
            'code',
            'ONLY_BUNDLED_SYNTHETIC_PDF',
          ),
        ),
      );
      expect(
        () => FileVault(root).resolve('../original.pdf'),
        throwsStateError,
      );
      expect(() => db.check('production/patient'), throwsStateError);
      api.close();
    },
  );
  for (final status in [401, 403, 409, 428, 422, 429, 502, 503]) {
    test(
      'HTTP $status stays explicit and does not echo private errors',
      () async {
        final api = ApiClient(
          client: MockClient(
            (r) async => response({
              'detail': {'code': 'SAFE_CODE', 'private': 'DO NOT ECHO'},
            }, status),
          ),
        );
        await expectLater(
          api.json('GET', '/api/v1/clinical-tests', session: patient()),
          throwsA(
            isA<ApiFailure>()
                .having((e) => e.status, 'status', status)
                .having(
                  (e) => e.toString(),
                  'private',
                  isNot(contains('DO NOT ECHO')),
                ),
          ),
        );
        api.close();
      },
    );
  }
  test(
    'signed PUT uses descriptor headers, never bearer; redirects refused',
    () async {
      var put = 0;
      final api = ApiClient(
        storageClient: MockClient((r) async {
          put++;
          expect(r.headers.containsKey('authorization'), isFalse);
          expect(r.followRedirects, isFalse);
          expect(r.headers['x-goog-if-generation-match'], '0');
          expect(r.bodyBytes, [1, 2, 3]);
          return http.Response('', 200);
        }),
      );
      await api.put(
        {
          'signed_url':
              'http://127.0.0.1:8765/object/quarantine/clinical-tests/test',
          'required_headers': {'x-goog-if-generation-match': '0'},
        },
        [1, 2, 3],
      );
      await expectLater(
        api.put(
          {
            'signed_url': 'https://untrusted.invalid/object',
            'required_headers': {},
          },
          [1],
        ),
        throwsA(isA<ApiFailure>()),
      );
      expect(put, 1);
      api.close();
    },
  );
  test(
    'uncertain initiate reuses immutable identity/key; processing requires server confirmation',
    () async {
      final keys = <String>[], bodies = <String>[];
      var fail = true;
      var complete = 0, puts = 0;
      String status = 'initiated';
      final api = ApiClient(
        client: MockClient((r) async {
          if (r.url.path.endsWith('/initiate')) {
            keys.add(r.headers['Idempotency-Key']!);
            bodies.add(r.body);
            if (fail) {
              fail = false;
              throw http.ClientException('offline');
            }
            return response({
              'upload_id': 'upload',
              'clinical_test_id': 'exam',
              'upload': {
                'signed_url':
                    'http://127.0.0.1:8765/object/quarantine/clinical-tests/test',
                'required_headers': {'x-goog-if-generation-match': '0'},
                'expires_at': '2099-01-01T00:00:00Z',
              },
            });
          }
          if (r.url.path.endsWith('/status')) {
            return response({
              'status': status,
              'upload_id': 'upload',
              'clinical_test_id': 'exam',
              'processing': {
                'malware_scan': 'passed',
                'mime_validation': 'passed',
              },
              'local_file_can_be_deleted': status == 'ready_for_review',
            });
          }
          if (r.url.path.endsWith('/complete')) {
            complete++;
            status = 'processing';
            return response({
              'status': 'processing',
              'upload_id': 'upload',
              'clinical_test_id': 'exam',
            });
          }
          throw StateError('Unexpected route');
        }),
        storageClient: MockClient((r) async {
          puts++;
          return http.Response('', 200);
        }),
      );
      var now = DateTime.now();
      final repo = UploadRepository(api, db, FileVault(root), clock: () => now);
      final s = patient();
      final op = await repo.queue(
        s,
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC',
        '2026-11-08',
        () {},
      );
      await expectLater(repo.resume(op, s, () {}), throwsA(isA<ApiFailure>()));
      now = DateTime.fromMillisecondsSinceEpoch(op.retryAt);
      expect(op.phase, 'queued');
      expect(op.canDelete, isFalse);
      await repo.resume(op, s, () {});
      expect(keys[0], keys[1]);
      expect(bodies[0], bodies[1]);
      expect(puts, 1);
      expect(complete, 1);
      expect(op.phase, 'processing');
      expect(op.canDelete, isFalse);
      await repo.resume(op, s, () {});
      expect(complete, 1);
      expect(puts, 1);
      status = 'ready_for_review';
      await repo.reconcile(op, s, () {});
      expect(op.phase, 'confirmed');
      expect(op.canDelete, isTrue);
      expect(await FileVault(root).resolve(op.file).exists(), isTrue);
      api.close();
    },
  );
  test(
    'same operation has one local sender; stale identity cannot continue writes',
    () async {
      final started = Completer<void>(), release = Completer<void>();
      var posts = 0;
      final api = ApiClient(
        client: MockClient((r) async {
          posts++;
          started.complete();
          await release.future;
          return response({}, 503);
        }),
      );
      final repo = UploadRepository(api, db, FileVault(root));
      final s = patient();
      final op = await repo.queue(
        s,
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC',
        '2026-11-08',
        () {},
      );
      var active = true;
      void check() {
        if (!active) throw const ApiFailure(401, 'SESSION_CHANGED');
      }

      final first = repo.resume(op, s, check);
      final failed = expectLater(first, throwsA(isA<ApiFailure>()));
      await started.future;
      await repo.resume(op, s, check);
      expect(posts, 1);
      active = false;
      release.complete();
      await failed;
      api.close();
    },
  );
  test(
    'logout drops private views and late HTTP response cannot repopulate them',
    () async {
      final gate = Completer<void>();
      final s = patient();
      var delayed = false;
      final api = ApiClient(
        client: MockClient((r) async {
          if (r.url.path == '/ready') return response({});
          if (delayed) await gate.future;
          return response({
            'items': [
              {
                'clinical_test_id': 'x',
                'title': 'SYNTHETIC PRIVATE',
                'test_date': '2026-11-08',
                'status': 'processing',
                'private_clinical_note': 'NEVER CACHE',
              },
            ],
            'next_cursor': null,
          });
        }),
      );
      final c = PatientController(api, FixedIdentity(s), db, root);
      await c.connect();
      expect(c.exams.single.title, 'SYNTHETIC PRIVATE');
      expect(
        (await db.cached(
          s.scope,
        )).single.toJson().containsKey('private_clinical_note'),
        isFalse,
      );
      delayed = true;
      final request = c.refresh();
      await Future<void>.delayed(Duration.zero);
      await c.logout();
      gate.complete();
      await request;
      expect(c.session, isNull);
      expect(c.exams, isEmpty);
      expect(await db.cached(s.scope), isEmpty);
      expect(await db.pending(s.scope), isEmpty);
      c.dispose();
    },
  );
  test('disabled identity adapter never contacts local authority', () async {
    var calls = 0;
    final api = ApiClient(
      client: MockClient((r) async {
        calls++;
        return response({});
      }),
    );
    await expectLater(
      LoopbackIdentity(api, enabled: false).connect(),
      throwsA(isA<ApiFailure>()),
    );
    expect(calls, 0);
    api.close();
  });
  test(
    '401 clears private cache but preserves scoped outbox identity for reconnect',
    () async {
      final s = patient();
      var denied = false;
      final api = ApiClient(
        client: MockClient((r) async {
          if (denied) {
            return response({
              'detail': {'code': 'EXPIRED'},
            }, 401);
          }
          return response({
            'items': [
              {
                'clinical_test_id': 'x',
                'title': 'SYNTHETIC',
                'test_date': '2026-11-08',
                'status': 'processing',
              },
            ],
          });
        }),
      );
      final c = PatientController(api, FixedIdentity(s), db, root);
      await c.connect();
      await c.queue(
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC',
        '2026-11-08',
      );
      final id = c.operations.single.id;
      final key = c.operations.single.initiateKey;
      denied = true;
      await c.refresh();
      expect(c.session, isNull);
      expect(c.exams, isEmpty);
      expect(c.operations, isEmpty);
      expect(await db.cached(s.scope), isEmpty);
      expect((await db.pending(s.scope)).single.id, id);
      denied = false;
      await c.connect();
      expect(c.operations.single.id, id);
      expect(c.operations.single.initiateKey, key);
      c.dispose();
    },
  );
  test(
    'offline retains cached view and operation; reconnect performs no clinical POST',
    () async {
      final s = patient();
      var offline = false;
      var posts = 0;
      final api = ApiClient(
        client: MockClient((r) async {
          if (r.method != 'GET') posts++;
          if (offline) throw http.ClientException('offline');
          return response({
            'items': [
              {
                'clinical_test_id': 'x',
                'title': 'SYNTHETIC',
                'test_date': '2026-11-08',
                'status': 'processing',
              },
            ],
          });
        }),
      );
      final c = PatientController(api, FixedIdentity(s), db, root);
      await c.connect();
      await c.queue(
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC',
        '2026-11-08',
      );
      final id = c.operations.single.id;
      offline = true;
      await c.refresh();
      expect(c.online, isFalse);
      expect(c.exams.single.id, 'x');
      expect(c.operations.single.id, id);
      offline = false;
      await c.reconcile();
      expect(posts, 0);
      expect(c.operations.single.id, id);
      expect(c.operations.single.phase, 'queued');
      c.dispose();
    },
  );
  test(
    'ambiguous complete is reconciled without repeating PUT or completion',
    () async {
      var complete = 0, puts = 0;
      var state = 'initiated';
      final api = ApiClient(
        client: MockClient((r) async {
          if (r.url.path.endsWith('/initiate')) {
            return response({
              'upload_id': 'u',
              'clinical_test_id': 'e',
              'upload': {
                'signed_url':
                    'http://127.0.0.1:8765/object/quarantine/clinical-tests/test',
                'required_headers': {'x-goog-if-generation-match': '0'},
                'expires_at': '2099-01-01T00:00:00Z',
              },
            });
          }
          if (r.url.path.endsWith('/status')) {
            return response({
              'status': state,
              'upload_id': 'u',
              'clinical_test_id': 'e',
              'local_file_can_be_deleted': false,
            });
          }
          if (r.url.path.endsWith('/complete')) {
            complete++;
            state = 'processing';
            throw http.ClientException('response lost after commit');
          }
          throw StateError('Unexpected route');
        }),
        storageClient: MockClient((r) async {
          puts++;
          return http.Response('', 200);
        }),
      );
      final s = patient();
      var now = DateTime.now();
      final repo = UploadRepository(api, db, FileVault(root), clock: () => now);
      final op = await repo.queue(
        s,
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC',
        '2026-11-08',
        () {},
      );
      await expectLater(repo.resume(op, s, () {}), throwsA(isA<ApiFailure>()));
      now = DateTime.fromMillisecondsSinceEpoch(op.retryAt);
      expect(op.phase, 'complete_pending');
      await repo.resume(op, s, () {});
      expect(op.phase, 'processing');
      expect(op.canDelete, isFalse);
      expect(puts, 1);
      expect(complete, 1);
      api.close();
    },
  );
  test(
    '409 blocks repeated writes and keeps immutable request for investigation',
    () async {
      var posts = 0;
      final api = ApiClient(
        client: MockClient((r) async {
          posts++;
          return response({
            'detail': {'code': 'UPLOAD_CONFLICT'},
          }, 409);
        }),
      );
      final s = patient();
      final repo = UploadRepository(api, db, FileVault(root));
      final op = await repo.queue(
        s,
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC',
        '2026-11-08',
        () {},
      );
      final key = op.initiateKey;
      await expectLater(repo.resume(op, s, () {}), throwsA(isA<ApiFailure>()));
      expect(op.phase, 'conflict');
      await expectLater(repo.resume(op, s, () {}), throwsA(isA<ApiFailure>()));
      expect(posts, 1);
      expect((await db.pending(s.scope)).single.initiateKey, key);
      api.close();
    },
  );
}
