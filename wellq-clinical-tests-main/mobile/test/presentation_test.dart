import 'dart:io';
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:wellq_mobile/application/patient_controller.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'package:wellq_mobile/presentation/app.dart';
import 'foundation_test.dart' show patient, FixedIdentity, response;

void main() {
  WidgetController.hitTestWarningShouldBeFatal = true;
  testWidgets('keyboard inset and offline rebuild preserve the unsent form', (
    t,
  ) async {
    t.view.physicalSize = const Size(390, 844);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    addTearDown(t.view.resetViewInsets);
    final db = LocalStore(NativeDatabase.memory());
    final s = patient();
    final c =
        PatientController(
            ApiClient(client: MockClient((r) async => response({}))),
            FixedIdentity(s),
            db,
            Directory.systemTemp,
          )
          ..session = s
          ..online = true;
    await t.pumpWidget(WellQApp(controller: c));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('patient-tab/2')));
    await t.pumpAndSettle();
    final title = find.byType(TextField).first;
    await t.ensureVisible(title);
    await t.showKeyboard(title);
    await t.enterText(title, 'SYNTHETIC KEYBOARD DRAFT');
    t.view.viewInsets = const FakeViewPadding(bottom: 280);
    c.online = false;
    c.notifyListeners();
    await t.pumpAndSettle();
    expect(find.text('SYNTHETIC KEYBOARD DRAFT'), findsOneWidget);
    expect(t.takeException(), isNull);
    await t.sendKeyEvent(LogicalKeyboardKey.tab);
    await t.pumpAndSettle();
    expect(
      t.widget<EditableText>(find.byType(EditableText).last).focusNode.hasFocus,
      isTrue,
    );
    t.testTextInput.hide();
    t.view.resetViewInsets();
    await t.pumpWidget(const SizedBox.shrink());
    c.dispose();
    await db.close();
  });
  for (final size in [
    const Size(320, 640),
    const Size(360, 740),
    const Size(375, 812),
    const Size(390, 844),
    const Size(430, 932),
    const Size(768, 1024),
    const Size(800, 360),
  ]) {
    for (final dark in [false, true]) {
      testWidgets(
        'patient navigation ${size.width}x${size.height} dark=$dark text=200%',
        (t) async {
          t.view.physicalSize = size;
          t.view.devicePixelRatio = 1;
          t.platformDispatcher.textScaleFactorTestValue = 2;
          t.platformDispatcher.platformBrightnessTestValue = dark
              ? Brightness.dark
              : Brightness.light;
          addTearDown(t.view.resetPhysicalSize);
          addTearDown(t.view.resetDevicePixelRatio);
          addTearDown(t.platformDispatcher.clearTextScaleFactorTestValue);
          addTearDown(t.platformDispatcher.clearPlatformBrightnessTestValue);
          final db = LocalStore(NativeDatabase.memory());
          final s = patient();
          final api = ApiClient(
            client: MockClient(
              (r) async => response({'items': [], 'next_cursor': null}),
            ),
          );
          final c =
              PatientController(api, FixedIdentity(s), db, Directory.systemTemp)
                ..session = s
                ..online = true
                ..exams = [
                  const Exam(
                    'fixture',
                    'SYNTHETIC WIDGET EXAM',
                    '2026-11-08',
                    'processing',
                  ),
                ];
          final semantics = t.ensureSemantics();
          await t.pumpWidget(WellQApp(controller: c));
          await t.pumpAndSettle();
          expect(t.takeException(), isNull);
          if (size.width == 390) {
            await expectLater(t, meetsGuideline(androidTapTargetGuideline));
            await expectLater(t, meetsGuideline(labeledTapTargetGuideline));
            await expectLater(t, meetsGuideline(textContrastGuideline));
          }
          for (final destination in [
            'Exámenes',
            'Cargar',
            'Pendientes',
            'Ajustes',
          ]) {
            final index = [
              'Inicio',
              'Exámenes',
              'Cargar',
              'Pendientes',
              'Ajustes',
            ].indexOf(destination);
            await t.tap(find.byKey(ValueKey('patient-tab/$index')));
            await t.pumpAndSettle();
            expect(t.takeException(), isNull);
            expect(
              find.text(switch (destination) {
                'Exámenes' => 'Mis exámenes',
                'Cargar' => 'Nuevo documento',
                'Pendientes' => 'Operaciones pendientes',
                _ => 'Tu espacio',
              }),
              findsOneWidget,
            );
          }
          await t.pumpWidget(const SizedBox.shrink());
          semantics.dispose();
          c.dispose();
          await db.close();
        },
      );
    }
  }
  testWidgets(
    'patient detail never renders private clinician fields and confirms only after explicit preview',
    (t) async {
      final db = LocalStore(NativeDatabase.memory());
      final s = patient();
      var writes = 0;
      final api = ApiClient(
        client: MockClient((r) async {
          if (r.method == 'PATCH') {
            writes++;
            return response({
              'status': 'confirmed',
              'extraction_id': 'x',
              'panels': [],
            });
          }
          if (r.url.path.endsWith('/extraction')) {
            return response({
              'status': 'awaiting_confirmation',
              'extraction_id': 'x',
              'panels': [
                {
                  'markers': [
                    {
                      'marker_code': 'glucose',
                      'raw_name': 'SYNTHETIC glucose',
                      'value_raw': '90',
                      'unit_raw': 'mg/dL',
                    },
                  ],
                },
              ],
            });
          }
          return response({
            'title': 'SYNTHETIC WIDGET EXAM',
            'test_date': '2026-11-08',
            'status': 'ready_for_review',
            'private_note': 'HIDDEN CLINICAL NOTE',
          });
        }),
      );
      final c = PatientController(
        api,
        FixedIdentity(s),
        db,
        Directory.systemTemp,
      )..session = s;
      await t.pumpWidget(
        MaterialApp(
          home: ExamScreen(
            c: c,
            exam: const Exam(
              'x',
              'SYNTHETIC WIDGET EXAM',
              '2026-11-08',
              'processing',
            ),
          ),
        ),
      );
      await t.pumpAndSettle();
      expect(find.text('HIDDEN CLINICAL NOTE'), findsNothing);
      expect(writes, 0);
      for (final text in [
        'He comprobado que este documento me corresponde.',
        'He cotejado valores, unidades y campos de baja confianza.',
      ]) {
        await t.scrollUntilVisible(
          find.text(text),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await t.tap(find.text(text));
        await t.pumpAndSettle();
      }
      await t.ensureVisible(find.text('Revisar y confirmar'));
      await t.tap(find.text('Revisar y confirmar'));
      await t.pumpAndSettle();
      expect(writes, 0);
      await t.tap(find.text('Confirmar acción'));
      await t.pumpAndSettle();
      expect(writes, 1);
      expect(
        find.textContaining('Estado determinado por FastAPI'),
        findsOneWidget,
      );
      await t.pumpWidget(const SizedBox.shrink());
      c.dispose();
      await db.close();
    },
  );
  testWidgets('logout removes detail navigation and sensitive widgets', (
    t,
  ) async {
    final db = LocalStore(NativeDatabase.memory());
    final s = patient();
    final api = ApiClient(client: MockClient((r) async => response({})));
    final c = PatientController(api, FixedIdentity(s), db, Directory.systemTemp)
      ..session = s
      ..exams = [
        const Exam(
          'private',
          'SYNTHETIC PRIVATE TITLE',
          '2026-11-08',
          'processing',
        ),
      ];
    await t.pumpWidget(WellQApp(controller: c));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('patient-tab/1')));
    await t.pumpAndSettle();
    expect(find.text('SYNTHETIC PRIVATE TITLE'), findsOneWidget);
    await c.logout();
    await t.pumpAndSettle();
    expect(find.text('SYNTHETIC PRIVATE TITLE'), findsNothing);
    expect(find.text('Conectar paciente sintético'), findsOneWidget);
    await t.pumpWidget(const SizedBox.shrink());
    c.dispose();
    await db.close();
  });
}
