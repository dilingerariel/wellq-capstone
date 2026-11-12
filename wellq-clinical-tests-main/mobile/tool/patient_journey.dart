// Opt-in native Dart integration using the SAME mobile clients and Drift.
// No Flutter engine or Android device. Never logs JWTs or signed URLs.
import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:drift/native.dart';
import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';
import 'package:wellq_mobile/data/api.dart';
import 'package:wellq_mobile/data/local_store.dart';
import 'package:wellq_mobile/data/uploads.dart';
import 'package:wellq_mobile/domain/extraction_draft.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'package:wellq_mobile/domain/sample_policy.dart';

class LostPutAcknowledgment extends http.BaseClient {
  final _wire = http.Client();
  bool loseNext = true;
  int puts = 0;
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    if (request.method != 'PUT' ||
        request.url.host != '127.0.0.1' ||
        request.url.port != 8765) {
      throw StateError('Unexpected storage destination');
    }
    puts++;
    final response = await _wire.send(request);
    if (loseNext && response.statusCode >= 200 && response.statusCode < 300) {
      loseNext = false;
      await response.stream.drain<void>();
      throw http.ClientException('Synthetic lost acknowledgment');
    }
    return response;
  }

  @override
  void close() => _wire.close();
}

Future<void> main(List<String> args) async {
  if (args.length != 2 ||
      !['access', 'offline', 'upload', 'verify'].contains(args[0])) {
    throw ArgumentError(
      'Usage: patient_journey.dart access|offline|upload|verify PRIVATE_MANIFEST',
    );
  }
  final stage = args[0], manifest = File(args[1]);
  final info = jsonDecode(await manifest.readAsString()) as Json;
  if (info['synthetic_only'] != true ||
      info['project'] != 'wellq-int-39706292db88' ||
      !(info['run'] as String).startsWith('native-journey-')) {
    throw StateError('An explicitly owned synthetic manifest is required');
  }
  var passed = 0;
  void check(bool value, String name) {
    if (!value) throw StateError(name);
    passed++;
  }

  Future<void> save() => manifest.writeAsString(jsonEncode(info), flush: true);
  final api = ApiClient();
  LocalStore? store;
  try {
    final identity = LoopbackIdentity(api, enabled: true);
    final s = await identity.connect();
    check(
      s.role == 'patient' &&
          s.patient == info['patient'] &&
          s.tenant == info['tenant'],
      'verified synthetic identity',
    );
    final page = ExamPage.fromJson(
      await api.json('GET', '/api/v1/clinical-tests', session: s),
    );
    check(page.items.isNotEmpty, 'own exams available from real FastAPI');
    try {
      await api.json('GET', '/api/v1/clinical-tests');
      throw StateError('Unauthenticated access unexpectedly allowed');
    } on ApiFailure catch (e) {
      check(e.status == 401, 'unauthenticated API rejected');
    }
    try {
      await api.json(
        'GET',
        '/api/v1/patients/${Uri.encodeComponent(s.patient)}/lab-score',
        session: s,
      );
      throw StateError('Patient score unexpectedly allowed');
    } on ApiFailure catch (e) {
      check(e.status == 403, 'patient cannot access professional score');
    }
    if (stage == 'access') {
      info['patient_access_real'] = true;
    } else if (stage == 'offline') {
      if (info.containsKey('offline_root')) {
        throw StateError('Never replace an existing offline verification');
      }
      final root = await Directory.systemTemp.createTemp(
        'wellq-native-offline-',
      );
      store = LocalStore(NativeDatabase(File('${root.path}/queue.sqlite')));
      final bytes = await File('assets/synthetic.pdf').readAsBytes();
      check(
        sha256.convert(bytes).toString() == syntheticPdfSha256,
        'reviewed synthetic fixture only',
      );
      final op = await UploadRepository(api, store, FileVault(root)).queue(
        s,
        bytes,
        'SYNTHETIC OFFLINE ${info['run']}',
        '2026-11-08',
        () {},
      );
      check(
        op.attempts == 0 && op.uploadId == null,
        'offline operation never transmitted',
      );
      info.addAll({
        'offline_root': root.path,
        'offline_operation': op.serialize(),
      });
      // This process exits. The verify invocation must reopen this exact row.
    } else if (stage == 'upload') {
      if (info['write_authorized'] != true ||
          info.containsKey('local_root') ||
          info.containsKey('clinical_test_id')) {
        throw StateError(
          'One new synthetic exam per authorized manifest; never replay an old run',
        );
      }
      final root = await Directory.systemTemp.createTemp(
        'wellq-native-journey-',
      );
      info['local_root'] = root.path;
      await save(); // A repeated invocation cannot create a second operation.
      final database = File('${root.path}/queue.sqlite');
      store = LocalStore(NativeDatabase(database));
      final bytes = await File('assets/synthetic.pdf').readAsBytes();
      check(
        sha256.convert(bytes).toString() == syntheticPdfSha256,
        'reviewed synthetic fixture only',
      );
      var repo = UploadRepository(api, store, FileVault(root));
      var op = await repo.queue(
        s,
        bytes,
        'SYNTHETIC CROSS CLIENT ${info['run']}',
        '2026-11-08',
        () {},
      );
      final before = op.serialize();
      final key = op.initiateKey, hash = op.initiate['sha256'];
      check(
        op.attempts == 0 && op.uploadId == null,
        'offline save does not send',
      );
      check(
        (await store.pending(
          '${s.tenant}/synthetic-local-patient-other',
        )).isEmpty,
        'different patient cannot read Drift',
      );
      await store.close();
      store = LocalStore(NativeDatabase(database));
      await store.recover();
      op = (await store.pending(s.scope)).single;
      check(
        op.serialize() == before && op.initiateKey == key,
        'SQLite reopen preserves exact operation and zero attempts',
      );
      check(
        sha256
                .convert(await FileVault(root).resolve(op.file).readAsBytes())
                .toString() ==
            hash,
        'private copy hash retained',
      );
      final losing = LostPutAcknowledgment();
      final interrupted = ApiClient(storageClient: losing);
      try {
        repo = UploadRepository(interrupted, store, FileVault(root));
        try {
          await repo.resume(op, s, () {});
          throw StateError('Missing simulated loss');
        } on ApiFailure catch (e) {
          check(
            e.status == 0 && losing.puts == 1,
            'real PUT committed before its reply was lost',
          );
        }
      } finally {
        interrupted.close();
      }
      check(
        op.phase == 'bytes_pending' && op.uploadId != null && !op.canDelete,
        'uncertain upload preserved without false success',
      );
      await store.close();
      store = LocalStore(NativeDatabase(database));
      await store.recover();
      op = (await store.pending(s.scope)).single;
      final wait = op.retryAt - DateTime.now().millisecondsSinceEpoch;
      if (wait > 0) {
        await Future<void>.delayed(Duration(milliseconds: wait + 50));
      }
      repo = UploadRepository(api, store, FileVault(root));
      await repo.resume(
        op,
        s,
        () {},
      ); // Explicit authorization of this one retry.
      final replay = await api.json(
        'POST',
        '/api/v1/clinical-tests/uploads/initiate',
        session: s,
        body: op.initiate,
        key: op.initiateKey,
      );
      check(
        replay['clinical_test_id'] == op.examId &&
            replay['upload_id'] == op.uploadId,
        'initiate replay returns the same exam',
      );
      for (var i = 0; i < 90 && !op.finished; i++) {
        await Future<void>.delayed(const Duration(seconds: 1));
        await repo.reconcile(op, s, () {});
      }
      check(
        op.phase == 'confirmed' && op.canDelete,
        'durable reception verified by backend',
      );
      Json? proposal;
      for (var i = 0; i < 60; i++) {
        try {
          final value = await api.json(
            'GET',
            '/api/v1/clinical-tests/${op.examId}/extraction',
            session: s,
          );
          if (value['status'] == 'awaiting_confirmation') {
            proposal = value;
            break;
          }
        } on ApiFailure catch (e) {
          if (e.status != 404 &&
              !(e.status == 409 && e.code == 'EXTRACTION_NOT_READY')) {
            rethrow;
          }
        }
        await Future<void>.delayed(const Duration(seconds: 1));
      }
      check(proposal != null, 'synthetic extraction ready for patient review');
      final body = ExtractionDraft(proposal!).body('confirm', true),
          confirmationKey = const Uuid().v4();
      final confirmed = await api.json(
        'PATCH',
        '/api/v1/clinical-tests/${op.examId}/extraction',
        session: s,
        body: body,
        key: confirmationKey,
      );
      final repeated = await api.json(
        'PATCH',
        '/api/v1/clinical-tests/${op.examId}/extraction',
        session: s,
        body: body,
        key: confirmationKey,
      );
      check(
        confirmed['status'] == 'confirmed' &&
            repeated['extraction_id'] == confirmed['extraction_id'],
        'patient confirmation is idempotent, distinct from clinical validation',
      );
      final doc = await api.json(
        'GET',
        '/api/v1/clinical-tests/${op.examId}',
        session: s,
      );
      final listed = ExamPage.fromJson(
        await api.json('GET', '/api/v1/clinical-tests', session: s),
      );
      check(
        listed.items.where((e) => e.id == op.examId).length == 1 &&
            op.initiateKey == key,
        'one logical exam after interrupted PUT and retry',
      );
      check(
        await FileVault(root).verified(FileVault(root).resolve(op.file), op) !=
            null,
        'original PDF retained after durable reception',
      );
      info.addAll({
        'clinical_test_id': op.examId,
        'upload_id': op.uploadId,
        'client_upload_id': op.id,
        'extraction_id': confirmed['extraction_id'],
        'clinical_version': doc['clinical_version'],
        'patient_confirmed': true,
        'title': op.title,
        'attempts': op.attempts,
      });
    } else {
      check(info['react_validated'] == true, 'React handoff completed');
      final id = info['clinical_test_id'] as String;
      final doc = await api.json(
        'GET',
        '/api/v1/clinical-tests/$id',
        session: s,
      );
      final ext = await api.json(
        'GET',
        '/api/v1/clinical-tests/$id/extraction',
        session: s,
      );
      check(
        doc['patient_id'] == s.patient &&
            (doc['review'] as Map)['status'] == 'reviewed',
        'same patient sees professional review',
      );
      check(
        ext['status'] == 'clinically_validated' &&
            ext['extraction_id'] == info['extraction_id'],
        'same extraction validated by authorized clinician',
      );
      check(
        !jsonEncode([doc, ext]).contains('SYNTHETIC CROSS PRIVATE'),
        'professional private notes not exposed to patient',
      );
      info['patient_observed_final'] = true;
      final root = Directory(info['local_root'] as String);
      store = LocalStore(NativeDatabase(File('${root.path}/queue.sqlite')));
      await store.recover();
      final op = (await store.pending(s.scope)).single;
      check(
        op.id == info['client_upload_id'] &&
            op.examId == id &&
            op.attempts == info['attempts'],
        'uploaded operation survives a new Dart process',
      );
      check(
        await FileVault(root).verified(FileVault(root).resolve(op.file), op) !=
            null,
        'uploaded private PDF remains intact',
      );
      await store.close();
      final offline = Directory(info['offline_root'] as String);
      store = LocalStore(NativeDatabase(File('${offline.path}/queue.sqlite')));
      await store.recover();
      final pending = (await store.pending(s.scope)).single;
      check(
        pending.serialize() == info['offline_operation'] &&
            pending.attempts == 0 &&
            pending.uploadId == null,
        'cold process restart preserves exact pending operation with zero attempts',
      );
      check(
        await FileVault(
              offline,
            ).verified(FileVault(offline).resolve(pending.file), pending) !=
            null,
        'offline private PDF hash preserved',
      );
      check(
        (await store.pending(
          '${s.tenant}/synthetic-local-patient-other',
        )).isEmpty,
        'cold process restart maintains patient isolation',
      );
    }
    info['${stage}_checks'] = passed;
    await save();
    stdout.writeln(
      jsonEncode({
        'stage': stage,
        'passed': passed,
        'failed': 0,
        'real_FastAPI': true,
        'Flutter_widgets': false,
      }),
    );
  } finally {
    api.close();
    await store?.close();
    // Retain this run's isolated SQLite/PDF as evidence; never touch Android.
  }
}
