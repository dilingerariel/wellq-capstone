// Focused pure Dart/real temporary filesystem checks; no Flutter tester, DB or HTTP.
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';
import 'package:wellq_mobile/data/file_vault.dart';
import 'package:wellq_mobile/domain/models.dart';
import 'package:wellq_mobile/domain/pdf_policy.dart';
import 'package:wellq_mobile/domain/sample_policy.dart';

Future<void> main() async {
  var passed = 0;
  void check(bool condition, String name) {
    if (!condition) throw StateError('Failed: $name');
    passed++;
  }

  void reject(void Function() action, String name) {
    var rejected = false;
    try {
      action();
    } on FormatException {
      rejected = true;
    }
    check(rejected, name);
  }

  final root = await Directory.systemTemp.createTemp('wellq-multi-pdf-check-');
  final vault = FileVault(root);
  final first = await File('assets/synthetic.pdf').readAsBytes();
  final text = latin1.decode(first);
  final eof = text.lastIndexOf('%%EOF');
  check(eof >= 0, 'reviewed fixture has PDF EOF');
  final second = latin1.encode(
    '${text.substring(0, eof)}% SYNTHETIC SECOND FIXTURE\n${text.substring(eof)}',
  );
  final a = validatedSyntheticPdfBytes(first, fileName: 'first.PDF');
  final b = validatedSyntheticPdfBytes(second, fileName: 'second.pdf');
  final hashA = sha256.convert(a).toString(),
      hashB = sha256.convert(b).toString();
  check(
    hashA == syntheticPdfSha256 && hashA != hashB,
    'independent hashes and legacy identity',
  );
  PendingUpload operation(String id, List<int> bytes, String hash) =>
      PendingUpload(id, 'synthetic-local-test/synthetic-local-patient-test', {
        'title': 'SYNTHETIC fixture',
        'file': 'uploads/$id.pdf',
        'initiate_key': 'stable-initiate-$id',
        'complete_key': 'stable-complete-$id',
        'copy_pending': true,
        'initiate': {
          'client_upload_id': id,
          'sha256': hash,
          'size_bytes': bytes.length,
          'mime_type': 'application/pdf',
          'file_name': 'synthetic.pdf',
        },
      });
  final old = operation('11111111-1111-4111-8111-111111111111', a, hashA);
  final newer = operation('22222222-2222-4222-8222-222222222222', b, hashB);
  for (final op in [old, newer]) {
    final bytes = op == old ? a : b;
    vault.validatePdf(bytes);
    await vault.stage(op, bytes);
    check(
      await vault.inspect(op, () {}) == null,
      'recover complete partial copy ${op.id}',
    );
    check(
      await vault.verified(vault.resolve(op.file), op) != null,
      'verify stored PDF ${op.id}',
    );
    final metadata = File('${root.path}/${op.id}.json');
    await metadata.writeAsString(op.serialize(), flush: true);
    final restored = PendingUpload.deserialize(await metadata.readAsString());
    check(
      restored.serialize() == op.serialize() &&
          restored.attempts == 0 &&
          restored.phase == 'queued',
      'restart serialization preserves IDs, keys, state, hash, reference and zero attempts',
    );
    check(
      await FileVault(root).inspect(restored, () {}) == null,
      'new vault recovers existing metadata',
    );
  }
  reject(
    () => verifiedPdfBytes(a, expectedSha256: hashB),
    'another document hash rejected',
  );
  final changed = Uint8List.fromList(b);
  changed[30] ^= 1;
  validatedSyntheticPdfBytes(changed); // Still passes format screening.
  await vault.resolve(newer.file).writeAsBytes(changed, flush: true);
  check(
    await vault.verified(vault.resolve(newer.file), newer) == null,
    'modified stored bytes rejected',
  );
  check(
    await vault.inspect(newer, () {}) == 'corrupt',
    'recovery reports corruption without deleting',
  );
  check(await vault.resolve(newer.file).exists(), 'corrupt file retained');
  check(
    await vault.verified(vault.resolve(old.file), old) != null,
    'legacy document remains readable',
  );
  final legacyConfirmed = PendingUpload.deserialize(old.serialize())
    ..phase = 'confirmed'
    ..attempts = 2
    ..examId = 'synthetic-existing-exam'
    ..canDelete = true;
  check(
    PendingUpload.deserialize(legacyConfirmed.serialize()).serialize() ==
            legacyConfirmed.serialize() &&
        await vault.verified(
              vault.resolve(legacyConfirmed.file),
              legacyConfirmed,
            ) !=
            null,
    'legacy confirmed reception preserves state and remains readable',
  );
  reject(
    () => validatedSyntheticPdfBytes(a, fileName: 'document.png'),
    'extension mismatch',
  );
  reject(
    () => validatedSyntheticPdfBytes(a, mimeType: 'image/png'),
    'MIME mismatch',
  );
  reject(
    () => validatedSyntheticPdfBytes(utf8.encode('not a PDF')),
    'invalid signature',
  );
  reject(() => validatedSyntheticPdfBytes(a.sublist(0, 20)), 'incomplete PDF');
  reject(() => validatedSyntheticPdfBytes([]), 'empty file');
  var invalidRejected = false;
  try {
    vault.validatePdf(utf8.encode('%PDF real patient'));
  } on ApiFailure catch (error) {
    invalidRejected =
        error.status == 422 && error.code == 'INVALID_SYNTHETIC_PDF';
  }
  check(invalidRejected, 'repository validation error remains explicit');
  reject(
    () => validatedSyntheticPdfBytes(Uint8List(maxSyntheticPdfBytes + 1)),
    'size limit',
  );
  reject(
    () => verifiedPdfBytes(a, expectedSha256: ''),
    'missing hash is not inferred from bytes',
  );
  stdout.writeln(
    'multi-PDF isolated checks: $passed passed, 0 failed; temporary fixtures retained',
  );
}
