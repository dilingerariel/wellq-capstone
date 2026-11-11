import 'dart:convert';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';

const maxSyntheticPdfBytes = 20 * 1024 * 1024;

// Format screening only, not a malware scan or proof that data are synthetic.
// Production remains blocked at the application/identity entry points.
Uint8List validatedSyntheticPdfBytes(
  List<int> bytes, {
  String fileName = 'synthetic.pdf',
  String mimeType = 'application/pdf',
}) {
  if (bytes.length > maxSyntheticPdfBytes) {
    throw const FormatException('fileTooLarge');
  }
  if (!fileName.toLowerCase().endsWith('.pdf') ||
      mimeType != 'application/pdf' ||
      bytes.length < 14 ||
      !RegExp(
        r'^%PDF-(1\.[0-7]|2\.0)',
      ).hasMatch(latin1.decode(bytes.take(8).toList())) ||
      !latin1
          .decode(
            bytes.skip(bytes.length > 1024 ? bytes.length - 1024 : 0).toList(),
          )
          .trimRight()
          .endsWith('%%EOF')) {
    throw const FormatException('syntheticIntegrityOnly');
  }
  return Uint8List.fromList(bytes);
}

Uint8List verifiedPdfBytes(List<int> bytes, {required String expectedSha256}) {
  if (bytes.length > maxSyntheticPdfBytes) {
    throw const FormatException('fileTooLarge');
  }
  if (!RegExp(r'^[a-f0-9]{64}$').hasMatch(expectedSha256) ||
      sha256.convert(bytes).toString() != expectedSha256) {
    throw const FormatException('syntheticIntegrityOnly');
  }
  return validatedSyntheticPdfBytes(bytes);
}

class VerifiedPdfDocument {
  const VerifiedPdfDocument(this.bytes, this.sha256);
  final List<int> bytes;
  final String sha256;
}
