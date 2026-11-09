import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/theme/app_theme.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/patient/patient_profile_screen.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('PatientProfileScreen renders correctly with Stitch Clinical Clarity theme', (tester) async {
    final authProvider = AuthProvider();
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
        ],
        child: MaterialApp(
          theme: AppTheme.lightTheme,
          home: const PatientProfileScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Patient Profile'), findsOneWidget);
    expect(find.text('MEDICONNECT PASS'), findsOneWidget);
    expect(find.text('Health Records & Documents'), findsOneWidget);
  });
}
