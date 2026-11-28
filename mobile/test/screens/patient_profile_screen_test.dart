import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/theme/app_theme.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/patient/patient_profile_screen.dart';
import 'package:provider/provider.dart';

import '../helpers/fake_profile_service.dart';

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
          home: PatientProfileScreen(service: FakeProfileService()),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Patient Profile'), findsOneWidget);
    // R02 (A05-O1): the invented "MediConnect Pass" insurance card is gone; only real sections remain.
    expect(find.text('MEDICONNECT PASS'), findsNothing);
    expect(find.text('Health Summary'), findsOneWidget);
    expect(find.text('Health Records & Documents'), findsOneWidget);
  });
}
