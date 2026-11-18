import 'dart:io';
import 'dart:async';

import 'package:flutter/foundation.dart';

import '../domain/models.dart';
import '../data/api.dart';
import '../data/local_store.dart';
import '../data/uploads.dart';
import '../domain/pdf_policy.dart';
import '../domain/exam_query.dart';

class PatientController extends ChangeNotifier {
  PatientController(this.api, this.identity, this.store, Directory directory)
    : uploads = UploadRepository(api, store, FileVault(directory));
  final ApiClient api;
  final IdentityAdapter identity;
  final LocalStore store;
  final UploadRepository uploads;
  Session? session;
  List<Exam> exams = [];
  List<PendingUpload> operations = [];
  String? cursor, message;
  ExamFilters filters = const ExamFilters();
  bool busy = false, online = false;
  int? authorizationFailure;
  Timer? _expiry;
  bool _foreground = true;
  UploadCancellation? _activeUpload;
  String? sendingId;
  int unreferencedFiles = 0;

  void setForeground(bool value) {
    _foreground = value;
    if (!value) pauseUpload();
  }

  void pauseUpload() => _activeUpload?.cancel();
  String get connectionLabel {
    if (authorizationFailure == 401 || session?.expired == true) {
      return 'sessionExpired';
    }
    if (authorizationFailure == 403) return 'accessUnauthorized';
    if (busy) return 'verifying';
    return online ? 'connected' : 'connectionUnverified';
  }

  void _watchExpiry() {
    _expiry?.cancel();
    final s = session;
    if (s == null) return;
    _expiry = Timer(s.expires.difference(DateTime.now()), () async {
      authorizationFailure = 401;
      message = const ApiFailure(401, 'SESSION_EXPIRED').message;
      await logout(keepMessage: true);
    });
  }

  Future<void> failure(ApiFailure e) async {
    message = e.message;
    if ((e.status == 0 && e.code != 'UPLOAD_PAUSED') || e.status >= 500) {
      online = false;
    }
    if (e.denied) {
      authorizationFailure = e.status;
      await logout(keepMessage: true);
    }
    notifyListeners();
  }

  int _epoch = 0;
  int get generation => _epoch;
  void Function() guard() {
    final captured = _epoch;
    return () {
      if (captured != _epoch || session == null || session!.expired) {
        throw const ApiFailure(401, 'SESSION_CHANGED');
      }
    };
  }

  Future<void> _run(Future<void> Function() action) async {
    if (busy) return;
    busy = true;
    notifyListeners();
    try {
      await action();
      message = null;
    } on ApiFailure catch (e) {
      if (e.code != 'SESSION_CHANGED') await failure(e);
    } catch (_) {
      message = 'operationInterrupted';
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> connect() => _run(() async {
    final ticket = _epoch;
    final fresh = await identity.connect();
    await _acceptSession(fresh, ticket);
  });

  Future<void> login(String email, String password) => _run(() async {
    final adapter = identity;
    if (adapter is! PatientAccountIdentityAdapter) {
      throw const ApiFailure(403, 'ACCOUNT_AUTH_UNAVAILABLE');
    }
    final ticket = _epoch;
    final fresh = await adapter.login(email, password);
    await _acceptSession(fresh, ticket);
  });

  Future<void> registerPatient({
    required String displayName,
    required String email,
    required String password,
    required String clinicId,
    required String clinicianId,
  }) => _run(() async {
    final adapter = identity;
    if (adapter is! PatientAccountIdentityAdapter) {
      throw const ApiFailure(403, 'ACCOUNT_AUTH_UNAVAILABLE');
    }
    final ticket = _epoch;
    final fresh = await adapter.registerPatient(
      displayName: displayName,
      email: email,
      password: password,
      clinicId: clinicId,
      clinicianId: clinicianId,
    );
    await _acceptSession(fresh, ticket);
  });

  Future<void> _acceptSession(Session fresh, int ticket) async {
    if (ticket != _epoch) return;
    final old = session;
    if (old != null &&
        (old.scope != fresh.scope ||
            !setEquals(old.permissions, fresh.permissions))) {
      await store.clearCache(old.scope);
      if (ticket != _epoch) return;
      exams = [];
      operations = [];
      _epoch++;
    }
    session = fresh;
    filters = const ExamFilters();
    cursor = null;
    online = false;
    authorizationFailure = null;
    _watchExpiry();
    final check = guard();
    unreferencedFiles = await uploads.recoverFiles(fresh, check);
    check();
    exams = await store.cached(fresh.scope);
    check();
    operations = await store.pending(fresh.scope);
    check();
    await _readExams(fresh, check);
  }
  Future<void> _readExams(
    Session s,
    void Function() check, {
    bool more = false,
    ExamFilters? filtering,
  }) async {
    final selected = filtering ?? filters;
    final next = more ? cursor : null;
    if (more && next == null) return;
    try {
      final page = ExamPage.fromJson(
        await api.json('GET', selected.path(cursor: next), session: s),
      );
      check();
      if (next != null && page.cursor == next) {
        throw const ApiFailure(502, 'REPEATED_CURSOR');
      }
      exams = {
        for (final exam in [...(more ? exams : <Exam>[]), ...page.items])
          exam.id: exam,
      }.values.toList();
      filters = selected;
      cursor = page.cursor;
      online = true;
      // The existing cache has no filter key. Never label a filtered snapshot as all documents.
      if (selected.isEmpty) await store.cache(s.scope, exams);
      check();
    } on ApiFailure {
      check(); // A late response cannot invalidate a different, newer session.
      rethrow;
    }
  }

  Future<void> refresh({bool more = false, ExamFilters? filtering}) =>
      _run(() async {
        final s = session;
        if (s == null) return;
        final check = guard();
        try {
          await api.ready();
        } on ApiFailure {
          check();
          rethrow;
        }
        check();
        await _readExams(s, check, more: more, filtering: filtering);
        operations = await store.pending(s.scope);
        check();
      });
  Future<void> queue(List<int> bytes, String title, String date) =>
      _run(() async {
        final s = session;
        if (s == null) return;
        final check = guard();
        await uploads.queue(s, bytes, title, date, check);
        check();
        operations = await store.pending(s.scope);
        check();
      });
  Future<void> resume(PendingUpload op) => _run(() async {
    final before = session;
    if (before == null || !_foreground) return;
    final check = guard();
    check();
    if (before.scope != op.scope ||
        !before.permissions.contains('clinical:write')) {
      throw const ApiFailure(403, 'UPLOAD_PERMISSION');
    }
    if (op.retryAt > DateTime.now().millisecondsSinceEpoch) {
      throw const ApiFailure(429, 'RETRY_AFTER');
    }
    final cancellation = UploadCancellation();
    _activeUpload = cancellation;
    sendingId = op.id;
    notifyListeners();
    try {
      final fresh = await identity.connect();
      check();
      cancellation.check();
      if (fresh.scope != before.scope ||
          !setEquals(fresh.permissions, before.permissions)) {
        throw const ApiFailure(403, 'IDENTITY_CHANGED');
      }
      session = fresh;
      _watchExpiry();
      online = true;
      await uploads.resume(op, fresh, check, cancellation: cancellation);
    } finally {
      cancellation.cancel();
      _activeUpload = null;
      sendingId = null;
      check();
      final updated = await store.pending(before.scope);
      check();
      operations = updated;
    }
  });
  // Explicit reconnect: reads only. Never replays clinical confirmations.
  Future<void> reconcile() => _run(() async {
    final before = session;
    if (before == null) return;
    final check = guard();
    final fresh = await identity.connect();
    check();
    if (fresh.scope != before.scope ||
        !setEquals(fresh.permissions, before.permissions)) {
      throw const ApiFailure(403, 'IDENTITY_CHANGED');
    }
    session = fresh;
    _watchExpiry();
    online = true;
    unreferencedFiles = await uploads.recoverFiles(fresh, check);
    check();
    for (final op in await store.pending(fresh.scope)) {
      await uploads.reconcile(op, fresh, check);
      check();
    }
    operations = await store.pending(fresh.scope);
    check();
    await _readExams(fresh, check);
  });
  Future<Json> extraction(String id) async {
    final s = session;
    if (s == null) throw const ApiFailure(401, 'NO_SESSION');
    final check = guard();
    try {
      final data = await api.json(
        'GET',
        '/api/v1/clinical-tests/${Uri.encodeComponent(id)}/extraction',
        session: s,
      );
      check();
      return data;
    } on ApiFailure catch (e) {
      check();
      await failure(e);
      rethrow;
    }
  }

  Future<List<int>?> document(String examId) async =>
      (await documentWithIntegrity(examId))?.bytes;

  Future<VerifiedPdfDocument?> documentWithIntegrity(String examId) async {
    final s = session;
    if (s == null) return null;
    final check = guard();
    check();
    for (final op in await store.pending(s.scope)) {
      if (op.examId != examId) continue;
      final file = uploads.vault.resolve(op.file);
      final bytes = await uploads.vault.verified(file, op);
      check();
      if (bytes == null) return null;
      return VerifiedPdfDocument(bytes, op.initiate['sha256'] as String);
    }
    return null;
  }

  Future<Json> detail(String id) async {
    final s = session;
    if (s == null) throw const ApiFailure(401, 'NO_SESSION');
    final check = guard();
    try {
      final data = await api.json(
        'GET',
        '/api/v1/clinical-tests/${Uri.encodeComponent(id)}',
        session: s,
      );
      check();
      return data;
    } on ApiFailure catch (e) {
      check();
      await failure(e);
      rethrow;
    }
  }

  Future<Json> confirm(String id, Json body, String key) async {
    final s = session;
    if (s == null || !s.permissions.contains('extractions:confirm')) {
      throw const ApiFailure(403, 'CONFIRM_PERMISSION');
    }
    final check = guard();
    try {
      final result = await api.json(
        'PATCH',
        '/api/v1/clinical-tests/${Uri.encodeComponent(id)}/extraction',
        session: s,
        body: body,
        key: key,
      );
      check();
      return result;
    } on ApiFailure catch (e) {
      check();
      await failure(e);
      rethrow;
    }
  }

  Future<void> logout({bool keepMessage = false}) async {
    final old = session;
    _expiry?.cancel();
    pauseUpload();
    _epoch++;
    session = null;
    identity.signOut();
    exams = [];
    operations = [];
    unreferencedFiles = 0;
    cursor = null;
    filters = const ExamFilters();
    online = false;
    if (!keepMessage) message = null;
    notifyListeners();
    // Ending access is independent of destruction. Keep all private files and
    // operations locked to the verified owner until a retention policy exists.
    if (old != null) await store.clearCache(old.scope);
  }

  @override
  void dispose() {
    _expiry?.cancel();
    pauseUpload();
    _epoch++;
    api.close();
    super.dispose();
  }
}
