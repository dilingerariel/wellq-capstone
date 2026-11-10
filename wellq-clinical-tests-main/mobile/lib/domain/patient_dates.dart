import 'package:intl/intl.dart';

String clinicalDate(String raw, {String? locale}) {
  final date = DateTime.tryParse(raw);
  if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(raw) ||
      date == null ||
      date.toIso8601String().substring(0, 10) != raw) {
    return 'dateUnavailable';
  }
  if (locale != null) return DateFormat.yMMMMd(locale).format(date);
  return '${raw.substring(8, 10)}/${raw.substring(5, 7)}/${raw.substring(0, 4)}';
}

// Only for confirmation.confirmed_at: the existing API writes datetime.utcnow()
// and may serialize without a suffix. Naive values in this field represent UTC.
// Explicit offsets are respected; the OS supplies local offset/DST at the instant.
String confirmationTime(String raw, {Duration? displayOffset, String? locale}) {
  if (!RegExp(
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})?$',
  ).hasMatch(raw)) {
    return 'timeUnavailable';
  }
  final zoned = RegExp(r'(Z|[+-]\d{2}:\d{2})$').hasMatch(raw);
  if (clinicalDate(raw.substring(0, 10)) == 'dateUnavailable') {
    return 'timeUnavailable';
  }
  final instant = DateTime.tryParse(zoned ? raw : '${raw}Z')?.toUtc();
  if (instant == null) return 'timeUnavailable';
  final offset = displayOffset ?? instant.toLocal().timeZoneOffset;
  final local = instant.add(offset);
  String two(int n) => n.toString().padLeft(2, '0');
  final minutes = offset.inMinutes.abs();
  final day = locale == null
      ? '${two(local.day)}/${two(local.month)}/${local.year}'
      : DateFormat.yMMMMd(locale).format(local);
  return '$day '
      '${two(local.hour)}:${two(local.minute)}:${two(local.second)} '
      '(UTC${offset.isNegative ? '-' : '+'}${two(minutes ~/ 60)}:${two(minutes % 60)})';
}
