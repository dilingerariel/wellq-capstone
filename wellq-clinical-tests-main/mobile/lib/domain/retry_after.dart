import 'dart:io';

/// Both wire formats of Retry-After. Invalid/past values use local backoff.
int retryAfterSeconds(String? header, {DateTime? now}) {
  if (header == null) return 0;
  final value = header.trim();
  if (RegExp(r'^\d+$').hasMatch(value)) {
    final seconds = int.tryParse(value);
    // A delay that cannot be represented by DateTime is not usable.
    final maximum =
        (8640000000000000 - (now ?? DateTime.now()).millisecondsSinceEpoch) ~/
        1000;
    if (seconds == null || seconds > maximum) return 0;
    return seconds;
  }
  try {
    final delay = HttpDate.parse(value).difference(now ?? DateTime.now());
    return delay.isNegative ? 0 : (delay.inMicroseconds / 1000000).ceil();
  } on HttpException {
    return 0;
  }
}
