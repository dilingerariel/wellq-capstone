import 'dart:io';
import '../domain/models.dart';
import '../domain/pdf_policy.dart';

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

  void validatePdf(List<int> bytes) {
    try {
      validatedSyntheticPdfBytes(bytes);
    } on FormatException {
      throw const ApiFailure(422, 'INVALID_SYNTHETIC_PDF');
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
        op.initiate['sha256'] is! String ||
        op.initiate['mime_type'] != 'application/pdf' ||
        await FileSystemEntity.type(file.path, followLinks: false) !=
            FileSystemEntityType.file ||
        await file.length() != size) {
      return null;
    }
    final bytes = await file.readAsBytes();
    if (bytes.length != size) return null;
    try {
      return verifiedPdfBytes(
        bytes,
        expectedSha256: op.initiate['sha256'] as String,
      );
    } on FormatException {
      return null;
    }
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
