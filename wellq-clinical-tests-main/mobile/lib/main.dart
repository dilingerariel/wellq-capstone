import 'application/language_controller.dart';
import 'data/language_preference.dart';
import 'l10n/localized_copy.dart';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:drift/native.dart';
import 'package:path_provider/path_provider.dart';
import 'application/patient_controller.dart';
import 'data/api.dart';
import 'data/local_store.dart';
import 'presentation/app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  const enabled = kDebugMode && bool.fromEnvironment('WELLQ_SYNTHETIC');
  if (!enabled) {
    runApp(
      MaterialApp(
        locale: const Locale('es'),
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        home: Scaffold(
          body: SafeArea(
            child: Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Builder(
                  builder: (context) => Text(context.l10n.productionBlocked),
                ),
              ),
            ),
          ),
        ),
      ),
    );
    return;
  }
  final root = await getApplicationSupportDirectory();
  await root.create(recursive: true);
  final language = LanguageController(
    preference: LanguagePreference(File('${root.path}/language.pref')),
  );
  await language.load();
  final store = LocalStore(
    NativeDatabase.createInBackground(
      File('${root.path}/wellq_synthetic.sqlite'),
    ),
  );
  final api = ApiClient();
  runApp(
    WellQApp(
      language: language,
      controller: PatientController(
        api,
        LoopbackIdentity(api, enabled: enabled),
        store,
        root,
      ),
    ),
  );
}
