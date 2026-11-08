import 'dart:convert';

import 'package:drift/drift.dart';

import '../domain/models.dart';

// Versioned SQL through Drift, deliberately no token/URL/password column.
class LocalStore extends GeneratedDatabase {
  LocalStore(super.executor);
  @override
  int get schemaVersion => 1;
  @override
  Iterable<TableInfo<Table, Object?>> get allTables => const [];
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => const [];
  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (_) async {
      await customStatement(
        'CREATE TABLE operations (id TEXT PRIMARY KEY, scope TEXT NOT NULL, data TEXT NOT NULL, running INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL)',
      );
      await customStatement(
        'CREATE INDEX operations_scope ON operations(scope, created_at)',
      );
      await customStatement(
        'CREATE TABLE exam_cache (scope TEXT PRIMARY KEY, data TEXT NOT NULL)',
      );
    },
    onUpgrade: (_, from, to) async {
      throw StateError('Unreviewed migration $from -> $to');
    },
  );
  void check(String scope) {
    if (!scope.startsWith('synthetic-local-') ||
        !scope.contains('/synthetic-local-patient-')) {
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

  Future<void> save(PendingUpload op) async {
    check(op.scope);
    await customUpdate(
      'UPDATE operations SET data=? WHERE id=? AND scope=?',
      variables: [
        Variable(op.serialize()),
        Variable(op.id),
        Variable(op.scope),
      ],
    );
  }

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

  Future<bool> claim(String scope, String id) async =>
      (await customUpdate(
        'UPDATE operations SET running=1 WHERE id=? AND scope=? AND running=0',
        variables: [Variable(id), Variable(scope)],
      )) ==
      1;
  Future<void> release(String scope, String id) async {
    await customUpdate(
      'UPDATE operations SET running=0 WHERE id=? AND scope=?',
      variables: [Variable(id), Variable(scope)],
    );
  }

  // Startup recovers leases only; it never replays a write.
  Future<void> recover() async {
    await customUpdate('UPDATE operations SET running=0');
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

  Future<void> clearScope(String scope) async {
    await transaction(() async {
      await customUpdate(
        'DELETE FROM exam_cache WHERE scope=?',
        variables: [Variable(scope)],
      );
      await customUpdate(
        'DELETE FROM operations WHERE scope=?',
        variables: [Variable(scope)],
      );
    });
  }
}
