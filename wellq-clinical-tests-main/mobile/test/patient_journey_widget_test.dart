// Real widgets/controller/Drift/files, explicit HTTP and OS-picker doubles.
// No bridge, Docker, identity provider, Android device or real patient data.
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:drift/native.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:pdfrx/pdfrx.dart';
import 'package:wellq_mobile/application/language_controller.dart';
import 'package:wellq_mobile/application/patient_controller.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'package:wellq_mobile/l10n/localized_copy.dart';
import 'package:wellq_mobile/presentation/app.dart';
import 'phase2_domain_test.dart' show proposal;

final class PickedFixture extends PlatformFile {
  PickedFixture(this.file);
  final File file;
  @override
  String get name => 'SYNTHETIC_selected.pdf';
  @override
  Uri get uri => file.uri;
  @override
  Never get xFile => throw StateError('Unexpected picker API');
  @override
  int? lengthSync() => file.lengthSync();
  @override
  Future<int?> length() => file.length();
  @override
  Future<Uint8List> readAsBytes() => file.readAsBytes();
  @override
  Stream<Uint8List> readAsByteStream() => throw StateError('Unexpected stream');
}

class FixturePicker extends FilePickerPlatform {
  FixturePicker(this.file);
  final File file;
  int calls = 0;
  Completer<List<PlatformFile>>? pending;
  @override
  Future<List<PlatformFile>> pickFiles({
    String? dialogTitle,
    String? initialDirectory,
    FileType type = FileType.any,
    List<String>? allowedExtensions,
    Function(FilePickerStatus)? onFileLoading,
    int compressionQuality = 0,
    AndroidOptions androidOptions = const AndroidOptions(),
    DarwinOptions darwinOptions = const DarwinOptions(),
    WindowsOptions windowsOptions = const WindowsOptions(),
    LinuxOptions linuxOptions = const LinuxOptions(),
    WebOptions webOptions = const WebOptions(),
  }) async {
    expect(type, FileType.custom);
    expect(allowedExtensions, ['pdf']);
    calls++;
    return pending == null ? [PickedFixture(file)] : pending!.future;
  }
}

class Journey {
  Journey(this.root) {
    c = PatientController(
      ApiClient(client: MockClient(reply), storageClient: MockClient(reply)),
      LoopbackIdentity(
        identityApi = ApiClient(client: MockClient(reply)),
        enabled: true,
      ),
      store,
      root,
    );
  }
  final Directory root;
  final store = LocalStore(NativeDatabase.memory());
  late final PatientController c;
  late final ApiClient identityApi;
  String owner = 'one';
  bool offline = false,
      expired = false,
      denied = false,
      uploaded = false,
      confirmed = false;
  int sessions = 0, puts = 0, completes = 0;
  final confirmations = <Json>[];
  String selectedTitle = 'SYNTHETIC SELECTED PDF';
  Future<http.Response> reply(http.Request r) async {
    if (offline) throw http.ClientException('Controlled offline');
    http.Response json(Object body, [int status = 200]) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json'},
    );
    final path = r.url.path;
    if (path == '/ready') return json({'status': 'ready'});
    if (path == '/__wellq_local/adapter.js') {
      return http.Response("const nonce = 'widget-nonce'", 200);
    }
    if (path == '/__wellq_local/session') {
      expect(jsonDecode(r.body), {'role': 'patient'});
      sessions++;
      return json({
        'accessToken': 'explicit-widget-double-not-a-JWT',
        'role': 'patient',
        'resourceId': 'synthetic-local-patient-$owner',
        'tenantId': 'synthetic-local-widget',
        'permissions': [
          'clinical:read',
          'clinical:write',
          'extractions:confirm',
        ],
        'expiresAt': expired
            ? 1
            : DateTime.now()
                      .add(Duration(minutes: 10 + sessions))
                      .millisecondsSinceEpoch ~/
                  1000,
      });
    }
    if (r.method == 'PUT') {
      expect(r.headers.containsKey('Authorization'), false);
      expect(r.headers['x-goog-if-generation-match'], '0');
      expect(r.bodyBytes.take(5), utf8.encode('%PDF-'));
      puts++;
      return json({});
    }
    if (denied) return json({}, 403);
    expect(
      r.headers['Authorization'],
      'Bearer explicit-widget-double-not-a-JWT',
    );
    if (path == '/api/v1/clinical-tests') {
      return json({
        'items': [
          {
            'clinical_test_id': 'id-$owner',
            'title': 'SYNTHETIC EXAM $owner',
            'test_date': '2026-11-08',
            'status': 'ready_for_review',
          },
          if (uploaded)
            {
              'clinical_test_id': 'new-id',
              'title': selectedTitle,
              'test_date': '2026-11-08',
              'status': 'ready_for_review',
            },
        ],
        'next_cursor': null,
      });
    }
    if (path.endsWith('/initiate')) {
      return json({
        'upload_id': 'u1',
        'clinical_test_id': 'new-id',
        'upload': {
          'signed_url':
              'http://127.0.0.1:8765/object/quarantine/clinical-tests/widget',
          'required_headers': {'x-goog-if-generation-match': '0'},
          'expires_at': '2099-01-01T00:00:00Z',
        },
      });
    }
    if (path.endsWith('/complete')) {
      completes++;
      uploaded = true;
      return json({
        'upload_id': 'u1',
        'clinical_test_id': 'new-id',
        'status': 'processing',
      });
    }
    if (path.endsWith('/status')) {
      return json({
        'upload_id': 'u1',
        'clinical_test_id': 'new-id',
        'status': uploaded ? 'ready_for_review' : 'initiated',
        'local_file_can_be_deleted': uploaded,
        'processing': {'malware_scan': 'passed', 'mime_validation': 'passed'},
      });
    }
    if (path.endsWith('/extraction')) {
      if (r.method == 'PATCH') {
        confirmations.add(jsonDecode(r.body) as Json);
        confirmed = true;
      }
      final p = proposal()
        ..['status'] = confirmed ? 'confirmed' : 'awaiting_confirmation';
      if (confirmed) {
        ((p['panels'] as List).single['markers'] as List).single['value_raw'] =
            '90.0';
      }
      return json(p);
    }
    if (path.startsWith('/api/v1/clinical-tests/')) {
      return json({
        'clinical_test_id': path.split('/').last,
        'title': path.endsWith('new-id')
            ? selectedTitle
            : 'SYNTHETIC EXAM $owner',
        'status': 'ready_for_review',
        'test_date': '2026-11-08',
        'test_type': 'blood_test',
        'review': {'status': 'pending'},
      });
    }
    throw StateError('Uncontracted fixture request');
  }

  bool disposed = false;
  Future<void> dispose() async {
    if (disposed) return;
    disposed = true;
    c.dispose();
    identityApi.close();
    await store.close();
  }
}

Future<void> idle(WidgetTester t, Journey h) async {
  for (var i = 0; i < 100; i++) {
    await t.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    await t.pump(const Duration(milliseconds: 20));
    if (!h.c.busy && find.byType(LinearProgressIndicator).evaluate().isEmpty) {
      break;
    }
  }
  expect(h.c.busy, false, reason: 'Controller must finish bounded fixture I/O');
  await t.pumpAndSettle();
}

Future<void> tapText(WidgetTester t, String text) async {
  await t.scrollUntilVisible(
    find.text(text).last,
    160,
    scrollable: find.byType(Scrollable).first,
  );
  await t.pumpAndSettle();
  await t.tap(find.text(text).last);
  await t.pump();
}

Future<void> start(
  WidgetTester t,
  Journey h,
  LanguageController language,
) async {
  t.view.physicalSize = const Size(430, 1100);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(WellQApp(controller: h.c, language: language));
  await t.pumpAndSettle();
}

void main() {
  WidgetController.hitTestWarningShouldBeFatal = true;
  setUpAll(() => pdfrxInitialize());
  late Journey h;
  late LanguageController language;
  void patientTest(String name, Future<void> Function(WidgetTester) body) {
    testWidgets(name, (t) async {
      try {
        await body(t);
      } finally {
        await t.pumpWidget(const SizedBox.shrink());
        await t.runAsync(h.dispose);
      }
    }, timeout: const Timeout(Duration(minutes: 3)));
  }

  setUp(() async {
    h = Journey(
      await Directory.systemTemp.createTemp('wellq-patient-widgets-'),
    );
    language = LanguageController();
    await h.store.customSelect('SELECT 1').get();
  });
  tearDown(() async {
    await h.dispose();
    language.dispose();
  });
  for (final locale in ['es', 'en']) {
    patientTest(
      'patient login, navigation, renewal and private logout $locale',
      (t) async {
        await t.runAsync(() => language.select(locale));
        debugPrint('patient flow: locale ready');
        final l = lookupAppLocalizations(Locale(locale));
        await start(t, h, language);
        debugPrint('patient flow: welcome ready');
        expect(find.text(l.connectSynthetic), findsOneWidget);
        expect(find.byKey(const ValueKey('patient-tab/1')), findsNothing);
        await tapText(t, l.connectSynthetic);
        await idle(t, h);
        debugPrint('patient flow: login complete');
        expect(h.c.session?.role, 'patient');
        expect(h.sessions, 1);
        expect(find.text('SYNTHETIC EXAM one'), findsOneWidget);
        await t.tap(find.byKey(const ValueKey('patient-tab/1')));
        await t.pumpAndSettle();
        expect(find.text(l.myExams), findsOneWidget);
        await t.runAsync(
          () => h.c.queue(
            File('assets/synthetic.pdf').readAsBytesSync(),
            'SYNTHETIC PRIVATE',
            '2026-11-08',
          ),
        );
        await idle(t, h);
        final original = h.c.operations.single.serialize(),
            scope = h.c.session!.scope;
        debugPrint('patient flow: local operation saved');
        await t.tap(find.byKey(const ValueKey('patient-tab/4')));
        await t.pumpAndSettle();
        if (locale == 'en') {
          await tapText(t, l.changeAppearance);
          await t.pumpAndSettle();
        }
        final expiry = h.c.session!.expires;
        await tapText(t, l.renewPatientSession);
        await idle(t, h);
        expect(h.sessions, 2);
        expect(h.c.session!.expires.isAfter(expiry), true);
        expect(h.puts, 0);
        expect(h.c.operations.single.serialize(), original);
        await tapText(t, l.logout);
        await t.pumpAndSettle();
        await t.tap(find.text(l.confirmAction));
        await idle(t, h);
        expect(h.c.session, isNull);
        expect(find.text(l.connectSynthetic), findsOneWidget);
        expect(h.c.exams, isEmpty);
        expect(h.c.operations, isEmpty);
        expect(
          (await t.runAsync(() => h.store.pending(scope)))!.single.serialize(),
          original,
        );
        h.owner = 'two';
        await tapText(t, l.connectSynthetic);
        await idle(t, h);
        expect(h.c.session!.patient, endsWith('two'));
        expect(h.c.operations, isEmpty);
        expect(find.text('SYNTHETIC EXAM one'), findsNothing);
        expect(find.text('SYNTHETIC EXAM two'), findsOneWidget);
        expect(h.puts, 0);
        expect(t.takeException(), isNull);
        await t.pumpWidget(const SizedBox.shrink());
      },
    );
  }
  patientTest(
    'picker, real PDF viewer, durable queue, explicit send and patient correction',
    (t) async {
      final l = lookupAppLocalizations(const Locale('es'));
      final file = await t.runAsync(
        () => File(
          '${h.root.path}/selected.pdf',
        ).writeAsBytes(File('assets/synthetic.pdf').readAsBytesSync()),
      );
      final oldPicker = FilePickerPlatform.instance,
          picker = FixturePicker(file!);
      FilePickerPlatform.instance = picker;
      addTearDown(() => FilePickerPlatform.instance = oldPicker);
      await start(t, h, language);
      await tapText(t, l.connectSynthetic);
      await idle(t, h);
      await t.tap(find.byKey(const ValueKey('patient-tab/2')));
      await t.pumpAndSettle();
      await tapText(t, l.selectTestPdf);
      await idle(t, h);
      expect(picker.calls, 1);
      await tapText(t, l.viewDocument);
      for (
        var i = 0;
        i < 100 && find.text(l.pagesCount(1)).evaluate().isEmpty;
        i++
      ) {
        await t.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 40)),
        );
        await t.pump(const Duration(milliseconds: 40));
      }
      expect(find.text(l.pagesCount(1)), findsOneWidget);
      expect(find.byType(PdfViewer), findsOneWidget);
      await t.pumpAndSettle();
      await t.tap(find.byType(BackButton));
      await t.pumpAndSettle();
      await t.enterText(find.byType(TextField).first, h.selectedTitle);
      t.testTextInput.hide();
      await t.pumpAndSettle();
      for (final label in [
        l.confirmSyntheticOnly,
        l.authorizeSyntheticProcessing,
      ]) {
        await tapText(t, label);
        await t.pumpAndSettle();
      }
      await tapText(t, l.savePending);
      await idle(t, h);
      expect(h.c.operations.single.attempts, 0);
      expect(h.puts, 0);
      expect(find.text(l.pendingOperations), findsOneWidget);
      await tapText(t, l.sendDocument);
      await idle(t, h);
      expect(h.puts, 1);
      expect(h.completes, 1);
      await tapText(t, l.checkStatesConnection);
      await idle(t, h);
      expect(h.c.operations.single.phase, 'confirmed');
      await tapText(t, l.openExamExtraction);
      await idle(t, h);
      final value = find.byKey(const ValueKey('review/glucose/value'));
      await t.scrollUntilVisible(
        value,
        160,
        scrollable: find.byType(Scrollable).first,
      );
      await t.enterText(value, '90.0');
      t.testTextInput.hide();
      await t.pumpAndSettle();
      for (final label in [
        l.identityAcknowledgement,
        l.valuesAcknowledgement,
      ]) {
        await tapText(t, label);
        await t.pumpAndSettle();
      }
      await tapText(t, l.reviewConfirm);
      await t.pumpAndSettle();
      expect(h.confirmations, isEmpty);
      await t.tap(find.text(l.confirmAction));
      await idle(t, h);
      expect(h.confirmations, hasLength(1));
      expect(find.text('90.0 mg/dL'), findsOneWidget);
      expect(find.text(l.reviewConfirm), findsNothing);
      expect(h.c.operations.single.attempts, 1);
      expect(await t.runAsync(() => h.c.document('new-id')), isNotNull);
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox.shrink());
    },
  );
  patientTest(
    'selection locks saving and duplicate pickers while retaining the cancelled draft',
    (t) async {
      final l = lookupAppLocalizations(const Locale('es'));
      final file = await t.runAsync(
        () => File(
          '${h.root.path}/selected.pdf',
        ).writeAsBytes(File('assets/synthetic.pdf').readAsBytesSync()),
      );
      final oldPicker = FilePickerPlatform.instance,
          picker = FixturePicker(file!);
      FilePickerPlatform.instance = picker;
      addTearDown(() => FilePickerPlatform.instance = oldPicker);
      await start(t, h, language);
      await tapText(t, l.connectSynthetic);
      await idle(t, h);
      await t.tap(find.byKey(const ValueKey('patient-tab/2')));
      await t.pumpAndSettle();
      await tapText(t, l.selectTestPdf);
      await idle(t, h);
      for (final label in [
        l.confirmSyntheticOnly,
        l.authorizeSyntheticProcessing,
      ]) {
        await tapText(t, label);
        await t.pumpAndSettle();
      }
      expect(
        t
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, l.savePending),
            )
            .onPressed,
        isNotNull,
      );
      picker.pending = Completer<List<PlatformFile>>();
      await tapText(t, l.selectTestPdf);
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      expect(
        t
            .widget<TextButton>(
              find.widgetWithText(TextButton, l.selectTestPdf),
            )
            .onPressed,
        isNull,
      );
      await t.scrollUntilVisible(
        find.text(l.savePending),
        160,
        scrollable: find.byType(Scrollable).first,
      );
      await t.pump();
      expect(
        t
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, l.savePending),
            )
            .onPressed,
        isNull,
      );
      expect(picker.calls, 2);
      picker.pending!.complete([]);
      await idle(t, h);
      await t.scrollUntilVisible(
        find.text(l.savePending),
        160,
        scrollable: find.byType(Scrollable).first,
      );
      await t.pumpAndSettle();
      expect(
        t
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, l.savePending),
            )
            .onPressed,
        isNotNull,
      );
      expect(h.c.operations, isEmpty);
      expect(h.puts, 0);
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox.shrink());
    },
  );
  patientTest(
    'expiration dismisses the open private exam and preserves pending files',
    (t) async {
      final l = lookupAppLocalizations(const Locale('es'));
      await start(t, h, language);
      await tapText(t, l.connectSynthetic);
      await idle(t, h);
      await t.runAsync(
        () => h.c.queue(
          File('assets/synthetic.pdf').readAsBytesSync(),
          'SYNTHETIC EXPIRY',
          '2026-11-08',
        ),
      );
      await idle(t, h);
      final old = h.c.operations.single.serialize(), scope = h.c.session!.scope;
      await tapText(t, 'SYNTHETIC EXAM one');
      await idle(t, h);
      expect(find.byType(ExamScreen), findsOneWidget);
      await t.pump(const Duration(minutes: 20));
      await idle(t, h);
      expect(h.c.session, isNull);
      expect(find.byType(ExamScreen), findsNothing);
      expect(find.text(l.connectSynthetic), findsOneWidget);
      expect(
        (await t.runAsync(() => h.store.pending(scope)))!.single.serialize(),
        old,
      );
      expect(h.puts, 0);
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox.shrink());
    },
  );
  patientTest(
    'offline and expired identity remain gated; denied refresh clears private routes',
    (t) async {
      final l = lookupAppLocalizations(const Locale('es'));
      h.offline = true;
      await start(t, h, language);
      await tapText(t, l.connectSynthetic);
      await idle(t, h);
      expect(h.c.session, isNull);
      expect(find.text(l.errorOffline), findsOneWidget);
      h.offline = false;
      h.expired = true;
      await tapText(t, l.connectSynthetic);
      await idle(t, h);
      expect(h.c.session, isNull);
      expect(find.text(l.errorSession), findsOneWidget);
      h.expired = false;
      await tapText(t, l.connectSynthetic);
      await idle(t, h);
      h.offline = true;
      await t.tap(find.byTooltip(l.refreshReadings));
      await idle(t, h);
      expect(h.c.online, false);
      expect(find.text('SYNTHETIC EXAM one'), findsOneWidget);
      h.offline = false;
      h.denied = true;
      await t.tap(find.byTooltip(l.refreshReadings));
      await idle(t, h);
      expect(h.c.session, isNull);
      expect(find.text('SYNTHETIC EXAM one'), findsNothing);
      expect(find.text(l.connectSynthetic), findsOneWidget);
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox.shrink());
    },
  );
}
