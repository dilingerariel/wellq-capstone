// Optional widget renderer. These images are NOT Android or real-HTTP evidence.
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
import '../test/foundation_test.dart' show patient, FixedIdentity, response;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
    final font = File(r'C:\Windows\Fonts\segoeui.ttf');
    if (await font.exists()) {
      final loader = FontLoader('Roboto')
        ..addFont(Future.value(ByteData.sublistView(await font.readAsBytes())));
      await loader.load();
    }
  });
  testWidgets('export synthetic widget previews', (t) async {
    t.view.physicalSize = const Size(390, 844);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
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
          ..online = true
          ..exams = [
            const Exam(
              'fixture',
              'SYNTHETIC MOBILE SAMPLE',
              '2026-11-08',
              'ready_for_review',
            ),
          ];
    await t.pumpWidget(WellQApp(controller: c));
    await t.pumpAndSettle();
    await expectLater(
      find.byType(WellQApp),
      matchesGoldenFile('../test_artifacts/widget-light.png'),
    );
    await t.tap(find.byKey(const ValueKey('patient-tab/1')));
    await t.pumpAndSettle();
    await t.tap(find.byTooltip('Cambiar tema'));
    await t.pumpAndSettle();
    await expectLater(
      find.byType(WellQApp),
      matchesGoldenFile('../test_artifacts/widget-dark.png'),
    );
    await t.pumpWidget(const SizedBox.shrink());
    c.dispose();
    await db.close();
  });
}
