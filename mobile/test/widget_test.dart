import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/main.dart';

void main() {
  testWidgets('App launch smoke test displays Splash screen branding', (WidgetTester tester) async {
    // Build our app and trigger first frame
    await tester.pumpWidget(const MediConnectApp());

    // Verify splash branding is visible immediately on launch
    expect(find.text('MediConnect'), findsOneWidget);
    expect(find.text('Your Health, Connected.'), findsOneWidget);

    // Advance clock past the splash delay to complete timer
    await tester.pump(const Duration(milliseconds: 1500));
  });
}
