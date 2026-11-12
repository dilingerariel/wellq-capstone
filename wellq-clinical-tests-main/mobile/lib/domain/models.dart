import 'dart:convert';
import 'patient_labels.dart';

typedef Json = Map<String, dynamic>;

class ApiFailure implements Exception {
  const ApiFailure(
    this.status,
    this.code, {
    this.storage = false,
    this.retryAfter = 0,
  });
  final int status, retryAfter;
  final String code;
  final bool storage;
  bool get denied => !storage && (status == 401 || status == 403);
  bool get conflict => status == 409 || status == 428;
  String get message => code == 'UPLOAD_PAUSED'
      ? 'queuePaused'
      : code == 'EXTRACTION_NOT_READY'
      ? 'errorExtractionNotReady'
      : switch (status) {
          0 => 'errorOffline',
          401 => 'errorSession',
          403 => storage ? 'errorStorageAuth' : 'errorDenied',
          404 => 'errorNotFound',
          409 || 428 => 'errorConflict',
          422 => 'errorValidation',
          429 => 'errorRateLimit',
          502 || 503 => 'errorService',
          _ => 'errorUnknown',
        };
  @override
  String toString() => 'ApiFailure($status, $code)';
}

class Session {
  Session.fromJson(Json j)
    : token = j['accessToken'] as String,
      patient = j['resourceId'] as String,
      tenant = j['tenantId'] as String,
      role = j['role'] as String,
      permissions = Set<String>.unmodifiable(
        (j['permissions'] as List).cast<String>(),
      ),
      expires = DateTime.fromMillisecondsSinceEpoch(
        (j['expiresAt'] as int) * 1000,
      ) {
    if (role != 'patient' ||
        !patient.startsWith('synthetic-local-patient-') ||
        !tenant.startsWith('synthetic-local-') ||
        !permissions.contains('clinical:read')) {
      throw const ApiFailure(403, 'SYNTHETIC_PATIENT_REQUIRED');
    }
    if (expired) throw const ApiFailure(401, 'SESSION_EXPIRED');
  }
  final String token, patient, tenant, role;
  final Set<String> permissions;
  final DateTime expires;
  bool get expired => !expires.isAfter(DateTime.now());
  String get scope => '$tenant/$patient';
  @override
  String toString() => 'Session(synthetic patient; token redacted)';
}

class Exam {
  const Exam(
    this.id,
    this.title,
    this.date,
    this.status, {
    this.testType,
    this.reviewStatus,
  });
  factory Exam.fromJson(Json j) => Exam(
    j['clinical_test_id'] as String,
    j['title'] as String,
    j['test_date'] as String,
    j['status'] as String,
    testType: j['test_type'] as String?,
    reviewStatus: (j['review'] as Map?)?['status'] as String?,
  );
  final String id, title, date, status;
  final String? testType, reviewStatus;
  Json toJson() => {
    'clinical_test_id': id,
    'title': title,
    'test_date': date,
    'status': status,
    if (testType != null) 'test_type': testType,
    if (reviewStatus != null) 'review': {'status': reviewStatus},
  };
}

class ExamPage {
  ExamPage.fromJson(Json j)
    : items = (j['items'] as List)
          .map((x) => Exam.fromJson(Map<String, dynamic>.from(x as Map)))
          .toList(),
      cursor = j['next_cursor'] as String?;
  final List<Exam> items;
  final String? cursor;
}

class PendingUpload {
  PendingUpload(
    this.id,
    this.scope,
    this.payload, {
    this.phase = 'queued',
    this.attempts = 0,
    this.version = 1,
    this.error,
    this.uploadId,
    this.examId,
    this.canDelete = false,
  });
  final String id, scope;
  final Json payload;
  String phase;
  int attempts, version;
  String? error, uploadId, examId;
  bool canDelete;
  String get title => payload['title'] as String;
  String get file => payload['file'] as String;
  String? get fileIssue => payload['file_issue'] as String?;
  int get retryAt => payload['retry_at'] as int? ?? 0;
  String get initiateKey => payload['initiate_key'] as String;
  String get completeKey => payload['complete_key'] as String;
  Json get initiate => Map<String, dynamic>.from(payload['initiate'] as Map);
  Json get complete => {
    for (final k in ['client_upload_id', 'sha256', 'size_bytes'])
      k: initiate[k],
  };
  bool get finished => ['confirmed', 'rejected', 'failed'].contains(phase);
  bool get canResume =>
      !finished &&
      fileIssue == null &&
      !['conflict', 'processing', 'object_uploaded'].contains(phase);
  String serialize() => jsonEncode({
    'id': id,
    'scope': scope,
    'payload': payload,
    'phase': phase,
    'attempts': attempts,
    'version': version,
    'error': error,
    'upload_id': uploadId,
    'exam_id': examId,
    'can_delete': canDelete,
  });
  factory PendingUpload.deserialize(String text) {
    final j = jsonDecode(text) as Json;
    return PendingUpload(
      j['id'] as String,
      j['scope'] as String,
      Map<String, dynamic>.from(j['payload'] as Map),
      phase: j['phase'] as String,
      attempts: j['attempts'] as int,
      version: j['version'] as int,
      error: j['error'] as String?,
      uploadId: j['upload_id'] as String?,
      examId: j['exam_id'] as String?,
      canDelete: j['can_delete'] as bool,
    );
  }
}

// A local "confirmed" phase means verified reception, not patient confirmation.
// Accept only actual UploadStatus values; commit nothing for an incoherent reply.
String verifiedUploadPhase(Json response) => switch (response['status']) {
  'ready_for_review' when response['local_file_can_be_deleted'] == true =>
    'confirmed',
  'ready_for_review' => throw const ApiFailure(
    502,
    'UNVERIFIED_READY_RESPONSE',
  ),
  'initiated' => 'bytes_pending',
  'object_uploaded' ||
  'processing' ||
  'rejected' ||
  'failed' => response['status'] as String,
  _ => throw const ApiFailure(502, 'UNKNOWN_UPLOAD_STATUS'),
};

String phaseLabel(String phase) => uploadLabel(phase);
