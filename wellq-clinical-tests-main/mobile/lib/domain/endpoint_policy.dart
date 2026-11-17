import 'dart:io';

/// Build-time allowlist, never a URL supplied by a document or API response.
class EndpointPolicy {
  EndpointPolicy(String configured, String trustedHost) {
    origin = Uri.parse(configured);
    local = configured == 'http://127.0.0.1:8765';
    if (local) return;
    // Separate isolated demo over an explicitly configured ADB loopback only.
    // This does not enable LoopbackIdentity or arbitrary cleartext hosts.
    if (configured == 'http://127.0.0.1:9080' && trustedHost == '127.0.0.1') {
      return;
    }
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
  bool acceptsUpload(Uri uri) {
    final sameOrigin =
        uri.scheme == origin.scheme &&
        uri.host == origin.host &&
        uri.port == origin.port &&
        (uri.path.startsWith('/object/quarantine/clinical-tests/') ||
            uri.path == '/api/v1/demo/storage/upload');
    // Production demo uploads use short-lived GCS V4 signed URLs. Trust only
    // Google's canonical storage host and the backend-issued quarantine path.
    final googleStorage =
        uri.scheme == 'https' &&
        uri.host == 'storage.googleapis.com' &&
        uri.port == 443 &&
        uri.path.contains('/quarantine/clinical-tests/');
    return (sameOrigin || googleStorage) &&
        uri.userInfo.isEmpty &&
        !uri.hasFragment;
  }
}
