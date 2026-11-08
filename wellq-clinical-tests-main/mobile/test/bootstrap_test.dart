import 'package:flutter_test/flutter_test.dart';
import 'package:wellq_mobile/main.dart' as application;

void main() {
  testWidgets('default composition stays locked without local debug opt-in', (
    tester,
  ) async {
    // No path-provider mock or identity service: opening a DB/session would fail.
    await application.main();
    await tester.pumpAndSettle();
    expect(find.textContaining('modo productivo bloqueado'), findsOneWidget);
    expect(find.text('Conectar paciente sintético'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
