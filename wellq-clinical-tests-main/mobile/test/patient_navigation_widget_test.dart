// Small tests of the actual navigation widget, without PDF/SQLite dependencies.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wellq_mobile/l10n/generated/app_localizations.dart';
import 'package:wellq_mobile/presentation/patient_widgets.dart';

void main() {
  WidgetController.hitTestWarningShouldBeFatal = true;
  for (final language in ['es', 'en']) {
    for (final dark in [false, true]) {
      testWidgets('patient navigation $language dark=$dark at 200 percent', (
        t,
      ) async {
        t.view.physicalSize = const Size(320, 800);
        t.view.devicePixelRatio = 1;
        t.platformDispatcher.textScaleFactorTestValue = 2;
        addTearDown(t.view.resetPhysicalSize);
        addTearDown(t.view.resetDevicePixelRatio);
        addTearDown(t.platformDispatcher.clearTextScaleFactorTestValue);
        var selected = 0;
        final semantics = t.ensureSemantics();
        try {
          await t.pumpWidget(
            MaterialApp(
              locale: Locale(language),
              supportedLocales: AppLocalizations.supportedLocales,
              localizationsDelegates: AppLocalizations.localizationsDelegates,
              theme: ThemeData(
                useMaterial3: true,
                brightness: dark ? Brightness.dark : Brightness.light,
              ),
              home: StatefulBuilder(
                builder: (context, update) => Scaffold(
                  body: Text('Selected: $selected'),
                  bottomNavigationBar: PatientNavigation(
                    selected: selected,
                    onSelected: (next) => update(() => selected = next),
                  ),
                ),
              ),
            ),
          );
          await t.pumpAndSettle();
          for (final index in [1, 2, 3, 4, 0]) {
            await t.tap(find.byKey(ValueKey('patient-tab/$index')));
            await t.pumpAndSettle();
            expect(selected, index);
            expect(
              t
                  .widget<PatientNavigation>(find.byType(PatientNavigation))
                  .selected,
              index,
            );
            expect(find.text('Selected: $index'), findsOneWidget);
            expect(t.takeException(), isNull);
          }
          await expectLater(t, meetsGuideline(androidTapTargetGuideline));
          await expectLater(t, meetsGuideline(labeledTapTargetGuideline));
          await t.pumpWidget(const SizedBox.shrink());
        } finally {
          semantics.dispose();
        }
      });
    }
  }
}
