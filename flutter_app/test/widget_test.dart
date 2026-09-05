// Smoke test — proves the app boots and the bootstrap placeholder renders
// with no exceptions. Replaced along with main.dart's real entry screen once
// FASE 4 (Autenticação) lands; this is intentionally minimal for FASE 2.

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/main.dart';

void main() {
  testWidgets('FazumApp boots and shows the bootstrap placeholder', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: FazumApp()));
    await tester.pump();

    expect(find.text('fazum'), findsOneWidget);
  });
}
