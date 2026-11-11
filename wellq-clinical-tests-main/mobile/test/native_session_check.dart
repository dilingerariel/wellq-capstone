// Small native Dart checks. No Flutter engine, live services or user database.
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'package:wellq_mobile/domain/retry_after.dart';

Future<void> main() async {
  var passed = 0, requests = 0;
  void check(bool value, String name) {
    if (!value) throw StateError(name);
    passed++;
  }

  Future<ApiFailure> failure(Future<dynamic> action) async {
    try {
      await action;
    } on ApiFailure catch (e) {
      return e;
    }
    throw StateError('Expected safe rejection');
  }

  final now = DateTime.utc(2026, 11, 11, 15, 0, 0, 500);
  for (final value in [null, '', '-1', 'broken', '9999999999999999999999']) {
    check(retryAfterSeconds(value, now: now) == 0, 'invalid Retry-After');
  }
  check(retryAfterSeconds(' 120 ', now: now) == 120, 'numeric delay');
  check(retryAfterSeconds('0', now: now) == 0, 'zero delay');
  check(
    retryAfterSeconds(
          HttpDate.format(now.add(const Duration(seconds: 60))),
          now: now,
        ) ==
        60,
    'HTTP date rounds up without retrying early',
  );
  check(
    retryAfterSeconds(
          HttpDate.format(now.subtract(const Duration(seconds: 10))),
          now: now,
        ) ==
        0,
    'past date',
  );
  final api = ApiClient(
    client: MockClient((r) async {
      requests++;
      return http.Response(
        '{}',
        503,
        headers: {
          'retry-after': HttpDate.format(
            DateTime.now().add(const Duration(seconds: 60)),
          ),
        },
      );
    }),
  );
  try {
    final denied = await failure(
      LoopbackIdentity(api, enabled: false).connect(),
    );
    check(
      denied.code == 'DEBUG_IDENTITY_DISABLED' && requests == 0,
      'explicit opt-in required',
    );
    const nonDebug =
        bool.fromEnvironment('dart.vm.product') ||
        bool.fromEnvironment('dart.vm.profile');
    if (nonDebug) {
      final disabled = await failure(
        LoopbackIdentity(api, enabled: true).connect(),
      );
      check(
        disabled.code == 'DEBUG_IDENTITY_DISABLED' && requests == 0,
        'product/profile never contacts authority',
      );
    }
    final retry = await failure(api.send('GET', '/ready'));
    check(
      retry.status == 503 && retry.retryAfter >= 59 && retry.retryAfter <= 60,
      'API propagates HTTP-date backoff',
    );
    final storage = ApiClient(
      storageClient: MockClient(
        (_) async => http.Response('', 429, headers: {'retry-after': '42'}),
      ),
    );
    try {
      final e = await failure(
        storage.put(
          {
            'signed_url':
                'http://127.0.0.1:8765/object/quarantine/clinical-tests/test',
            'required_headers': {'x-goog-if-generation-match': '0'},
          },
          [1],
        ),
      );
      check(
        e.storage && e.status == 429 && e.retryAfter == 42,
        'storage propagates server delay',
      );
    } finally {
      storage.close();
    }
    final session = {
      'accessToken': 'explicit-unit-double-not-a-JWT',
      'resourceId': 'synthetic-local-patient-unit',
      'tenantId': 'synthetic-local-unit',
      'role': 'patient',
      'permissions': ['clinical:read'],
      'expiresAt':
          DateTime.now()
              .add(const Duration(minutes: 2))
              .millisecondsSinceEpoch ~/
          1000,
    };
    for (final changes in [
      {'role': 'clinician'},
      {'tenantId': 'real-tenant'},
      {'expiresAt': 1},
      {'permissions': <String>[]},
      {'resourceId': 'unbound-patient'},
    ]) {
      var rejected = false;
      try {
        Session.fromJson({...session, ...changes});
      } on ApiFailure {
        rejected = true;
      }
      check(rejected, 'session metadata rejected');
    }
    check(
      !Session.fromJson(session).toString().contains('explicit-unit'),
      'token never rendered',
    );
  } finally {
    api.close();
  }
  stdout.writeln(
    jsonEncode({
      'passed': passed,
      'failed': 0,
      'mode': 'isolated native Dart; controlled HTTP responses',
    }),
  );
}
