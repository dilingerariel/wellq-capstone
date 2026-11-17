import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../domain/models.dart';
import '../domain/endpoint_policy.dart';
import '../domain/retry_after.dart';

// Same compilation constants as Flutter kDebugMode. Keeping the HTTP clients
// independent of dart:ui also permits low-memory native Dart integration tests.
const _debugIdentity =
    !bool.fromEnvironment('dart.vm.product') &&
    !bool.fromEnvironment('dart.vm.profile');

abstract interface class IdentityAdapter {
  Future<Session> connect();
  void signOut();
}

class UploadCancellation {
  final _signal = Completer<void>();
  Future<void> get signal => _signal.future;
  void cancel() {
    if (!_signal.isCompleted) _signal.complete();
  }

  void check() {
    if (_signal.isCompleted) throw const ApiFailure(0, 'UPLOAD_PAUSED');
  }
}

class _Exchange {
  _Exchange(this.cancellation);
  final UploadCancellation? cancellation;
  final abort = Completer<void>();

  Future<http.Response> run(
    http.Client client,
    http.Request request,
    Duration deadline,
  ) async {
    cancellation?.check();
    final response = client.send(request).then(http.Response.fromStream);
    final signal = cancellation;
    try {
      return await (signal == null
              ? response
              : Future.any<http.Response>([
                  response,
                  signal.signal.then<http.Response>((_) {
                    if (!abort.isCompleted) abort.complete();
                    throw const ApiFailure(0, 'UPLOAD_PAUSED');
                  }),
                ]))
          .timeout(
            deadline,
            onTimeout: () {
              if (!abort.isCompleted) abort.complete();
              throw TimeoutException('Request deadline');
            },
          );
    } on http.RequestAbortedException {
      signal?.check();
      rethrow;
    }
  }
}

class ApiClient {
  ApiClient({http.Client? client, http.Client? storageClient})
    : client = client ?? http.Client(),
      storageClient = storageClient ?? http.Client();
  static final endpoint = EndpointPolicy.environment();
  static final origin = endpoint.origin;
  final http.Client client, storageClient;
  Future<http.Response> send(
    String method,
    String path, {
    Session? session,
    Json? body,
    String? key,
    UploadCancellation? cancellation,
  }) async {
    if (!path.startsWith('/') || path.startsWith('//')) {
      throw const ApiFailure(0, 'INVALID_PATH');
    }
    final exchange = _Exchange(cancellation);
    final req = http.AbortableRequest(
      method,
      origin.resolve(path),
      abortTrigger: exchange.abort.future,
    )..followRedirects = false;
    req.headers['Accept'] = 'application/json';
    if (session != null) {
      if (session.expired) throw const ApiFailure(401, 'SESSION_EXPIRED');
      req.headers['Authorization'] = 'Bearer ${session.token}';
    }
    if (key != null) req.headers['Idempotency-Key'] = key;
    if (body != null) {
      req.headers['Content-Type'] = 'application/json';
      req.body = jsonEncode(body);
    }
    try {
      final res = await exchange.run(client, req, const Duration(seconds: 20));
      if (res.statusCode < 200 || res.statusCode >= 300) {
        var code = 'HTTP_${res.statusCode}';
        try {
          final d = (jsonDecode(res.body) as Json)['detail'];
          if (d is Map &&
              d['code'] is String &&
              RegExp(r'^[A-Z0-9_]+$').hasMatch(d['code'] as String)) {
            code = d['code'] as String;
          }
        } catch (_) {
          /* No raw server error reflected. */
        }
        throw ApiFailure(
          res.statusCode,
          code,
          retryAfter: retryAfterSeconds(res.headers['retry-after']),
        );
      }
      return res;
    } on SocketException {
      throw const ApiFailure(0, 'NETWORK');
    } on http.ClientException {
      throw const ApiFailure(0, 'NETWORK');
    } on TimeoutException {
      throw const ApiFailure(0, 'TIMEOUT_UNCERTAIN');
    }
  }

  Future<Json> json(
    String method,
    String path, {
    Session? session,
    Json? body,
    String? key,
    UploadCancellation? cancellation,
  }) async {
    final res = await send(
      method,
      path,
      session: session,
      body: body,
      key: key,
      cancellation: cancellation,
    );
    try {
      return jsonDecode(res.body) as Json;
    } catch (_) {
      throw const ApiFailure(502, 'INVALID_RESPONSE');
    }
  }

  Future<void> ready() async {
    await send('GET', '/ready');
  }

  Future<void> put(
    Json descriptor,
    List<int> bytes, {
    UploadCancellation? cancellation,
  }) async {
    final uri = endpoint.origin.resolve(descriptor['signed_url'] as String);
    if (!endpoint.acceptsUpload(uri)) {
      throw const ApiFailure(403, 'STORAGE_ORIGIN_DENIED', storage: true);
    }
    final headers = Map<String, String>.from(
      descriptor['required_headers'] as Map,
    );
    if (headers.keys.any(
      (k) => ['authorization', 'cookie', 'host'].contains(k.toLowerCase()),
    )) {
      throw const ApiFailure(403, 'STORAGE_HEADER_DENIED', storage: true);
    }
    final demoCapability =
        uri.path == '/api/v1/demo/storage/upload' &&
        headers.entries.any(
          (entry) =>
              entry.key.toLowerCase() == 'x-wellq-upload-token' &&
              entry.value.isNotEmpty,
        ) &&
        headers.entries.any(
          (entry) =>
              entry.key.toLowerCase() == 'x-wellq-if-absent' &&
              entry.value == 'true',
        );
    final generation = headers.entries.where(
      (entry) => entry.key.toLowerCase() == 'x-goog-if-generation-match',
    );
    if (!demoCapability &&
        (generation.length != 1 || generation.single.value != '0')) {
      throw const ApiFailure(
        403,
        'STORAGE_PRECONDITION_REQUIRED',
        storage: true,
      );
    }
    final exchange = _Exchange(cancellation);
    final req =
        http.AbortableRequest('PUT', uri, abortTrigger: exchange.abort.future)
          ..followRedirects = false
          ..headers.addAll(headers)
          ..bodyBytes = bytes;
    try {
      final res = await exchange.run(
        storageClient,
        req,
        const Duration(seconds: 30),
      );
      // 412 can mean an immutable object already exists after an uncertain PUT.
      // Only backend hash/scan checks may confirm it. Never call this validation.
      if (!((res.statusCode >= 200 && res.statusCode < 300) ||
          res.statusCode == 412)) {
        throw ApiFailure(
          res.statusCode,
          'STORAGE_UPLOAD_FAILED',
          storage: true,
          retryAfter: retryAfterSeconds(res.headers['retry-after']),
        );
      }
    } on SocketException {
      throw const ApiFailure(0, 'STORAGE_NETWORK', storage: true);
    } on http.ClientException {
      throw const ApiFailure(0, 'STORAGE_NETWORK', storage: true);
    } on TimeoutException {
      throw const ApiFailure(0, 'STORAGE_UNCERTAIN', storage: true);
    }
  }

  void close() {
    client.close();
    storageClient.close();
  }
}

class LoopbackIdentity implements IdentityAdapter {
  LoopbackIdentity(this.api, {required this.enabled});
  final ApiClient api;
  final bool enabled;
  @override
  Future<Session> connect() async {
    if (!enabled || !_debugIdentity || !ApiClient.endpoint.local) {
      throw const ApiFailure(403, 'DEBUG_IDENTITY_DISABLED');
    }
    await api.ready();
    final js = await api.send('GET', '/__wellq_local/adapter.js');
    final nonce = RegExp(
      "const nonce = '([^']+)'",
    ).firstMatch(js.body)?.group(1);
    if (nonce == null) {
      throw const ApiFailure(503, 'LOCAL_AUTHORITY_UNAVAILABLE');
    }
    final exchange = _Exchange(null);
    final req =
        http.AbortableRequest(
            'POST',
            ApiClient.origin.resolve('/__wellq_local/session'),
            abortTrigger: exchange.abort.future,
          )
          ..followRedirects = false
          ..headers.addAll({
            'Content-Type': 'application/json',
            'X-WellQ-Local': nonce,
          })
          ..body = jsonEncode({'role': 'patient'});
    try {
      final res = await exchange.run(
        api.client,
        req,
        const Duration(seconds: 15),
      );
      if (res.statusCode != 200) {
        throw ApiFailure(res.statusCode, 'LOCAL_AUTHORITY_DENIED');
      }
      return Session.fromJson(jsonDecode(res.body) as Json);
    } on SocketException {
      throw const ApiFailure(0, 'IDENTITY_NETWORK');
    } on http.ClientException {
      throw const ApiFailure(0, 'IDENTITY_NETWORK');
    } on TimeoutException {
      throw const ApiFailure(0, 'IDENTITY_TIMEOUT');
    }
  }

  @override
  void signOut() {} // Controller owns RAM tokens. No signing or persisted JWT.
}

/// Synthetic demo only. The API issues a patient session for the fixed demo
/// identity; no token or access code is compiled into or persisted by the app.
class DemoIdentity implements IdentityAdapter {
  DemoIdentity(this.api, {required this.enabled});
  final ApiClient api;
  final bool enabled;
  @override
  Future<Session> connect() async {
    if (!enabled || !_debugIdentity || ApiClient.endpoint.local) {
      throw const ApiFailure(403, 'DEBUG_IDENTITY_DISABLED');
    }
    final data = await api.json(
      'POST',
      '/api/v1/demo/login',
      body: {
        'role': 'patient',
        'client_id': 'clinica_alemana',
        'patient_id': 'paciente_ariel_demo',
      },
    );
    final session = Session.fromJson(data);
    await api.json(
      'POST',
      '/api/v1/demo/link-patient',
      body: {
        'patient_id': 'paciente_ariel_demo',
        'clinic_id': 'clinica_alemana',
        'clinician_id': 'rene_faundez',
      },
    );
    return session;
  }

  @override
  void signOut() {} // Controller immediately clears RAM state; JWTs expire server-side.
}
