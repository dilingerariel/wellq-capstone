import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:uuid/uuid.dart';

import '../domain/models.dart';
import '../domain/sample_policy.dart';
import 'api.dart';
import 'local_store.dart';

class FileVault {
  FileVault(this.root);
  final Directory root;
  File resolve(String name) {
    if (!RegExp(r'^uploads/[a-f0-9-]{36}\.pdf$').hasMatch(name)) {
      throw StateError('Invalid private reference');
    }
    return File('${root.path}/$name');
  }

  Future<String> copy(String id, List<int> bytes) async {
    if (bytes.length > 20 * 1024 * 1024 ||
        sha256.convert(bytes).toString() != syntheticPdfSha256) {
      throw const ApiFailure(422, 'ONLY_BUNDLED_SYNTHETIC_PDF');
    }
    final name = 'uploads/$id.pdf';
    final file = resolve(name);
    await file.parent.create(recursive: true);
    await file.writeAsBytes(bytes, flush: true);
    return name;
  }
}

class UploadRepository {
  UploadRepository(this.api, this.store, this.vault);
  final ApiClient api;
  final LocalStore store;
  final FileVault vault;
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
    check();
    final path = await vault.copy(id, bytes);
    check();
    final op = PendingUpload(id, session.scope, {
      'title': title.trim(),
      'file': path,
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
    check();
    return op;
  }

  Future<void> reconcile(
    PendingUpload op,
    Session session,
    void Function() check,
  ) async {
    if (op.scope != session.scope) throw const ApiFailure(403, 'OWNER_CHANGED');
    if (op.uploadId == null) return;
    final s = await api.json(
      'GET',
      '/api/v1/clinical-tests/uploads/${Uri.encodeComponent(op.uploadId!)}/status',
      session: session,
    );
    check();
    op.phase = s['status'] == 'ready_for_review'
        ? 'confirmed'
        : s['status'] as String;
    if (op.phase == 'initiated') op.phase = 'bytes_pending';
    op.canDelete = s['local_file_can_be_deleted'] == true;
    if (op.phase == 'confirmed' && !op.canDelete) {
      throw const ApiFailure(502, 'UNVERIFIED_READY_RESPONSE');
    }
    await store.save(op);
    check();
  }

  Future<void> resume(
    PendingUpload op,
    Session session,
    void Function() check,
  ) async {
    if (op.scope != session.scope) throw const ApiFailure(403, 'OWNER_CHANGED');
    if (op.phase == 'conflict') {
      throw const ApiFailure(409, 'RECONCILIATION_REQUIRED');
    }
    final due = op.payload['retry_at'] as int? ?? 0;
    if (DateTime.now().millisecondsSinceEpoch < due) {
      throw const ApiFailure(429, 'RETRY_AFTER');
    }
    if (op.finished || !await store.claim(op.scope, op.id)) return;
    try {
      check();
      op.attempts++;
      op.version++;
      op.error = null;
      await store.save(op);
      check();
      Json? descriptor;
      if (op.uploadId == null) {
        final init = await api.json(
          'POST',
          '/api/v1/clinical-tests/uploads/initiate',
          session: session,
          body: op.initiate,
          key: op.initiateKey,
        );
        check();
        op.uploadId = init['upload_id'] as String;
        op.examId = init['clinical_test_id'] as String;
        op.phase = 'bytes_pending';
        descriptor = Map<String, dynamic>.from(init['upload'] as Map);
        await store.save(op);
        check();
      }
      // Reconcile before any retry; a completed request is never sent twice.
      final phaseBefore = op.phase;
      await reconcile(op, session, check);
      check();
      if (op.finished || op.phase == 'processing') return;
      if (phaseBefore == 'complete_pending') op.phase = 'complete_pending';
      if (op.phase != 'complete_pending') {
        final bytes = await vault.resolve(op.file).readAsBytes();
        check();
        if (sha256.convert(bytes).toString() != op.initiate['sha256']) {
          throw const ApiFailure(409, 'LOCAL_FILE_CHANGED');
        }
        if (descriptor == null) {
          final refreshed = await api.json(
            'POST',
            '/api/v1/clinical-tests/uploads/${op.uploadId}/refresh-url',
            session: session,
            body: {'client_upload_id': op.id, 'sha256': op.initiate['sha256']},
            key: const Uuid().v4(),
          );
          check();
          descriptor = Map<String, dynamic>.from(refreshed['upload'] as Map);
        }
        op.phase = 'bytes_pending';
        await store.save(op);
        check();
        await api.put(descriptor, bytes);
        check();
        op.phase = 'complete_pending';
        await store.save(op);
        check();
      }
      await api.json(
        'POST',
        '/api/v1/clinical-tests/uploads/${op.uploadId}/complete',
        session: session,
        body: op.complete,
        key: op.completeKey,
      );
      check();
      op.phase = 'processing';
      await store.save(op);
      check();
    } on ApiFailure catch (e) {
      check();
      op.error = e.code;
      if (e.conflict) op.phase = 'conflict';
      if (e.retryAfter > 0) {
        op.payload['retry_at'] = DateTime.now()
            .add(Duration(seconds: e.retryAfter.clamp(1, 3600)))
            .millisecondsSinceEpoch;
      }
      await store.save(op);
      rethrow;
    } finally {
      await store.release(op.scope, op.id);
    }
  }
}
