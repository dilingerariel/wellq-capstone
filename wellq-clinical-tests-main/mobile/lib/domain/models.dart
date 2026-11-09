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
  String get message => code == 'EXTRACTION_NOT_READY'
      ? 'El documento sigue preparando la propuesta. Consulta nuevamente.'
      : switch (status) {
          0 => 'Sin conexión verificada. Tu operación sigue pendiente.',
          401 => 'La sesión venció. Vuelve a conectar el perfil sintético.',
          403 =>
            storage
                ? 'Autorización del archivo vencida. Reintenta explícitamente.'
                : 'No tienes permiso para esta operación.',
          409 ||
          428 => 'Conflicto: consulta el estado actual antes de continuar.',
          422 => 'Revisa los campos y el consentimiento del documento.',
          429 => 'Límite temporal. Espera antes de reintentar.',
          502 || 503 => 'Servicio no disponible. No se ha confirmado éxito.',
          _ => 'No se pudo completar la operación ($status).',
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
      permissions = Set<String>.from(j['permissions'] as List),
      expires = DateTime.fromMillisecondsSinceEpoch(
        (j['expiresAt'] as int) * 1000,
      ) {
    if (role != 'patient' ||
        !patient.startsWith('synthetic-local-patient-') ||
        !tenant.startsWith('synthetic-local-') ||
        !permissions.contains('clinical:read') ||
        expired) {
      throw const ApiFailure(403, 'SYNTHETIC_PATIENT_REQUIRED');
    }
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
  String get initiateKey => payload['initiate_key'] as String;
  String get completeKey => payload['complete_key'] as String;
  Json get initiate => Map<String, dynamic>.from(payload['initiate'] as Map);
  Json get complete => {
    for (final k in ['client_upload_id', 'sha256', 'size_bytes'])
      k: initiate[k],
  };
  bool get finished => ['confirmed', 'rejected', 'failed'].contains(phase);
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

String phaseLabel(String phase) => uploadLabel(phase);
