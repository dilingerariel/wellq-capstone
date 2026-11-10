import 'dart:async';
import 'package:intl/date_symbol_data_local.dart';

Future<void> testExecutable(FutureOr<void> Function() main) async {
  // Legacy widget harnesses intentionally omit the app localization delegates.
  // Load the same packaged date symbols used by the real Material delegates.
  await initializeDateFormatting();
  await main();
}
