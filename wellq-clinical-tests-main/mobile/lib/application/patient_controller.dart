import 'dart:io';
import 'dart:async';

import 'package:flutter/foundation.dart';

import '../domain/models.dart';
import '../data/api.dart';
import '../data/local_store.dart';
import '../data/uploads.dart';
import 'package:crypto/crypto.dart';
import '../domain/sample_policy.dart';

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
  bool busy = false, online = false;
  int? authorizationFailure;
  Timer? _expiry;
  String get connectionLabel {
    if (authorizationFailure == 401 || session?.expired == true) {
      return 'Sesión expirada';
    }
    if (authorizationFailure == 403) return 'Acceso no autorizado';
    if (busy) return 'Verificando';
    return online ? 'Conectado' : 'Sin conexión verificada';
  }

  void _watchExpiry() {
    _expiry?.cancel();
    final s = session;
    if (s == null) return;
    _expiry = Timer(s.expires.difference(DateTime.now()), () async {
      authorizationFailure = 401;
      message = const ApiFailure(401, 'SESSION_EXPIRED').message;
      await logout(keepMessage: true, preservePending: true);
    });
  }

  Future<void> failure(ApiFailure e) async {
    message = e.message;
    if (e.status == 0 || e.status >= 500) online = false;
    if (e.denied) {
      authorizationFailure = e.status;
      await logout(keepMessage: true, preservePending: true);
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
      await failure(e);
    } catch (_) {
      message =
          'Operación interrumpida. Consulta el estado antes de reintentar.';
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> connect() => _run(() async {
    final ticket = _epoch;
    final fresh = await identity.connect();
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
    online = false;
    authorizationFailure = null;
    _watchExpiry();
    final check = guard();
    await store.recover();
    check();
    exams = await store.cached(fresh.scope);
    check();
    operations = await store.pending(fresh.scope);
    check();
    final page = ExamPage.fromJson(
      await api.json('GET', '/api/v1/clinical-tests', session: fresh),
    );
    check();
    exams = page.items;
    online = true;
    cursor = page.cursor;
    await store.cache(fresh.scope, exams);
    check();
  });
  Future<void> refresh({bool more = false}) => _run(() async {
    final s = session;
    if (s == null) return;
    final check = guard();
    await api.ready();
    check();
    final page = ExamPage.fromJson(
      await api.json(
        'GET',
        '/api/v1/clinical-tests${more && cursor != null ? '?cursor=${Uri.encodeQueryComponent(cursor!)}' : ''}',
        session: s,
      ),
    );
    check();
    exams = more ? [...exams, ...page.items] : page.items;
    cursor = page.cursor;
    online = true;
    await store.cache(s.scope, exams);
    check();
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
    await uploads.resume(op, fresh, check);
    check();
    operations = await store.pending(fresh.scope);
    check();
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
    for (final op in operations) {
      await uploads.reconcile(op, fresh, check);
      check();
    }
    operations = await store.pending(fresh.scope);
    check();
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
      await failure(e);
      rethrow;
    }
  }

  Future<List<int>?> document(String examId) async {
    final s = session;
    if (s == null) return null;
    final check = guard();
    check();
    for (final op in await store.pending(s.scope)) {
      if (op.examId != examId) continue;
      final file = uploads.vault.resolve(op.file);
      if (!await file.exists() || await file.length() > 20 * 1024 * 1024) {
        return null;
      }
      final bytes = await file.readAsBytes();
      check();
      if (sha256.convert(bytes).toString() != syntheticPdfSha256) return null;
      return bytes;
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
      await failure(e);
      rethrow;
    }
  }

  Future<void> logout({
    bool keepMessage = false,
    bool preservePending = false,
  }) async {
    final old = session;
    _expiry?.cancel();
    _epoch++;
    session = null;
    identity.signOut();
    exams = [];
    operations = [];
    cursor = null;
    online = false;
    if (!keepMessage) message = null;
    notifyListeners();
    if (old != null) {
      if (preservePending) {
        await store.clearCache(old.scope);
      } else {
        await store.clearScope(old.scope);
      }
    }
  }

  @override
  void dispose() {
    _expiry?.cancel();
    _epoch++;
    api.close();
    super.dispose();
  }
}
