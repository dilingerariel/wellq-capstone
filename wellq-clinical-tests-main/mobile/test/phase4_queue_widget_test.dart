import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wellq_mobile/application/language_controller.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'package:wellq_mobile/l10n/localized_copy.dart';
import 'package:wellq_mobile/presentation/app.dart';

import 'i18n_test.dart' show PatientHarness, reveal;

void main() {
  for (final lang in ['es', 'en']) {
    for (final dark in [false, true]) {
      testWidgets(
        'queue $lang dark=$dark at 200 percent retains files and requires explicit action',
        (t) async {
          final dir = Directory.systemTemp.createTempSync(
            'wellq-phase4-queue-ui-',
          );
          final harness = PatientHarness(dir)..authorize();
          addTearDown(harness.dispose);
          final language = LanguageController();
          addTearDown(language.dispose);
          await language.select(lang);
          final l = lookupAppLocalizations(Locale(lang));
          t.view.physicalSize = const Size(320, 950);
          t.view.devicePixelRatio = 1;
          t.platformDispatcher.textScaleFactorTestValue = 2;
          addTearDown(t.view.resetPhysicalSize);
          addTearDown(t.view.resetDevicePixelRatio);
          addTearDown(t.platformDispatcher.clearTextScaleFactorTestValue);
          final c = harness.c;
          c.operations = [
            PendingUpload('missing', c.session!.scope, {
              'title': 'SYNTHETIC MISSING',
              'file_issue': 'missing',
            }),
            PendingUpload('waiting', c.session!.scope, {
              'title': 'SYNTHETIC WAITING',
            }),
            PendingUpload(
              'verified',
              c.session!.scope,
              {'title': 'SYNTHETIC VERIFIED'},
              phase: 'confirmed',
              canDelete: true,
            ),
          ];
          await t.pumpWidget(WellQApp(controller: c, language: language));
          await t.pumpAndSettle();
          if (dark) {
            await t.tap(find.byTooltip(l.changeTheme));
            await t.pumpAndSettle();
          }
          await t.tap(find.byKey(const ValueKey('patient-tab/3')));
          await t.pumpAndSettle();
          await reveal(t, find.text(l.queueMissing));
          expect(find.text(l.queueMissing), findsOneWidget);
          await reveal(t, find.text(l.queueAwaitingAuthorization));
          await reveal(t, find.text(l.sendDocument));
          expect(find.text(l.sendDocument), findsOneWidget);
          await reveal(t, find.text(l.verifiedLocalCopy));
          expect(find.text(l.verifiedLocalCopy), findsOneWidget);
          expect(harness.requests, 0);
          expect(t.takeException(), isNull);
          await t.pumpWidget(const SizedBox.shrink());
        },
      );
    }
  }
}
