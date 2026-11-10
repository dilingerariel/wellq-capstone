import 'dart:io';

// Device preference only. Never reads/writes the clinical store or session.
class LanguagePreference {
  LanguagePreference(this.file);
  final File file;
  Future<String> read() async {
    try {
      if (!await file.exists() || await file.length() != 2) return 'es';
      final value = await file.readAsString();
      return value == 'en' || value == 'es' ? value : 'es';
    } catch (_) {
      return 'es';
    }
  }

  Future<void> write(String code) async {
    if (code != 'es' && code != 'en') throw ArgumentError('Unsupported locale');
    await file.writeAsString(code, flush: true);
  }
}
