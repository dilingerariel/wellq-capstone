import 'dart:convert';

import 'package:drift/drift.dart';

import '../domain/models.dart';

// Versioned SQL through Drift, deliberately no token/URL/password column.
class LocalStore extends GeneratedDatabase {
  LocalStore(super.executor);
  @override
  int get schemaVersion => 2;
  @override
  Iterable<TableInfo<Table, Object?>> get allTables => const [];
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => const [];
  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (_) async {
      await customStatement(
        'CREATE TABLE operations (id TEXT PRIMARY KEY, scope TEXT NOT NULL, data TEXT NOT NULL, running INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL, lease_owner TEXT)',
      );
      await customStatement(
        'CREATE INDEX operations_scope ON operations(scope, created_at)',
      );
      await customStatement(
        'CREATE TABLE exam_cache (scope TEXT PRIMARY KEY, data TEXT NOT NULL)',
      );
    },
    onUpgrade: (_, from, to) async {
      if (from != 1 || to != 2) {
        throw StateError('Unreviewed migration $from -> $to');
      }
      await transaction(() async {
        await customStatement(
          'ALTER TABLE operations ADD COLUMN lease_owner TEXT',
        );
      });
    },
  );
  void check(String scope) {
    final localScope = scope.startsWith('synthetic-local-') &&
        scope.contains('/synthetic-local-patient-');
    final demoScope = scope == 'clinica_alemana/paciente_ariel_demo';
    final registeredPatientScope = RegExp(
      r'^(clinica_alemana|clinica_santa_maria)/[a-f0-9]{32}$',
    ).hasMatch(scope);
    if (!localScope && !demoScope && !registeredPatientScope) {
      throw StateError('Synthetic scope required');
    }
  }

  Future<void> enqueue(PendingUpload op) async {
    check(op.scope);
    await customInsert(
      'INSERT INTO operations(id,scope,data,created_at) VALUES(?,?,?,?)',
      variables: [
        Variable(op.id),
        Variable(op.scope),
        Variable(op.serialize()),
        Variable(DateTime.now().millisecondsSinceEpoch),
      ],
    );
  }

  Future<void> save(PendingUpload op, {String? lease}) async {
    check(op.scope);
    final changed = await customUpdate(
      'UPDATE operations SET data=? WHERE id=? AND scope=? AND '
      '${lease == null ? 'running=0' : 'running=1 AND lease_owner=?'}',
      variables: [
        Variable(op.serialize()),
        Variable(op.id),
        Variable(op.scope),
        if (lease != null) Variable(lease),
      ],
    );
    if (changed != 1) throw const ApiFailure(409, 'LOCAL_LEASE_LOST');
  }

  Future<PendingUpload?> operation(String scope, String id) async {
    check(scope);
    final row = await customSelect(
      'SELECT data FROM operations WHERE scope=? AND id=?',
      variables: [Variable(scope), Variable(id)],
    ).getSingleOrNull();
    return row == null
        ? null
        : PendingUpload.deserialize(row.read<String>('data'));
  }

  // Used only to detect unreferenced files; never expose IDs from other scopes.
  Future<Set<String>> referencedIds() async => (await customSelect(
    'SELECT id FROM operations',
  ).get()).map((row) => row.read<String>('id')).toSet();

  Future<List<PendingUpload>> pending(String scope) async {
    check(scope);
    final rows = await customSelect(
      'SELECT data FROM operations WHERE scope=? ORDER BY created_at DESC',
      variables: [Variable(scope)],
    ).get();
    return rows
        .map((x) => PendingUpload.deserialize(x.read<String>('data')))
        .toList();
  }

  Future<bool> claim(
    String scope,
    String id, {
    String lease = 'legacy',
  }) async =>
      (await customUpdate(
        'UPDATE operations SET running=1, lease_owner=? WHERE id=? AND scope=? AND running=0',
        variables: [Variable(lease), Variable(id), Variable(scope)],
      )) ==
      1;
  Future<void> release(
    String scope,
    String id, {
    String lease = 'legacy',
  }) async {
    await customUpdate(
      'UPDATE operations SET running=0, lease_owner=NULL WHERE id=? AND scope=? AND lease_owner=?',
      variables: [Variable(id), Variable(scope), Variable(lease)],
    );
  }

  // Call once at process startup, under the exclusive vault process lock.
  Future<void> recover() async {
    await customUpdate(
      'UPDATE operations SET running=0, lease_owner=NULL WHERE running<>0',
    );
  }

  Future<void> cache(String scope, List<Exam> exams) async {
    check(scope);
    await customInsert(
      'INSERT OR REPLACE INTO exam_cache(scope,data) VALUES(?,?)',
      variables: [
        Variable(scope),
        Variable(jsonEncode(exams.map((e) => e.toJson()).toList())),
      ],
    );
  }

  Future<List<Exam>> cached(String scope) async {
    check(scope);
    final row = await customSelect(
      'SELECT data FROM exam_cache WHERE scope=?',
      variables: [Variable(scope)],
    ).getSingleOrNull();
    if (row == null) return [];
    return (jsonDecode(row.read<String>('data')) as List)
        .map((e) => Exam.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<void> clearCache(String scope) async {
    await customUpdate(
      'DELETE FROM exam_cache WHERE scope=?',
      variables: [Variable(scope)],
    );
  }
}
