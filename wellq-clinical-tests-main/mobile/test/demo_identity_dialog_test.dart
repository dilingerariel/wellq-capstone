// Requires Flutter Linux/Android runner. Not a native Dart or HTTP test.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wellq_mobile/l10n/localized_copy.dart';
import 'package:wellq_mobile/presentation/patient_dialogs.dart';

void main() {
  for (final language in ['es', 'en']) {
    testWidgets('explicit demo access dialog $language at 200 percent', (
      t,
    ) async {
      t.view.physicalSize = const Size(320, 800);
      t.view.devicePixelRatio = 1;
      t.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      addTearDown(t.platformDispatcher.clearTextScaleFactorTestValue);
      String? entered;
      await t.pumpWidget(
        MaterialApp(
          locale: Locale(language),
          supportedLocales: AppLocalizations.supportedLocales,
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          theme: ThemeData(
            brightness: language == 'en' ? Brightness.dark : Brightness.light,
          ),
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () async {
                  entered = await showDialog<String>(
                    context: context,
                    builder: (_) => const DemoAccessDialog(),
                  );
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );
      await t.tap(find.text('Open'));
      await t.pumpAndSettle();
      final l = lookupAppLocalizations(Locale(language));
      expect(find.text(l.demoAccessHelp), findsOneWidget);
      expect(t.widget<TextField>(find.byType(TextField)).obscureText, true);
      expect(entered, isNull);
      await t.enterText(find.byType(TextField), 'SYNTHETIC-DEMO-ONLY');
      t.testTextInput.hide();
      await t.pumpAndSettle();
      await t.tap(find.text(language == 'es' ? l.confirmAction : l.back));
      await t.pumpAndSettle();
      expect(entered, language == 'es' ? 'SYNTHETIC-DEMO-ONLY' : null);
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox.shrink());
    });
  }
}
