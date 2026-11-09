import 'dart:async';
import 'dart:io';
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:wellq_mobile/application/patient_controller.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/domain/exam_query.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'package:wellq_mobile/presentation/exam_list.dart';
import 'package:wellq_mobile/presentation/exam_screen.dart';
import 'foundation_test.dart' show patient, FixedIdentity, response;
import 'phase2_domain_test.dart' show proposal;

const a = Exam('a', 'SYNTHETIC Alfa sangre', '2026-11-09', 'processing');
const b = Exam('b', 'SYNTHETIC Beta', '2026-11-08', 'ready_for_review');
Json page(List<Exam> items, [String? next]) => {
  'items': items.map((e) => e.toJson()).toList(),
  'next_cursor': next,
};

void main() {
  WidgetController.hitTestWarningShouldBeFatal = true;
  late LocalStore store;
  late Directory root;
  late PatientController c;
  late FixedIdentity identity;
  PatientController controller(
    Future<http.Response> Function(http.Request) handler,
  ) {
    identity = FixedIdentity(patient());
    return PatientController(
      ApiClient(client: MockClient(handler)),
      identity,
      store,
      root,
    )..session = identity.session;
  }

  setUp(() async {
    root = await Directory.systemTemp.createTemp('wellq-phase3-synthetic-');
    store = LocalStore(NativeDatabase.memory());
  });
  tearDown(() async {
    c.dispose();
    await store.close();
  });

  test(
    'query uses only real filter parameters and opaque encoded cursor',
    () async {
      c = controller((_) async => response(page([])));
      final uri = Uri.parse(
        const ExamFilters(
          status: 'processing',
          type: 'blood_test',
        ).path(cursor: '+/=&'),
      );
      expect(uri.queryParameters, {
        'status': 'processing',
        'test_type': 'blood_test',
        'cursor': '+/=&',
      });
      expect(
        () => const ExamFilters(status: 'reviewed').path(),
        throwsA(isA<ApiFailure>()),
      );
      expect(const ExamFilters().path(), '/api/v1/clinical-tests');
    },
  );
  test(
    'local title search and date ordering never mutate or imply unloaded results',
    () {
      c = controller((_) async => response(page([])));
      final loaded = [b, a];
      expect(searchLoadedExams(loaded, 'synthetic SANGRE').single.id, 'a');
      expect(searchLoadedExams(loaded, '').map((e) => e.id), ['a', 'b']);
      expect(
        searchLoadedExams(loaded, '', oldestFirst: true).map((e) => e.id),
        ['b', 'a'],
      );
      expect(searchLoadedExams(loaded, 'absent'), isEmpty);
      expect(loaded, [b, a]);
    },
  );
  test(
    'pagination retains server filters, deduplicates overlapping records and stops at end',
    () async {
      final calls = <Uri>[];
      c = controller((r) async {
        if (r.url.path == '/ready') return response({'status': 'ready'});
        calls.add(r.url);
        return response(
          r.url.queryParameters.containsKey('cursor')
              ? page([a, b])
              : page([a], 'opaque+/='),
        );
      });
      await c.refresh(
        filtering: const ExamFilters(status: 'processing', type: 'blood_test'),
      );
      await c.refresh(more: true);
      expect(c.exams.map((e) => e.id), ['a', 'b']);
      expect(calls.last.queryParameters, {
        'status': 'processing',
        'test_type': 'blood_test',
        'cursor': 'opaque+/=',
      });
      await c.refresh(more: true);
      expect(calls.length, 2);
      expect(c.cursor, isNull);
    },
  );
  test(
    'failed filter retains last applied results, cursor and unfiltered cache',
    () async {
      c = controller(
        (r) async => r.url.path == '/ready'
            ? response({'status': 'ready'})
            : response({
                'detail': {'code': 'UNAVAILABLE'},
              }, 503),
      );
      c.exams = [a];
      c.cursor = 'old';
      c.online = true;
      await store.cache(c.session!.scope, [a]);
      await c.refresh(filtering: const ExamFilters(status: 'failed'));
      expect(c.filters.isEmpty, isTrue);
      expect(c.exams, [a]);
      expect(c.cursor, 'old');
      expect(c.online, isFalse);
      expect((await store.cached(c.session!.scope)).single.id, 'a');
    },
  );
  test(
    'successful filter starts a new cursor and cannot overwrite default cache',
    () async {
      c = controller(
        (r) async => r.url.path == '/ready'
            ? response({'status': 'ready'})
            : response(page([b], 'new')),
      );
      c.exams = [a];
      c.cursor = 'old';
      await store.cache(c.session!.scope, [a]);
      await c.refresh(filtering: const ExamFilters(status: 'ready_for_review'));
      expect(c.exams.single.id, 'b');
      expect(c.cursor, 'new');
      expect(c.filters.status, 'ready_for_review');
      expect((await store.cached(c.session!.scope)).single.id, 'a');
    },
  );
  test(
    'repeated cursor is a failed read and cannot replace the prior list',
    () async {
      c = controller(
        (r) async => r.url.path == '/ready'
            ? response({'status': 'ready'})
            : response(page([b], 'same')),
      );
      c.exams = [a];
      c.cursor = 'same';
      await c.refresh(more: true);
      expect(c.exams, [a]);
      expect(c.cursor, 'same');
      expect(c.online, isFalse);
    },
  );
  test(
    'reconnect refreshes current filtered list without submitting queued work',
    () async {
      final calls = <http.Request>[];
      c = controller((r) async {
        calls.add(r);
        return response(page([b]));
      });
      await c.queue(
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC P3',
        '2026-11-09',
      );
      c.filters = const ExamFilters(status: 'ready_for_review');
      await c.reconcile();
      expect(c.exams.single.id, 'b');
      expect(c.operations.single.attempts, 0);
      expect(calls.every((r) => r.method == 'GET'), isTrue);
      expect(calls.last.url.queryParameters['status'], 'ready_for_review');
    },
  );
  for (final method in ['detail', 'extraction', 'confirm']) {
    test(
      'late $method denial cannot log out a newer patient or tenant',
      () async {
        final pending = Completer<http.Response>();
        c = controller((_) => pending.future);
        final request = switch (method) {
          'detail' => c.detail('old'),
          'extraction' => c.extraction('old'),
          _ => c.confirm('old', {}, 'synthetic-key'),
        };
        final expected = expectLater(
          request,
          throwsA(
            isA<ApiFailure>().having((e) => e.code, 'code', 'SESSION_CHANGED'),
          ),
        );
        await c.logout(preservePending: true);
        final fresh = Session.fromJson({
          'accessToken': 'synthetic-new-test-only',
          'resourceId': 'synthetic-local-patient-new',
          'tenantId': 'synthetic-local-other',
          'role': 'patient',
          'permissions': ['clinical:read'],
          'expiresAt':
              DateTime.now()
                  .add(const Duration(minutes: 10))
                  .millisecondsSinceEpoch ~/
              1000,
        });
        c.session = fresh;
        pending.complete(
          response({
            'detail': {'code': 'FORBIDDEN'},
          }, 403),
        );
        await expected;
        expect(c.session, same(fresh));
        expect(c.authorizationFailure, isNull);
      },
    );
  }
  test(
    'unverified ready and unknown upload status cannot finish a local operation',
    () async {
      var status = 'ready_for_review';
      c = controller(
        (_) async =>
            response({'status': status, 'local_file_can_be_deleted': false}),
      );
      await c.queue(
        await File('assets/synthetic.pdf').readAsBytes(),
        'SYNTHETIC P3',
        '2026-11-09',
      );
      final op = c.operations.single
        ..uploadId = 'synthetic-upload'
        ..phase = 'processing';
      await store.save(op);
      await expectLater(
        c.uploads.reconcile(op, c.session!, c.guard()),
        throwsA(isA<ApiFailure>()),
      );
      expect(op.phase, 'processing');
      expect(op.finished, isFalse);
      expect(op.canDelete, isFalse);
      status = 'unexpected';
      await expectLater(
        c.uploads.reconcile(op, c.session!, c.guard()),
        throwsA(isA<ApiFailure>()),
      );
      expect(
        (await store.pending(c.session!.scope)).single.phase,
        'processing',
      );
    },
  );
  test(
    'processing work exposes read reconciliation instead of another send',
    () {
      c = controller((_) async => response(page([])));
      final op = PendingUpload('id', patient().scope, {}, phase: 'processing');
      expect(op.canResume, isFalse);
      op.phase = 'bytes_pending';
      expect(op.canResume, isTrue);
      op.phase = 'conflict';
      expect(op.canResume, isFalse);
    },
  );
  for (final width in [320.0, 360.0, 390.0, 430.0]) {
    for (final scale in [1.0, 2.0]) {
      testWidgets('list search filters and order reflow at $width / $scale', (
        t,
      ) async {
        c = controller(
          (r) async => r.url.path == '/ready'
              ? response({'status': 'ready'})
              : response(page([b])),
        );
        c.exams = [a, b];
        c.online = true;
        c.cursor = 'more';
        t.view.physicalSize = Size(width, 850);
        t.view.devicePixelRatio = 1;
        addTearDown(t.view.resetPhysicalSize);
        addTearDown(t.view.resetDevicePixelRatio);
        await t.pumpWidget(
          AnimatedBuilder(
            animation: c,
            builder: (context, _) => MaterialApp(
              home: MediaQuery(
                data: MediaQueryData(
                  size: Size(width, 850),
                  textScaler: TextScaler.linear(scale),
                ),
                child: Scaffold(
                  body: ExamList(
                    c: c,
                    card: (e) => ListTile(title: Text(e.title)),
                  ),
                ),
              ),
            ),
          ),
        );
        await t.enterText(
          find.byKey(const ValueKey('exam-search')),
          'no-match',
        );
        await t.pumpAndSettle();
        expect(find.textContaining('0 de 2 documentos'), findsOneWidget);
        expect(find.textContaining('Sin coincidencias'), findsOneWidget);
        await t.tap(find.byTooltip('Limpiar búsqueda'));
        await t.pumpAndSettle();
        expect(find.textContaining('2 de 2 documentos'), findsOneWidget);
        await t.tap(find.text('Filtrar y ordenar'));
        await t.pumpAndSettle();
        expect(
          t.widget<EditableText>(find.byType(EditableText)).focusNode.hasFocus,
          isFalse,
        );
        final status = find.byKey(const ValueKey('exam-status'));
        await t.ensureVisible(status);
        await t.tap(status);
        await t.pumpAndSettle();
        await t.tap(find.text('Procesando documento').last);
        await t.pumpAndSettle();
        expect(c.filters.status, 'processing');
        expect(t.takeException(), isNull);
      });
    }
  }
  testWidgets(
    'failed server filter leaves its controlled selector on the applied value',
    (t) async {
      c = controller(
        (r) async => r.url.path == '/ready'
            ? response({'status': 'ready'})
            : response({
                'detail': {'code': 'UNAVAILABLE'},
              }, 503),
      );
      c.exams = [a];
      c.online = true;
      await t.pumpWidget(
        AnimatedBuilder(
          animation: c,
          builder: (context, _) => MaterialApp(
            home: Scaffold(
              body: ExamList(c: c, card: (e) => Text(e.title)),
            ),
          ),
        ),
      );
      await t.tap(find.text('Filtrar y ordenar'));
      await t.pumpAndSettle();
      final field = find.byKey(const ValueKey('exam-status'));
      await t.ensureVisible(field);
      await t.tap(field);
      await t.pumpAndSettle();
      await t.tap(find.text('Procesando documento').last);
      await t.pumpAndSettle();
      expect(c.filters.isEmpty, isTrue);
      expect(c.exams, [a]);
      expect(t.widget<DropdownButton<String>>(field).value, '');
      expect(c.online, isFalse);
      expect(t.takeException(), isNull);
    },
  );
  testWidgets(
    'rejected detail keeps safe metadata and does not request an extraction',
    (t) async {
      var extractionReads = 0;
      c = controller((r) async {
        if (r.url.path.endsWith('/extraction')) {
          extractionReads++;
          return response(proposal());
        }
        return response({
          ...a.toJson(),
          'status': 'rejected',
          'file': {'name': 'synthetic.pdf', 'size_bytes': 2485},
          'notes': 'SYNTHETIC patient note',
          'review': {
            'status': 'not_reviewed',
            'private_note': 'MUST_NOT_DISPLAY',
          },
        });
      });
      await t.pumpWidget(
        MaterialApp(
          home: ExamScreen(c: c, exam: a),
        ),
      );
      await t.pumpAndSettle();
      expect(find.text('Archivo: synthetic.pdf'), findsOneWidget);
      expect(find.text('Tus notas: SYNTHETIC patient note'), findsOneWidget);
      expect(find.textContaining('MUST_NOT_DISPLAY'), findsNothing);
      expect(find.text('Revisar y confirmar'), findsNothing);
      expect(extractionReads, 0);
    },
  );
  testWidgets('missing exam is distinct from a proposal not yet available', (
    t,
  ) async {
    c = controller(
      (_) async => response({
        'detail': {'code': 'NOT_FOUND'},
      }, 404),
    );
    await t.pumpWidget(
      MaterialApp(
        home: ExamScreen(c: c, exam: a),
      ),
    );
    await t.pumpAndSettle();
    expect(find.textContaining('El examen no está disponible'), findsOneWidget);
    expect(find.textContaining('La extracción aún no'), findsNothing);
  });
}
