import 'dart:io';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wellq_mobile/application/patient_controller.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/domain/exam_query.dart';
import 'package:wellq_mobile/domain/models.dart';

// Real loopback HTTP, read-only; never starts/stops Docker or touches Android.
void main() {
  test(
    'real FastAPI patient filters, cursor order and mobile reconciliation',
    () async {
      final api = ApiClient();
      final store = LocalStore(NativeDatabase.memory());
      final c = PatientController(
        api,
        LoopbackIdentity(api, enabled: true),
        store,
        Directory.systemTemp,
      );
      try {
        await c.connect();
        expect(c.session, isNotNull);
        expect(c.online, isTrue);
        final first = ExamPage.fromJson(
          await api.json(
            'GET',
            '/api/v1/clinical-tests?limit=1',
            session: c.session,
          ),
        );
        expect(first.items, hasLength(1));
        final e = first.items.single;
        expect(
          first.cursor,
          isNotNull,
          reason:
              'The existing synthetic fixture must contain multiple exams to verify pagination.',
        );
        final second = ExamPage.fromJson(
          await api.json(
            'GET',
            Uri(
              path: '/api/v1/clinical-tests',
              queryParameters: {'limit': '1', 'cursor': first.cursor!},
            ).toString(),
            session: c.session,
          ),
        );
        expect(second.items, hasLength(1));
        expect(second.items.single.id, isNot(e.id));
        expect(
          e.date.compareTo(second.items.single.date),
          greaterThanOrEqualTo(0),
        );
        await c.refresh(
          filtering: ExamFilters(status: e.status, type: e.testType),
        );
        expect(c.message, isNull);
        expect(c.exams, isNotEmpty);
        expect(
          c.exams.every(
            (x) => x.status == e.status && x.testType == e.testType,
          ),
          isTrue,
        );
        await c.reconcile();
        expect(c.message, isNull);
        expect(c.filters.status, e.status);
        expect(c.exams.every((x) => x.status == e.status), isTrue);
        final invalid = api.json(
          'GET',
          '/api/v1/clinical-tests?status=not-a-real-state',
          session: c.session,
        );
        await expectLater(
          invalid,
          throwsA(isA<ApiFailure>().having((x) => x.status, 'status', 422)),
        );
      } finally {
        c.dispose();
        await store.close();
      }
    },
    skip: !const bool.fromEnvironment('WELLQ_LIVE'),
  );
}
