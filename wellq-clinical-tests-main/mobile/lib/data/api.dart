import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';

import 'package:http/http.dart' as http;

import '../domain/models.dart';

abstract interface class IdentityAdapter {
  Future<Session> connect();
  void signOut();
}

class ApiClient {
  ApiClient({http.Client? client, http.Client? storageClient})
    : client = client ?? http.Client(),
      storageClient = storageClient ?? http.Client();
  static final origin = Uri.parse('http://127.0.0.1:8765');
  final http.Client client, storageClient;
  Future<http.Response> send(
    String method,
    String path, {
    Session? session,
    Json? body,
    String? key,
  }) async {
    if (!path.startsWith('/') || path.startsWith('//')) {
      throw const ApiFailure(0, 'INVALID_PATH');
    }
    final req = http.Request(method, origin.resolve(path))
      ..followRedirects = false;
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
      final res = await http.Response.fromStream(
        await client.send(req),
      ).timeout(const Duration(seconds: 20));
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
          retryAfter: int.tryParse(res.headers['retry-after'] ?? '') ?? 0,
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
  }) async {
    final res = await send(
      method,
      path,
      session: session,
      body: body,
      key: key,
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

  Future<void> put(Json descriptor, List<int> bytes) async {
    final uri = Uri.parse(descriptor['signed_url'] as String);
    if (uri.scheme != 'http' ||
        uri.host != '127.0.0.1' ||
        uri.port != 8765 ||
        uri.userInfo.isNotEmpty ||
        !uri.path.startsWith('/object/quarantine/clinical-tests/')) {
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
    final req = http.Request('PUT', uri)
      ..followRedirects = false
      ..headers.addAll(headers)
      ..bodyBytes = bytes;
    try {
      final res = await http.Response.fromStream(
        await storageClient.send(req),
      ).timeout(const Duration(seconds: 30));
      // 412 can mean an immutable object already exists after an uncertain PUT.
      // Only backend hash/scan checks may confirm it. Never call this validation.
      if (!((res.statusCode >= 200 && res.statusCode < 300) ||
          res.statusCode == 412)) {
        throw ApiFailure(
          res.statusCode,
          'STORAGE_UPLOAD_FAILED',
          storage: true,
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
    if (!enabled || !kDebugMode) {
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
    final req =
        http.Request('POST', ApiClient.origin.resolve('/__wellq_local/session'))
          ..followRedirects = false
          ..headers.addAll({
            'Content-Type': 'application/json',
            'X-WellQ-Local': nonce,
          })
          ..body = jsonEncode({'role': 'patient'});
    try {
      final res = await http.Response.fromStream(
        await api.client.send(req),
      ).timeout(const Duration(seconds: 15));
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
