import 'dart:io';
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:wellq_mobile/application/patient_controller.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'package:wellq_mobile/domain/patient_dates.dart';
import 'package:wellq_mobile/presentation/app.dart';
import 'package:wellq_mobile/presentation/patient_widgets.dart';
import 'foundation_test.dart' show patient, FixedIdentity, response;
import 'phase2_domain_test.dart' show proposal;

void main() {
  WidgetController.hitTestWarningShouldBeFatal = true;
  test(
    'date-only values do not shift days and invalid dates stay explicit',
    () {
      expect(clinicalDate('2026-11-08'), '08/11/2026');
      expect(clinicalDate('2026-02-31'), 'dateUnavailable');
      expect(clinicalDate(''), 'dateUnavailable');
    },
  );
  test(
    'confirmation naive UTC and explicit offsets retain the same instant',
    () {
      const local = Duration(hours: -3);
      final expected = '09/11/2026 00:30:08 (UTC-03:00)';
      for (final raw in [
        '2026-11-09T03:30:08.356000',
        '2026-11-09T03:30:08.356Z',
        '2026-11-09T00:30:08.356-03:00',
      ]) {
        expect(confirmationTime(raw, displayOffset: local), expected);
      }
      expect(
        confirmationTime('2026-11-09T01:30:00Z', displayOffset: local),
        '08/11/2026 22:30:00 (UTC-03:00)',
      );
      expect(
        confirmationTime(
          '2026-11-08T23:30:00-04:00',
          displayOffset: Duration.zero,
        ),
        '09/11/2026 03:30:00 (UTC+00:00)',
      );
      expect(
        confirmationTime(
          '2026-11-09T03:30:08Z',
          displayOffset: const Duration(hours: 5, minutes: 30),
        ),
        '09/11/2026 09:00:08 (UTC+05:30)',
      );
      expect(confirmationTime('invalid'), 'timeUnavailable');
      expect(confirmationTime('2026-02-31T00:00:00'), 'timeUnavailable');
    },
  );
  for (final width in [320.0, 360.0, 390.0, 430.0]) {
    for (final scale in [1.0, 1.3, 2.0]) {
      testWidgets(
        'navigation fits $width at text scale $scale with system inset',
        (t) async {
          t.view.physicalSize = Size(width, 740);
          t.view.devicePixelRatio = 1;
          t.view.padding = const FakeViewPadding(bottom: 34);
          t.platformDispatcher.textScaleFactorTestValue = scale;
          addTearDown(t.view.resetPhysicalSize);
          addTearDown(t.view.resetDevicePixelRatio);
          addTearDown(t.view.resetPadding);
          addTearDown(t.platformDispatcher.clearTextScaleFactorTestValue);
          var selected = 0;
          await t.pumpWidget(
            MaterialApp(
              theme: ThemeData(useMaterial3: true),
              home: StatefulBuilder(
                builder: (context, update) => Scaffold(
                  body: Text('Selected $selected'),
                  bottomNavigationBar: PatientNavigation(
                    selected: selected,
                    onSelected: (i) => update(() => selected = i),
                  ),
                ),
              ),
            ),
          );
          final semantics = t.ensureSemantics();
          for (var i = 0; i < 5; i++) {
            final target = find.byKey(ValueKey('patient-tab/$i'));
            expect(t.getRect(target).bottom, lessThanOrEqualTo(706));
            await t.tap(target);
            await t.pumpAndSettle();
            expect(selected, i);
          }
          final labels = find.descendant(
            of: find.byType(PatientNavigation),
            matching: find.byType(Text),
          );
          for (final element in labels.evaluate()) {
            final paragraph = element.renderObject! as RenderParagraph;
            expect(paragraph.didExceedMaxLines, isFalse);
            expect(
              t.widget<Text>(find.byWidget(element.widget)).softWrap,
              isFalse,
            );
          }
          await expectLater(t, meetsGuideline(androidTapTargetGuideline));
          await expectLater(t, meetsGuideline(labeledTapTargetGuideline));
          expect(t.takeException(), isNull);
          semantics.dispose();
        },
      );
    }
    testWidgets('reference and date labels wrap safely at $width and 200%', (
      t,
    ) async {
      t.view.physicalSize = Size(width, 840);
      t.view.devicePixelRatio = 1;
      t.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      addTearDown(t.platformDispatcher.clearTextScaleFactorTestValue);
      addTearDown(t.view.resetViewInsets);
      final db = LocalStore(NativeDatabase.memory());
      final c = PatientController(
        ApiClient(
          client: MockClient(
            (r) async => response(
              r.url.path.endsWith('/extraction')
                  ? proposal()
                  : {'title': 'SYNTHETIC', 'status': 'ready_for_review'},
            ),
          ),
        ),
        FixedIdentity(patient()),
        db,
        Directory.systemTemp,
      )..session = patient();
      await t.pumpWidget(
        MaterialApp(
          home: ExamScreen(
            c: c,
            exam: const Exam('exam', 'SYNTHETIC', '2026-11-09', 'processing'),
          ),
        ),
      );
      await t.pumpAndSettle();
      for (final section in [
        'Referencia del documento',
        'Fechas del documento',
      ]) {
        await t.scrollUntilVisible(
          find.text(section),
          180,
          scrollable: find.byType(Scrollable).first,
        );
        await t.pumpAndSettle();
        await t.ensureVisible(find.text(section));
        await t.tap(find.text(section));
        await t.pumpAndSettle();
        final label = section.startsWith('Referencia')
            ? 'Texto de referencia'
            : 'Fecha de informe';
        final fieldId = section.startsWith('Referencia')
            ? 'reference-text'
            : 'report-date';
        final field = find.byKey(
          ValueKey(
            'review/${section.startsWith('Referencia') ? 'glucose' : 'document'}/$fieldId',
          ),
        );
        await t.scrollUntilVisible(
          field,
          180,
          scrollable: find.byType(Scrollable).first,
        );
        await t.pumpAndSettle();
        final text = find.text(label);
        expect(
          t.renderObject<RenderParagraph>(text).didExceedMaxLines,
          isFalse,
        );
        expect(t.widget<Text>(text).maxLines, isNull);
        await t.enterText(
          field,
          section.startsWith('Referencia')
              ? 'SYNTHETIC reference draft'
              : '2026-11-09',
        );
        t.view.viewInsets = const FakeViewPadding(bottom: 180);
        await t.pumpAndSettle();
        await t.ensureVisible(field);
        await t.pumpAndSettle();
        expect(t.takeException(), isNull);
        t.view.resetViewInsets();
        t.testTextInput.hide();
        await t.pumpAndSettle();
      }
      await t.pumpWidget(const SizedBox.shrink());
      c.dispose();
      await db.close();
    });
  }
  testWidgets(
    'temporary network and 502 preserve authorized draft across tabs and reconnect',
    (t) async {
      final db = LocalStore(NativeDatabase.memory());
      final root = Directory.systemTemp.createTempSync(
        'wellq-phase21-reconnect-',
      );
      var down = true, posts = 0;
      final s = patient();
      final c = PatientController(
        ApiClient(
          client: MockClient((r) async {
            if (r.method != 'GET') posts++;
            return down
                ? response({}, 502)
                : response({'items': [], 'next_cursor': null});
          }),
        ),
        FixedIdentity(s),
        db,
        root,
      )..session = s;
      await t.pumpWidget(WellQApp(controller: c));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('patient-tab/2')));
      await t.pumpAndSettle();
      await t.enterText(
        find.byType(TextField).first,
        'SYNTHETIC PRESERVED DRAFT',
      );
      final generation = c.generation;
      await c.refresh();
      await t.pumpAndSettle();
      expect(c.session, same(s));
      expect(c.generation, generation);
      expect(c.online, isFalse);
      await t.tap(find.byKey(const ValueKey('patient-tab/3')));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('patient-tab/2')));
      await t.pumpAndSettle();
      expect(find.text('SYNTHETIC PRESERVED DRAFT'), findsOneWidget);
      down = false;
      await t.runAsync(c.reconcile);
      await t.pumpAndSettle();
      expect(find.text('SYNTHETIC PRESERVED DRAFT'), findsOneWidget);
      expect(posts, 0);
      await c.failure(const ApiFailure(401, 'EXPIRED'));
      await t.pumpAndSettle();
      expect(find.text('SYNTHETIC PRESERVED DRAFT'), findsNothing);
      expect(find.text('Conectar paciente sintético'), findsOneWidget);
      await t.pumpWidget(const SizedBox.shrink());
      c.dispose();
      await db.close();
    },
  );
  testWidgets(
    'long exam title is limited in cards and fully available in detail',
    (t) async {
      const title =
          'SYNTHETIC MOBILE LIVE b1bcf848-2e93-49a8-87ee-888b71ba659e';
      final db = LocalStore(NativeDatabase.memory());
      final c =
          PatientController(
              ApiClient(
                client: MockClient(
                  (r) async => response(
                    r.url.path.endsWith('/extraction')
                        ? (proposal()..['status'] = 'confirmed')
                        : {'title': title, 'status': 'ready_for_review'},
                  ),
                ),
              ),
              FixedIdentity(patient()),
              db,
              Directory.systemTemp,
            )
            ..session = patient()
            ..exams = [
              const Exam('id', title, '2026-11-09', 'ready_for_review'),
            ];
      await t.pumpWidget(WellQApp(controller: c));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('patient-tab/1')));
      await t.pumpAndSettle();
      await t.scrollUntilVisible(
        find.text(title),
        150,
        scrollable: find.byType(Scrollable).first,
      );
      expect(t.widget<Text>(find.text(title)).maxLines, 2);
      expect(t.widget<Text>(find.text(title)).overflow, TextOverflow.ellipsis);
      await t.tap(find.text(title));
      await t.pumpAndSettle();
      expect(t.widget<Text>(find.text(title)).maxLines, isNull);
      await t.pumpWidget(const SizedBox.shrink());
      c.dispose();
      await db.close();
    },
  );
}
