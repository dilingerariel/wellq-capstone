import 'dart:convert';
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/data/uploads.dart';
import 'package:wellq_mobile/domain/models.dart';

import 'foundation_test.dart' show patient;
import 'phase4_durable_test.dart' show active, remote, signed;

// Redirect only the test transport to an ephemeral fixture. Production client
// origin checks are unchanged; this test never connects to an existing bridge.
class FixtureTransport extends http.BaseClient {
  FixtureTransport(this.port);
  final int port;
  final _client = http.Client();

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    if (request is! http.AbortableRequest ||
        request.url.host != '127.0.0.1' ||
        request.url.port != 8765 ||
        request.url.scheme != 'http') {
      throw StateError('Unexpected fixture destination');
    }
    final local =
        http.AbortableRequest(
            request.method,
            request.url.replace(port: port),
            abortTrigger: request.abortTrigger,
          )
          ..followRedirects = false
          ..bodyBytes = request.bodyBytes
          ..headers.addAll(request.headers);
    return _client.send(local);
  }

  @override
  void close() => _client.close();
}

void main() {
  test(
    'real loopback HTTP recovers an acknowledged object with a lost complete response',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      addTearDown(() => server.close(force: true));
      final root = await Directory.systemTemp.createTemp('wellq-phase4-http-');
      addTearDown(() => root.delete(recursive: true));
      final db = LocalStore(NativeDatabase.memory());
      addTearDown(db.close);
      final api = ApiClient(
        client: FixtureTransport(server.port),
        storageClient: FixtureTransport(server.port),
      );
      addTearDown(api.close);
      final s = patient();
      final pdf = await File('assets/synthetic.pdf').readAsBytes();
      var puts = 0, completions = 0, init = 0;
      var state = 'initiated';
      final methods = <String>[];
      final fixtureErrors = <String>[];
      server.listen((request) async {
        try {
          final part = request.uri.pathSegments.last;
          methods.add('${request.method} $part');
          final bytes = await request.fold<List<int>>(
            [],
            (all, chunk) => all..addAll(chunk),
          );
          Json body = {};
          if (request.method == 'PUT') {
            if (request.headers.value('authorization') != null ||
                request.headers.value('x-goog-if-generation-match') != '0' ||
                bytes.length != pdf.length ||
                !List.generate(
                  pdf.length,
                  (i) => bytes[i] == pdf[i],
                ).every((v) => v)) {
              throw StateError('Fixture PUT contract failed');
            }
            puts++;
          } else {
            if (request.headers.value('authorization') != 'Bearer ${s.token}') {
              throw StateError('Fixture auth boundary failed');
            }
            if (part == 'initiate') {
              init++;
              body = {...remote, 'upload': signed};
            } else if (part == 'status') {
              body = {...remote, 'status': state};
            } else if (part == 'complete') {
              if (puts != 1) throw StateError('Fixture object missing');
              completions++;
              state = 'processing';
              final socket = await request.response.detachSocket(
                writeHeaders: false,
              );
              socket.destroy(); // Only the test's connection; emulate lost ACK.
              return;
            } else {
              throw StateError('Unexpected fixture request');
            }
          }
          request.response.headers.contentType = ContentType.json;
          request.response.write(jsonEncode(body));
          await request.response.close();
        } catch (_) {
          fixtureErrors.add('Fixture protocol failure');
          request.response.statusCode = 500;
          await request.response.close();
        }
      });
      var now = DateTime.now();
      final repo = UploadRepository(api, db, FileVault(root), clock: () => now);
      final op = await repo.queue(
        s,
        pdf,
        'SYNTHETIC HTTP PHASE 4',
        '2026-11-08',
        active,
      );
      expect(methods, isEmpty);
      await expectLater(repo.resume(op, s, active), throwsA(isA<ApiFailure>()));
      expect(op.phase, 'complete_pending');
      now = DateTime.fromMillisecondsSinceEpoch(op.retryAt);
      await repo.resume(op, s, active);
      expect(op.phase, 'processing');
      expect(op.canDelete, isFalse);
      expect([init, puts, completions], [1, 1, 1]);
      expect(methods, [
        'POST initiate',
        'GET status',
        'PUT phase4',
        'POST complete',
        'GET status',
      ]);
      expect(fixtureErrors, isEmpty);
    },
  );
}
