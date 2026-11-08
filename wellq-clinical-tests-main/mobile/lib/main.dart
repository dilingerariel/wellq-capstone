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
      const MaterialApp(
        home: Scaffold(
          body: SafeArea(
            child: Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'WellQ: modo productivo bloqueado. Solo debug con datos sinteticos.',
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
  final store = LocalStore(
    NativeDatabase.createInBackground(
      File('${root.path}/wellq_synthetic.sqlite'),
    ),
  );
  final api = ApiClient();
  runApp(
    WellQApp(
      controller: PatientController(
        api,
        LoopbackIdentity(api, enabled: enabled),
        store,
        root,
      ),
    ),
  );
}
