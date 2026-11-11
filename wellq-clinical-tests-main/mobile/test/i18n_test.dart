import 'dart:convert';
import 'dart:io';
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:wellq_mobile/application/language_controller.dart';
import 'package:wellq_mobile/application/patient_controller.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/language_preference.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/domain/exam_query.dart';
import 'package:wellq_mobile/domain/extraction_draft.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'package:wellq_mobile/domain/patient_dates.dart';
import 'package:wellq_mobile/l10n/localized_copy.dart';
import 'package:wellq_mobile/presentation/app.dart';
import 'foundation_test.dart' show patient, FixedIdentity, response;
import 'phase2_domain_test.dart' show proposal;

class PatientHarness {
  PatientHarness(this.directory) {
    c = PatientController(
      ApiClient(
        client: MockClient((r) async {
          requests++;
          if (r.method == 'PATCH') {
            patches.add(jsonDecode(r.body) as Json);
            return response(proposal()..['status'] = 'confirmed');
          }
          if (r.url.path == '/ready') return response({'status': 'ready'});
          if (r.url.path.endsWith('/extraction')) return response(proposal());
          if (r.url.path == '/api/v1/clinical-tests/id') {
            return response({
              'title': 'SYNTHETIC título Original',
              'status': 'ready_for_review',
              'test_date': '2026-11-09',
              'test_type': 'blood_test',
              'file': {'name': 'SYNTHETIC_original.pdf', 'size_bytes': 1234},
              'notes': 'SYNTHETIC notas Original',
            });
          }
          return response({
            'items': [
              const Exam(
                'id',
                'SYNTHETIC título Original',
                '2026-11-09',
                'ready_for_review',
                testType: 'blood_test',
              ).toJson(),
            ],
            'next_cursor': null,
          });
        }),
      ),
      FixedIdentity(patient()),
      store,
      directory,
    );
  }
  final Directory directory;
  final store = LocalStore(NativeDatabase.memory());
  late final PatientController c;
  int requests = 0;
  final patches = <Json>[];
  void authorize() {
    c.session = patient();
    c.online = true;
    c.exams = [
      const Exam(
        'id',
        'SYNTHETIC título Original',
        '2026-11-09',
        'ready_for_review',
        testType: 'blood_test',
      ),
    ];
  }

  Future<void> dispose() async {
    c.dispose();
    await store.close();
  }
}

Future<void> reveal(WidgetTester t, Finder target, [double delta = 140]) async {
  await t.scrollUntilVisible(
    target,
    delta,
    scrollable: find.byType(Scrollable).first,
  );
  await t.pumpAndSettle();
}

void main() {
  WidgetController.hitTestWarningShouldBeFatal = true;
  late Directory temp;
  late PatientHarness h;
  setUp(() async {
    temp = await Directory.systemTemp.createTemp('wellq-i18n-synthetic-');
    h = PatientHarness(temp);
  });
  tearDown(() async {
    await h.dispose();
  });

  test(
    'preference defaults, invalid fallback and exact non-sensitive persistence',
    () async {
      final file = File('${temp.path}/language.pref');
      final pref = LanguagePreference(file);
      expect(await pref.read(), 'es');
      for (final invalid in [
        '',
        'fr',
        'EN',
        ' es',
        'es\n',
        '../../../secret',
        'not-a-language',
      ]) {
        await file.writeAsString(invalid);
        expect(await pref.read(), 'es');
      }
      final first = LanguageController(preference: pref);
      await first.load();
      await first.select('en');
      expect(await file.readAsString(), 'en');
      expect(await file.length(), 2);
      final restart = LanguageController(preference: LanguagePreference(file));
      await restart.load();
      expect(restart.code, 'en');
      await restart.select('es');
      final secondRestart = LanguageController(preference: pref);
      await secondRestart.load();
      expect(secondRestart.code, 'es');
      first.dispose();
      restart.dispose();
      secondRestart.dispose();
    },
  );

  test(
    'fast consecutive changes persist the final choice without session data',
    () async {
      final file = File('${temp.path}/language.pref');
      final lang = LanguageController(preference: LanguagePreference(file));
      final one = lang.select('en');
      final two = lang.select('es');
      final three = lang.select('en');
      await Future.wait([one, two, three]);
      expect(await file.readAsBytes(), [101, 110]);
      expect(h.c.session, isNull);
      expect(h.requests, 0);
      lang.dispose();
    },
  );

  testWidgets(
    'Spanish default and real selector roundtrip offline without identity',
    (t) async {
      final lang = LanguageController();
      await t.pumpWidget(WellQApp(controller: h.c, language: lang));
      await t.pumpAndSettle();
      expect(find.text('Tu salud, en orden'), findsOneWidget);
      await t.tap(find.text('Ajustes'));
      await t.pumpAndSettle();
      await reveal(t, find.byKey(const ValueKey('language-selector')));
      await t.tap(find.byKey(const ValueKey('language-selector')));
      await t.pumpAndSettle();
      await t.tap(find.text('English').last);
      await t.pumpAndSettle();
      expect(lang.code, 'en');
      await reveal(t, find.text('Your health, organized'), -140);
      expect(find.text('Your health, organized'), findsOneWidget);
      expect(h.c.session, isNull);
      expect(h.c.operations, isEmpty);
      expect(h.requests, 0);
      await reveal(t, find.byKey(const ValueKey('language-selector')));
      await t.tap(find.byKey(const ValueKey('language-selector')));
      await t.pumpAndSettle();
      await t.tap(find.text('Español').last);
      await t.pumpAndSettle();
      expect(lang.code, 'es');
      expect(h.requests, 0);
      await t.pumpWidget(const SizedBox.shrink());
      lang.dispose();
    },
  );

  testWidgets(
    'cold app restart keeps English but never restores clinical authorization',
    (t) async {
      final file = File('${temp.path}/language.pref');
      final first = (await t.runAsync(() async {
        final language = LanguageController(
          preference: LanguagePreference(file),
        );
        await language.select('en');
        return language;
      }))!;
      await t.pumpWidget(WellQApp(controller: h.c, language: first));
      await t.pumpAndSettle();
      expect(find.text('Your health, organized'), findsOneWidget);
      await t.pumpWidget(const SizedBox.shrink());
      first.dispose();
      final restarted = (await t.runAsync(() async {
        final language = LanguageController(
          preference: LanguagePreference(file),
        );
        await language.load();
        return language;
      }))!;
      await t.pumpWidget(WellQApp(controller: h.c, language: restarted));
      await t.pumpAndSettle();
      expect(find.text('Your health, organized'), findsOneWidget);
      expect(find.byKey(const ValueKey('patient-tab/1')), findsNothing);
      expect(h.c.session, isNull);
      expect(h.requests, 0);
      await t.pumpWidget(const SizedBox.shrink());
      restarted.dispose();
    },
  );

  testWidgets(
    'changing language preserves pending identities, hashes and patient isolation',
    (t) async {
      h.authorize();
      final owner = h.c.session!;
      await t.runAsync(() async {
        final pdf = await rootBundle.load('assets/synthetic.pdf');
        await h.c.queue(
          pdf.buffer.asUint8List(),
          'SYNTHETIC título Original',
          '2026-11-09',
        );
      });
      final before = h.c.operations.single.serialize();
      final generation = h.c.generation;
      final lang = LanguageController();
      await t.pumpWidget(WellQApp(controller: h.c, language: lang));
      await t.pumpAndSettle();
      final requests = h.requests;
      await lang.select('en');
      await t.pumpAndSettle();
      expect(h.c.session, same(owner));
      expect(h.c.generation, generation);
      expect(h.c.operations.single.serialize(), before);
      expect(h.requests, requests);
      expect(await h.store.pending(patient('other').scope), isEmpty);
      expect((await h.store.pending(owner.scope)).single.serialize(), before);
      h.c.online = false;
      h.c.message = const ApiFailure(
        503,
        'PRIVATE_INTERNAL_DIAGNOSTIC',
      ).message;
      await lang.select('es');
      await t.pumpAndSettle();
      expect(
        find.text('Servicio no disponible. No se ha confirmado éxito.'),
        findsOneWidget,
      );
      await lang.select('en');
      await t.pumpAndSettle();
      expect(
        find.text('Service unavailable. Success has not been confirmed.'),
        findsOneWidget,
      );
      expect(find.textContaining('PRIVATE_INTERNAL'), findsNothing);
      expect(h.requests, requests);
      await h.c.logout();
      await t.pumpAndSettle();
      expect(lang.code, 'en');
      expect(h.c.session, isNull);
      expect(find.text('Your health, organized'), findsOneWidget);
      expect((await h.store.pending(owner.scope)).single.serialize(), before);
      await t.pumpWidget(const SizedBox.shrink());
      lang.dispose();
    },
  );

  testWidgets(
    'preference write failure is local, visible and grants no identity',
    (t) async {
      final lang = (await t.runAsync(() async {
        final language = LanguageController(
          preference: LanguagePreference(File(temp.path)),
        );
        await language.select('en');
        return language;
      }))!;
      await t.pumpWidget(WellQApp(controller: h.c, language: lang));
      await t.pumpAndSettle();
      await t.tap(find.text('Settings'));
      await t.pumpAndSettle();
      final l = lookupAppLocalizations(const Locale('en'));
      await reveal(t, find.text(l.languageSaveFailed));
      expect(find.text(l.languageSaveFailed), findsOneWidget);
      expect(h.c.session, isNull);
      expect(h.requests, 0);
      expect(await t.runAsync(temp.exists), isTrue);
      await t.pumpWidget(const SizedBox.shrink());
      lang.dispose();
    },
  );

  for (final code in ['es', 'en']) {
    final l = lookupAppLocalizations(Locale(code));
    test('safe $code errors, distinct statuses and immutable filter IDs', () {
      for (final status in [
        0,
        401,
        403,
        404,
        409,
        422,
        428,
        429,
        502,
        503,
        599,
      ]) {
        final msg = l.safeMessage(
          ApiFailure(status, 'PRIVATE_DIAGNOSTIC').message,
        );
        expect(msg, isNot(contains('PRIVATE_DIAGNOSTIC')));
        expect(msg, isNotEmpty);
      }
      expect(l.safeMessage('PRIVATE_DIAGNOSTIC'), l.errorUnknown);
      expect(
        l.safeMessage('statusReady'),
        isNot(l.safeMessage('extractionConfirmed')),
      );
      expect(
        l.safeMessage('uploadVerified'),
        isNot(l.safeMessage('extractionConfirmed')),
      );
      expect(
        const ExamFilters(status: 'processing', type: 'blood_test').path(),
        contains('processing'),
      );
      expect(
        const ExamFilters(status: 'processing', type: 'blood_test').path(),
        contains('blood_test'),
      );
    });
    test(
      'calendar and timezone display in $code does not modify stored values',
      () {
        const raw = '2026-11-09';
        expect(
          clinicalDate(raw, locale: code),
          code == 'es' ? '9 de noviembre de 2026' : 'November 9, 2026',
        );
        final value = confirmationTime(
          '2026-11-09T01:30:00Z',
          displayOffset: const Duration(hours: -3),
          locale: code,
        );
        expect(
          value,
          contains(
            code == 'es' ? '8 de noviembre de 2026' : 'November 8, 2026',
          ),
        );
        expect(value, contains('22:30:00 (UTC-03:00)'));
        expect(raw, '2026-11-09');
        expect(
          l.resultCount(1000, 2000),
          contains(code == 'es' ? '1.000' : '1,000'),
        );
        expect(
          l.resultCount(1000, 2000),
          contains(code == 'es' ? '2.000' : '2,000'),
        );
        for (final formatted in [
          l.currentViewCount(1000),
          l.localOperationsCount(1000),
          l.pagesCount(1000),
        ]) {
          expect(formatted, contains(code == 'es' ? '1.000' : '1,000'));
          expect(formatted, isNot(contains('#')));
        }
        final d = ExtractionDraft(proposal());
        final before = jsonEncode(d.body('confirm', true));
        d.summaryWith(l.safeMessage);
        expect(jsonEncode(d.body('confirm', true)), before);
        expect(d.markers.single.value, '90');
        expect(d.markers.single.unit, 'mg/dL');
      },
    );

    testWidgets('search and server filters use identical IDs in $code', (
      t,
    ) async {
      h.authorize();
      final lang = LanguageController();
      await lang.select(code);
      await t.pumpWidget(WellQApp(controller: h.c, language: lang));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('patient-tab/1')));
      await t.pumpAndSettle();
      await reveal(t, find.byKey(const ValueKey('exam-search')));
      await t.enterText(find.byKey(const ValueKey('exam-search')), 'missing');
      await t.pumpAndSettle();
      await reveal(t, find.text(l.resultCount(0, 1)));
      expect(find.text(l.resultCount(0, 1)), findsOneWidget);
      await reveal(t, find.text(l.noMatches));
      expect(find.text(l.noMatches), findsOneWidget);
      await reveal(t, find.text(l.filterSort), -140);
      await t.tap(find.text(l.filterSort));
      await t.pumpAndSettle();
      await reveal(t, find.byKey(const ValueKey('exam-status')));
      await t.tap(find.byKey(const ValueKey('exam-status')));
      await t.pumpAndSettle();
      await t.tap(find.text(l.statusProcessing).last);
      await t.pumpAndSettle();
      expect(h.c.filters.status, 'processing');
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox.shrink());
      lang.dispose();
    });

    testWidgets(
      'confirmation stays human and sends unchanged raw values in $code',
      (t) async {
        h.authorize();
        final lang = LanguageController();
        await lang.select(code);
        await t.pumpWidget(WellQApp(controller: h.c, language: lang));
        await t.pumpAndSettle();
        await t.tap(find.byKey(const ValueKey('patient-tab/1')));
        await t.pumpAndSettle();
        await reveal(t, find.text('SYNTHETIC título Original'));
        await t.tap(find.text('SYNTHETIC título Original'));
        await t.pumpAndSettle();
        final input = find.byKey(const ValueKey('review/glucose/value'));
        await reveal(t, input);
        await t.enterText(input, '90.00');
        await t.pumpAndSettle();
        final requests = h.requests;
        await lang.select(code == 'es' ? 'en' : 'es');
        await t.pumpAndSettle();
        expect(
          t.widget<TextFormField>(input).controller?.text ??
              t
                  .widget<EditableText>(
                    find.descendant(
                      of: input,
                      matching: find.byType(EditableText),
                    ),
                  )
                  .controller
                  .text,
          '90.00',
        );
        expect(h.requests, requests);
        expect(h.patches, isEmpty);
        await lang.select(code);
        await t.pumpAndSettle();
        for (final text in [
          l.identityAcknowledgement,
          l.valuesAcknowledgement,
        ]) {
          await reveal(t, find.text(text));
          await t.tap(find.text(text));
          await t.pumpAndSettle();
        }
        await reveal(t, find.text(l.reviewConfirm));
        await t.tap(find.text(l.reviewConfirm));
        await t.pumpAndSettle();
        expect(find.text(l.reviewConfirmation), findsOneWidget);
        expect(h.patches, isEmpty);
        expect(find.textContaining('90 mg/dL → 90.00 mg/dL'), findsOneWidget);
        await t.tap(find.text(l.confirmAction));
        await t.pumpAndSettle();
        final expected = ExtractionDraft(proposal());
        expected.markers.single.value = '90.00';
        expect(h.patches.single, expected.body('confirm', true));
        expect(find.text(l.extractionConfirmed), findsOneWidget);
        expect(t.takeException(), isNull);
        await t.pumpWidget(const SizedBox.shrink());
        lang.dispose();
      },
    );
  }

  for (final code in ['es', 'en']) {
    for (final width in [320.0, 360.0, 390.0, 430.0]) {
      for (final scale in [1.0, 1.45, 2.0]) {
        for (final dark in [false, true]) {
          testWidgets('patient i18n reflow $code $width $scale dark=$dark', (
            t,
          ) async {
            t.view.physicalSize = Size(width, 950);
            t.view.devicePixelRatio = 1;
            t.platformDispatcher.textScaleFactorTestValue = scale;
            addTearDown(t.view.resetPhysicalSize);
            addTearDown(t.view.resetDevicePixelRatio);
            addTearDown(t.platformDispatcher.clearTextScaleFactorTestValue);
            final semantics = t.ensureSemantics();
            final lang = LanguageController();
            try {
              h.authorize();
              await lang.select(code);
              await t.pumpWidget(WellQApp(controller: h.c, language: lang));
              await t.pumpAndSettle();
              final l = lookupAppLocalizations(Locale(code));
              expect(
                MediaQuery.textScalerOf(
                  t.element(find.byType(PatientShell)),
                ).scale(10),
                closeTo(10 * scale, .001),
              );
              if (dark) {
                await t.tap(find.byTooltip(l.changeTheme));
                await t.pumpAndSettle();
              }
              for (var tab = 0; tab < 5; tab++) {
                final target = find.byKey(ValueKey('patient-tab/$tab'));
                await t.tap(target);
                await t.pumpAndSettle();
                final labels = [
                  l.home,
                  l.exams,
                  l.upload,
                  l.pending,
                  l.settings,
                ];
                expect(t.getSemantics(target).label, contains(labels[tab]));
                expect(t.takeException(), isNull);
              }
              expect(
                Theme.of(t.element(find.byType(PatientShell))).brightness,
                dark ? Brightness.dark : Brightness.light,
              );
              expect(lang.code, code);
              expect(h.c.session, isNotNull);
              await t.tap(find.byKey(const ValueKey('patient-tab/1')));
              await t.pumpAndSettle();
              await reveal(t, find.text('SYNTHETIC t\u00edtulo Original'));
              await t.tap(find.text('SYNTHETIC t\u00edtulo Original'));
              await t.pumpAndSettle();
              for (final entry in {'value': '90', 'unit': 'mg/dL'}.entries) {
                final field = find.byKey(
                  ValueKey('review/glucose/${entry.key}'),
                );
                await reveal(t, field);
                final editable = find.descendant(
                  of: field,
                  matching: find.byType(EditableText),
                );
                expect(
                  t.widget<EditableText>(editable).controller.text,
                  entry.value,
                );
                expect(
                  MediaQuery.textScalerOf(t.element(field)).scale(10),
                  closeTo(10 * scale, .001),
                );
                expect(t.takeException(), isNull);
              }
              expect(h.patches, isEmpty);
              await t.tap(find.byType(BackButton));
              await t.pumpAndSettle();
              expect(lang.code, code);
              expect(t.takeException(), isNull);
            } finally {
              await t.pumpWidget(const SizedBox.shrink());
              lang.dispose();
              semantics.dispose();
            }
          });
        }
      }
    }
  }
}
