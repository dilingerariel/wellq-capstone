import 'dart:io';

/// Build-time allowlist, never a URL supplied by a document or API response.
class EndpointPolicy {
  EndpointPolicy(String configured, String trustedHost) {
    origin = Uri.parse(configured);
    local = configured == 'http://127.0.0.1:8765';
    if (local) return;
    if (origin.scheme != 'https' ||
        trustedHost.isEmpty ||
        origin.host != trustedHost.toLowerCase() ||
        InternetAddress.tryParse(origin.host) != null ||
        origin.userInfo.isNotEmpty ||
        origin.hasQuery ||
        origin.hasFragment ||
        (origin.path.isNotEmpty && origin.path != '/') ||
        origin.port != 443) {
      throw const FormatException('DEMO_ORIGIN_DENIED');
    }
  }
  factory EndpointPolicy.environment() => EndpointPolicy(
    const String.fromEnvironment(
      'WELLQ_DEMO_ORIGIN',
      defaultValue: 'http://127.0.0.1:8765',
    ),
    const String.fromEnvironment('WELLQ_DEMO_HOST'),
  );
  late final Uri origin;
  late final bool local;
  bool acceptsUpload(Uri uri) =>
      uri.scheme == origin.scheme &&
      uri.host == origin.host &&
      uri.port == origin.port &&
      uri.userInfo.isEmpty &&
      !uri.hasFragment &&
      uri.path.startsWith('/object/quarantine/clinical-tests/');
}
