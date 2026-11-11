import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:uuid/uuid.dart';

import '../domain/models.dart';
import '../domain/sample_policy.dart';
import 'api.dart';
import 'local_store.dart';

class FileVault {
  FileVault(this.root);
  final Directory root;
  Directory get directory => Directory('${root.path}/uploads');
  File resolve(String name) {
    if (!RegExp(r'^uploads/[a-f0-9-]{36}\.pdf$').hasMatch(name)) {
      throw StateError('Invalid private reference');
    }
    return File('${root.path}/$name');
  }

  void validateSample(List<int> bytes) {
    if (bytes.length > 20 * 1024 * 1024 ||
        sha256.convert(bytes).toString() != syntheticPdfSha256) {
      throw const ApiFailure(422, 'ONLY_BUNDLED_SYNTHETIC_PDF');
    }
  }

  File staged(PendingUpload op) => File('${resolve(op.file).path}.part');

  Future<void> stage(PendingUpload op, List<int> bytes) async {
    await directory.create(recursive: true);
    final part = staged(op);
    await part.create(exclusive: true);
    await part.writeAsBytes(bytes, flush: true);
  }

  Future<List<int>?> verified(File file, PendingUpload op) async {
    final size = op.initiate['size_bytes'];
    if (size is! int ||
        size <= 0 ||
        size > 20 * 1024 * 1024 ||
        op.file != 'uploads/${op.id}.pdf' ||
        op.initiate['sha256'] != syntheticPdfSha256 ||
        await FileSystemEntity.type(file.path, followLinks: false) !=
            FileSystemEntityType.file ||
        await file.length() != size) {
      return null;
    }
    final bytes = await file.readAsBytes();
    return bytes.length == size &&
            sha256.convert(bytes).toString() == syntheticPdfSha256
        ? bytes
        : null;
  }

  Future<String?> inspect(PendingUpload op, void Function() check) async {
    try {
      final file = resolve(op.file);
      final type = await FileSystemEntity.type(file.path, followLinks: false);
      if (type != FileSystemEntityType.notFound) {
        return await verified(file, op) == null ? 'corrupt' : null;
      }
      final part = staged(op);
      if (await FileSystemEntity.type(part.path, followLinks: false) ==
          FileSystemEntityType.notFound) {
        return 'missing';
      }
      if (op.payload['copy_pending'] != true ||
          await verified(part, op) == null) {
        return 'incomplete';
      }
      check();
      // Single process + operation lease. Never replace an existing final file.
      if (await FileSystemEntity.type(file.path, followLinks: false) !=
          FileSystemEntityType.notFound) {
        return 'corrupt';
      }
      check();
      await part.rename(file.path);
      return null;
    } on FileSystemException {
      return 'unreadable';
    } on StateError {
      return 'corrupt';
    }
  }

  Future<int> countUnreferenced(Set<String> ids) async {
    if (!await directory.exists()) return 0;
    var count = 0;
    await for (final entry in directory.list(followLinks: false)) {
      final match = RegExp(
        r'^([a-f0-9-]{36})\.pdf(?:\.part)?$',
      ).firstMatch(entry.uri.pathSegments.last);
      if (match != null && !ids.contains(match.group(1))) count++;
    }
    return count;
  }
}

class UploadRepository {
  UploadRepository(
    this.api,
    this.store,
    this.vault, {
    DateTime Function()? clock,
    int Function(int)? jitter,
  }) : clock = clock ?? DateTime.now,
       jitter = jitter ?? Random().nextInt;
  final ApiClient api;
  final LocalStore store;
  final FileVault vault;
  final DateTime Function() clock;
  final int Function(int) jitter;

  void _requireWriter(
    PendingUpload op,
    Session session,
    void Function() check,
  ) {
    check();
    if (op.scope != session.scope) throw const ApiFailure(403, 'OWNER_CHANGED');
    if (session.expired || !session.permissions.contains('clinical:write')) {
      throw const ApiFailure(403, 'UPLOAD_PERMISSION');
    }
  }

  Future<PendingUpload> queue(
    Session session,
    List<int> bytes,
    String title,
    String date,
    void Function() check,
  ) async {
    if (session.expired || !session.permissions.contains('clinical:write')) {
      throw const ApiFailure(403, 'UPLOAD_PERMISSION');
    }
    if (title.trim().isEmpty ||
        title.length > 200 ||
        !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(date)) {
      throw const ApiFailure(422, 'INPUT');
    }
    final id = const Uuid().v4();
    vault.validateSample(bytes);
    check();
    final op = PendingUpload(id, session.scope, {
      'title': title.trim(),
      'file': 'uploads/$id.pdf',
      'copy_pending': true,
      'initiate_key': const Uuid().v4(),
      'complete_key': const Uuid().v4(),
      'initiate': {
        'client_upload_id': id,
        'file_name': 'synthetic.pdf',
        'mime_type': 'application/pdf',
        'size_bytes': bytes.length,
        'sha256': sha256.convert(bytes).toString(),
        'test_type': 'blood_test',
        'title': title.trim(),
        'test_date': date,
        'ai_consent': true,
      },
    });
    await store.enqueue(op);
    final lease = const Uuid().v4();
    if (!await store.claim(op.scope, op.id, lease: lease)) {
      throw const ApiFailure(409, 'LOCAL_LEASE_LOST');
    }
    try {
      check();
      try {
        await vault.stage(op, bytes);
      } on FileSystemException {
        check();
        op.payload['file_issue'] = 'unreadable';
        await store.save(op, lease: lease);
        return op; // The durable row and any partial bytes are kept.
      }
      await _inspect(op, check, lease);
    } finally {
      await store.release(op.scope, op.id, lease: lease);
    }
    return op;
  }

  Future<void> _inspect(
    PendingUpload op,
    void Function() check,
    String lease,
  ) async {
    check();
    final issue = await vault.inspect(op, check);
    check();
    if (issue == op.fileIssue &&
        (issue != null || op.payload['copy_pending'] != true)) {
      return;
    }
    if (issue == null) {
      op.payload.remove('file_issue');
      op.payload.remove('copy_pending');
    } else {
      op.payload['file_issue'] = issue;
    }
    await store.save(op, lease: lease);
  }

  Future<int> recoverFiles(Session session, void Function() check) async {
    for (final op in await store.pending(session.scope)) {
      check();
      final lease = const Uuid().v4();
      if (!await store.claim(op.scope, op.id, lease: lease)) continue;
      try {
        final current = await store.operation(op.scope, op.id);
        if (current != null) await _inspect(current, check, lease);
      } finally {
        await store.release(op.scope, op.id, lease: lease);
      }
    }
    check();
    final count = await vault.countUnreferenced(await store.referencedIds());
    check();
    return count;
  }

  Future<void> reconcile(
    PendingUpload op,
    Session session,
    void Function() check,
  ) async {
    check();
    if (op.scope != session.scope) throw const ApiFailure(403, 'OWNER_CHANGED');
    if (op.uploadId == null || op.finished) return;
    final lease = const Uuid().v4();
    if (!await store.claim(op.scope, op.id, lease: lease)) return;
    try {
      await _requireCurrent(op);
      await _reconcile(op, session, check, lease);
    } finally {
      await store.release(op.scope, op.id, lease: lease);
    }
  }

  Future<void> _requireCurrent(PendingUpload op) async {
    final saved = await store.operation(op.scope, op.id);
    if (saved?.serialize() != op.serialize()) {
      throw const ApiFailure(409, 'STALE_LOCAL_OPERATION');
    }
  }

  Future<void> _reconcile(
    PendingUpload op,
    Session session,
    void Function() check,
    String lease, {
    UploadCancellation? cancellation,
  }) async {
    check();
    final s = await api.json(
      'GET',
      '/api/v1/clinical-tests/uploads/${Uri.encodeComponent(op.uploadId!)}/status',
      session: session,
      cancellation: cancellation,
    );
    check();
    _verifyRemote(op, s);
    var phase = verifiedUploadPhase(s);
    if (phase == 'bytes_pending') {
      if (op.phase == 'processing' || op.phase == 'object_uploaded') {
        throw const ApiFailure(502, 'UNEXPECTED_UPLOAD_REGRESSION');
      }
      // A successful PUT is a durable checkpoint even if complete was lost.
      if (op.phase == 'complete_pending' || op.phase == 'conflict') return;
    }
    if (phase == 'confirmed') {
      final processing = s['processing'];
      if (processing is! Map ||
          processing['malware_scan'] != 'passed' ||
          processing['mime_validation'] != 'passed') {
        throw const ApiFailure(502, 'UNVERIFIED_READY_RESPONSE');
      }
    }
    if (phase == 'object_uploaded' && op.phase == 'complete_pending') {
      phase = 'complete_pending';
    }
    if (phase == op.phase) return;
    op.phase = phase;
    op.canDelete = phase == 'confirmed';
    if (phase == 'processing' || op.finished) {
      op.payload['sync_step'] = phase == 'processing' ? 'verify' : 'settled';
      _clearRetry(op);
    }
    await store.save(op, lease: lease);
    check();
  }

  void _verifyRemote(PendingUpload op, Json data, {bool examRequired = true}) {
    if (data['upload_id'] != op.uploadId ||
        (examRequired && data['clinical_test_id'] != op.examId)) {
      throw const ApiFailure(502, 'UPLOAD_RESPONSE_MISMATCH');
    }
  }

  Json _descriptor(Json data) {
    final value = data['upload'];
    if (value is! Map ||
        value['signed_url'] is! String ||
        value['required_headers'] is! Map ||
        value['expires_at'] is! String ||
        DateTime.tryParse(value['expires_at'] as String) == null) {
      throw const ApiFailure(502, 'INVALID_UPLOAD_DESCRIPTOR');
    }
    return Map<String, dynamic>.from(value);
  }

  bool _expired(Json descriptor) =>
      !DateTime.parse(descriptor['expires_at'] as String).isAfter(clock());

  Future<Json> _renew(
    PendingUpload op,
    Session session,
    void Function() check,
    String lease,
    UploadCancellation? cancellation,
  ) async {
    // Replay an ambiguous refresh once with its original key. If that signed
    // URL has expired, persist a new key before requesting the next URL.
    for (var i = 0; i < 2; i++) {
      final key = (op.payload['refresh_key'] as String?) ?? const Uuid().v4();
      op.payload['refresh_key'] = key;
      op.payload['sync_step'] = 'renew';
      await store.save(op, lease: lease);
      check();
      final result = await api.json(
        'POST',
        '/api/v1/clinical-tests/uploads/${Uri.encodeComponent(op.uploadId!)}/refresh-url',
        session: session,
        body: {'client_upload_id': op.id, 'sha256': op.initiate['sha256']},
        key: key,
        cancellation: cancellation,
      );
      check();
      _verifyRemote(op, result, examRequired: false);
      final descriptor = _descriptor(result);
      if (!_expired(descriptor)) return descriptor;
      op.payload.remove('refresh_key');
    }
    throw const ApiFailure(503, 'UPLOAD_URL_EXPIRED');
  }

  void _clearRetry(PendingUpload op) {
    op.error = null;
    op.payload.remove('retry_at');
    op.payload.remove('retry_failures');
  }

  bool _retryable(ApiFailure e) =>
      e.status == 0 ||
      e.status == 429 ||
      e.status >= 500 ||
      e.code == 'RETRYABLE_CONFLICT' ||
      (e.storage && e.status == 403 && e.code == 'STORAGE_UPLOAD_FAILED');

  Future<void> resume(
    PendingUpload op,
    Session session,
    void Function() check, {
    UploadCancellation? cancellation,
  }) async {
    // Invocation is the explicit grant for this operation and this attempt;
    // never persist a grant that a future process could use to send.
    final identity = (op.id, op.scope, op.file, op.initiateKey, op.completeKey);
    final payload = op.initiate.toString();
    void authorized() {
      _requireWriter(op, session, check);
      cancellation?.check();
      if (identity !=
              (op.id, op.scope, op.file, op.initiateKey, op.completeKey) ||
          payload != op.initiate.toString()) {
        throw const ApiFailure(409, 'LOCAL_OPERATION_CHANGED');
      }
    }

    authorized();
    if (op.phase == 'conflict') {
      throw const ApiFailure(409, 'RECONCILIATION_REQUIRED');
    }
    if (op.finished || op.phase == 'processing') return;
    final lease = const Uuid().v4();
    if (!await store.claim(op.scope, op.id, lease: lease)) return;
    var attempted = false;
    try {
      await _requireCurrent(op);
      authorized();
      if (clock().millisecondsSinceEpoch < op.retryAt) {
        throw const ApiFailure(429, 'RETRY_AFTER');
      }
      await _inspect(op, authorized, lease);
      authorized();
      if (op.fileIssue != null) return;
      op.attempts++;
      op.version++;
      op.error = null;
      op.payload.remove('retry_at');
      op.payload['sync_step'] = op.uploadId == null ? 'initiate' : 'status';
      await store.save(op, lease: lease);
      attempted = true;
      authorized();
      Json? descriptor;
      if (op.uploadId == null) {
        final init = await api.json(
          'POST',
          '/api/v1/clinical-tests/uploads/initiate',
          session: session,
          body: op.initiate,
          key: op.initiateKey,
          cancellation: cancellation,
        );
        authorized();
        final uploadId = init['upload_id'], examId = init['clinical_test_id'];
        if (uploadId is! String ||
            uploadId.isEmpty ||
            examId is! String ||
            examId.isEmpty) {
          throw const ApiFailure(502, 'INVALID_UPLOAD_IDENTIFIERS');
        }
        op.uploadId = uploadId;
        op.examId = examId;
        op.phase = 'bytes_pending';
        op.payload['sync_step'] = 'status';
        await store.save(op, lease: lease);
        descriptor = _descriptor(init);
      }
      await _reconcile(
        op,
        session,
        authorized,
        lease,
        cancellation: cancellation,
      );
      authorized();
      if (op.finished || op.phase == 'processing') return;
      if (op.phase != 'complete_pending' && op.phase != 'object_uploaded') {
        if (descriptor == null || _expired(descriptor)) {
          descriptor = await _renew(
            op,
            session,
            authorized,
            lease,
            cancellation,
          );
        }
        final bytes = await vault.verified(vault.resolve(op.file), op);
        authorized();
        if (bytes == null) {
          op.payload['file_issue'] = 'corrupt';
          await store.save(op, lease: lease);
          return;
        }
        // Persist uncertainty before the request. Only a successful response
        // can advance the PUT checkpoint; retry uses immutable object creation.
        op.phase = 'bytes_pending';
        op.payload['sync_step'] = 'put';
        op.payload.remove('refresh_key');
        await store.save(op, lease: lease);
        authorized();
        await api.put(descriptor, bytes, cancellation: cancellation);
        authorized();
      }
      op.phase = 'complete_pending';
      op.payload['sync_step'] = 'complete';
      await store.save(op, lease: lease);
      authorized();
      final result = await api.json(
        'POST',
        '/api/v1/clinical-tests/uploads/${Uri.encodeComponent(op.uploadId!)}/complete',
        session: session,
        body: op.complete,
        key: op.completeKey,
        cancellation: cancellation,
      );
      authorized();
      _verifyRemote(op, result);
      if (!['processing', 'ready_for_review'].contains(result['status'])) {
        throw const ApiFailure(502, 'INVALID_COMPLETE_RESPONSE');
      }
      op.phase = 'processing';
      op.payload['sync_step'] = 'verify';
      _clearRetry(op);
      await store.save(op, lease: lease);
      authorized();
    } on ApiFailure catch (e) {
      if (!attempted || e.code == 'SESSION_CHANGED') rethrow;
      check(); // Do not write a response from a stale session.
      op.error = e.code;
      if (e.code != 'UPLOAD_PAUSED' && !e.denied) {
        if (_retryable(e)) {
          final failures = ((op.payload['retry_failures'] as int? ?? 0) + 1)
              .clamp(1, 8);
          final delay = min(300, (1 << failures) + jitter(1 << (failures - 1)));
          op.payload['retry_failures'] = failures;
          op.payload['retry_at'] = clock()
              .add(Duration(seconds: max(delay, e.retryAfter)))
              .millisecondsSinceEpoch;
        } else {
          op.phase = e.conflict ? 'conflict' : 'failed';
        }
      }
      await store.save(op, lease: lease);
      rethrow;
    } on FileSystemException {
      check();
      op.payload['file_issue'] = 'unreadable';
      await store.save(op, lease: lease);
    } finally {
      await store.release(op.scope, op.id, lease: lease);
    }
  }
}
