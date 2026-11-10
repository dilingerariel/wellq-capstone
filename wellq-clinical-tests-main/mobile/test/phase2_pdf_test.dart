import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pdfrx/pdfrx.dart';
import 'package:wellq_mobile/l10n/localized_copy.dart';
import 'package:wellq_mobile/presentation/synthetic_pdf_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() => pdfrxInitialize());
  test(
    'PDFium opens the allowed PDF, renders a complete page and disposes resources',
    () async {
      final data = verifiedSyntheticBytes(
        await File('assets/synthetic.pdf').readAsBytes(),
      );
      final document = await PdfDocument.openData(
        data,
        sourceName: 'synthetic-test.pdf',
      );
      try {
        expect(document.pages, hasLength(1));
        final page = document.pages.single;
        final image = await page.render(
          fullWidth: page.width,
          fullHeight: page.height,
        );
        expect(image, isNotNull);
        expect(image!.width, greaterThan(500));
        expect(image.height, greaterThan(700));
        image.dispose();
      } finally {
        await document.dispose();
      }
    },
  );
  testWidgets(
    'viewer renders the actual fixture, zooms and returns to the unchanged form',
    (t) async {
      final bytes = await t.runAsync(
        () => File('assets/synthetic.pdf').readAsBytes(),
      );
      await t.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: Column(
                children: [
                  const TextField(
                    decoration: InputDecoration(labelText: 'Draft title'),
                  ),
                  TextButton(
                    onPressed: () => Navigator.push(
                      context,
                      MaterialPageRoute<void>(
                        builder: (_) =>
                            SyntheticPdfScreen(load: () async => bytes!),
                      ),
                    ),
                    child: const Text('Open PDF'),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
      await t.enterText(find.byType(TextField), 'SYNTHETIC DRAFT');
      await t.tap(find.text('Open PDF'));
      await t.pump();
      for (var i = 0; i < 80 && find.text('1 página').evaluate().isEmpty; i++) {
        await t.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 50)),
        );
        await t.pump(const Duration(milliseconds: 50));
      }
      expect(find.text('1 página'), findsOneWidget);
      final viewer = t.widget<PdfViewer>(find.byType(PdfViewer));
      final zoom = viewer.controller!.currentZoom;
      await t.tap(find.byTooltip('Acercar documento'));
      await t.pump(const Duration(milliseconds: 300));
      expect(viewer.controller!.currentZoom, greaterThan(zoom));
      await t.pageBack();
      await t.pumpAndSettle();
      expect(find.text('SYNTHETIC DRAFT'), findsOneWidget);
      expect(find.byType(PdfViewer), findsNothing);
    },
  );
  testWidgets(
    'PDF controls change language without reloading or changing the document',
    (t) async {
      final bytes = (await t.runAsync(
        () => File('assets/synthetic.pdf').readAsBytes(),
      ))!;
      final original = Uint8List.fromList(bytes);
      final locale = ValueNotifier(const Locale('es'));
      await t.pumpWidget(
        ValueListenableBuilder(
          valueListenable: locale,
          builder: (context, selected, _) => MaterialApp(
            locale: selected,
            supportedLocales: AppLocalizations.supportedLocales,
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            home: SyntheticPdfScreen(load: () async => bytes),
          ),
        ),
      );
      for (var i = 0; i < 80 && find.text('1 página').evaluate().isEmpty; i++) {
        await t.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 50)),
        );
        await t.pump(const Duration(milliseconds: 50));
      }
      expect(find.text('1 página'), findsOneWidget);
      final controller = t
          .widget<PdfViewer>(find.byType(PdfViewer))
          .controller!;
      locale.value = const Locale('en');
      await t.pumpAndSettle();
      expect(find.text('1 page'), findsOneWidget);
      expect(find.text('Synthetic document'), findsOneWidget);
      expect(find.text('Not for clinical use'), findsOneWidget);
      expect(
        t.widget<PdfViewer>(find.byType(PdfViewer)).controller,
        same(controller),
      );
      final zoom = controller.currentZoom;
      await t.tap(find.byTooltip('Zoom in'));
      await t.pump(const Duration(milliseconds: 300));
      expect(controller.currentZoom, greaterThan(zoom));
      final changedZoom = controller.currentZoom;
      locale.value = const Locale('es');
      await t.pumpAndSettle();
      expect(find.text('1 página'), findsOneWidget);
      expect(find.byTooltip('Acercar documento'), findsOneWidget);
      expect(controller.currentZoom, changedZoom);
      expect(bytes, orderedEquals(original));
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox.shrink());
      locale.dispose();
    },
  );
  testWidgets(
    'viewer shows a safe error for missing and damaged input, and Back works',
    (t) async {
      await t.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => TextButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute<void>(
                  builder: (_) => SyntheticPdfScreen(
                    load: () async => Uint8List.fromList([1, 2, 3]),
                  ),
                ),
              ),
              child: const Text('Open synthetic'),
            ),
          ),
        ),
      );
      await t.tap(find.text('Open synthetic'));
      await t.pumpAndSettle();
      expect(
        find.textContaining('No se puede abrir el documento'),
        findsOneWidget,
      );
      await t.pageBack();
      await t.pumpAndSettle();
      expect(find.text('Open synthetic'), findsOneWidget);
      await t.pumpWidget(
        MaterialApp(
          home: SyntheticPdfScreen(
            load: () async =>
                throw const FileSystemException('Missing synthetic test PDF'),
          ),
        ),
      );
      await t.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 30)),
      );
      await t.pumpAndSettle();
      expect(
        find.textContaining('No se puede abrir el documento'),
        findsOneWidget,
      );
    },
  );
}
