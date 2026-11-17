// Isolated native Dart checks. HTTP doubles; no Flutter engine or real TLS.
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/domain/endpoint_policy.dart';
import 'package:wellq_mobile/domain/models.dart';

Future<void> main() async {
  var checks = 0;
  void check(bool ok) {
    if (!ok) throw StateError('Demo check failed');
    checks++;
  }

  for (final url in [
    'http://demo.example',
    'https://other.example',
    'https://name:pass@demo.example',
    'https://demo.example/base',
    'https://demo.example?key=value',
    'https://demo.example#fragment',
    'https://demo.example:8443',
    'https://127.0.0.1',
  ]) {
    try {
      EndpointPolicy(url, 'demo.example');
      throw StateError('Origin accepted');
    } on FormatException {
      checks++;
    }
  }
  check(EndpointPolicy('http://127.0.0.1:8765', '').local);
  final demoLocal = EndpointPolicy('http://127.0.0.1:9080', '127.0.0.1');
  check(!demoLocal.local);
  check(
    demoLocal.acceptsUpload(
      Uri.parse('http://127.0.0.1:9080/object/quarantine/clinical-tests/a'),
    ),
  );
  final policy = EndpointPolicy('https://demo.example', 'demo.example');
  check(
    policy.acceptsUpload(
      Uri.parse(
        'https://demo.example/object/quarantine/clinical-tests/a?signature=test',
      ),
    ),
  );
  for (final url in [
    'http://demo.example/object/quarantine/clinical-tests/a',
    'https://other.example/object/quarantine/clinical-tests/a',
    'https://demo.example/object/private/a',
    'https://user@demo.example/object/quarantine/clinical-tests/a',
  ]) {
    check(!policy.acceptsUpload(Uri.parse(url)));
  }
  var calls = 0;
  var validatedRequests = 0;
  final api = ApiClient(
    client: MockClient((request) async {
      calls++;
      const expectedOrigin = String.fromEnvironment(
        'WELLQ_DEMO_ORIGIN',
        defaultValue: 'https://demo.example',
      );
      check(request.url.origin == Uri.parse(expectedOrigin).origin);
      check(
        request.url.path ==
            switch (calls) {
              1 || 3 => '/api/v1/demo/login',
              2 || 4 => '/api/v1/demo/link-patient',
              _ => '',
            },
      );
      if (calls == 1 || calls == 3) {
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        check(body['role'] == 'patient');
        check(body['client_id'] == 'clinica_alemana');
        check(body['patient_id'] == 'paciente_ariel_demo');
        return http.Response(
          jsonEncode({
            'accessToken': 'synthetic-wire-token',
            'tenantId': 'clinica_alemana',
            'resourceId': 'paciente_ariel_demo',
            'role': 'patient',
            'permissions': ['clinical:read', 'clinical:write'],
            'capabilities': [],
            'expiresAt': DateTime.now().millisecondsSinceEpoch ~/ 1000 + 120,
          }),
          200,
        );
      }
      final body = jsonDecode(request.body) as Map<String, dynamic>;
      check(body['patient_id'] == 'paciente_ariel_demo');
      check(body['clinic_id'] == 'clinica_alemana');
      check(body['clinician_id'] == 'rene_faundez');
      validatedRequests++;
      return http.Response(jsonEncode({'status': 'linked'}), 200);
    }),
  );
  final identity = DemoIdentity(api, enabled: true);
  Future<void> denied(Future<Object?> Function() action, int status) async {
    try {
      await action();
      throw StateError('Expected rejection');
    } on ApiFailure catch (e) {
      check(e.status == status);
    }
  }

  const release =
      bool.fromEnvironment('dart.vm.product') ||
      bool.fromEnvironment('dart.vm.profile');
  if (release) {
    await denied(identity.connect, 403);
    check(calls == 0);
  } else {
    check((await identity.connect()).role == 'patient');
    await identity.connect();
    identity.signOut();
    await Future<void>.delayed(Duration.zero);
    check(calls == 4 && validatedRequests == 2);
  }
  await denied(LoopbackIdentity(api, enabled: true).connect, 403);
  await denied(DemoIdentity(api, enabled: false).connect, 403);
  api.close();
  stdout.writeln(
    '$checks native Dart checks passed; HTTP doubles; no Android/TLS execution',
  );
}
