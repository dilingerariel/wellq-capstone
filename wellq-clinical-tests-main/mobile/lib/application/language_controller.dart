import 'package:flutter/widgets.dart';
import '../data/language_preference.dart';

class LanguageController extends ChangeNotifier {
  LanguageController({this.preference});
  final LanguagePreference? preference;
  String _code = 'es';
  int _selection = 0;
  bool saveFailed = false, _disposed = false;
  Future<void> _writes = Future.value();
  String get code => _code;
  Locale get locale => Locale(_code);

  Future<void> load() async {
    _code = await preference?.read() ?? 'es';
    if (!_disposed) notifyListeners();
  }

  Future<void> select(String code) {
    _code = code == 'en' ? 'en' : 'es';
    final selected = _code;
    final ticket = ++_selection;
    saveFailed = false;
    notifyListeners(); // Rebuild immediately; persistence needs no network/session.
    _writes = _writes.then((_) async {
      try {
        await preference?.write(selected);
      } catch (_) {
        if (ticket == _selection) {
          saveFailed = true;
          if (!_disposed) notifyListeners();
        }
      }
    });
    return _writes;
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
