import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/network/api_exceptions.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/auth/create_account_screen.dart';
import 'package:mediconnect/screens/auth/email_verification_screen.dart';
import 'package:mediconnect/services/auth_api_service.dart';
import 'package:provider/provider.dart';

class MockAuthApiServiceForRegister extends AuthApiService {
  ApiException? exceptionToThrow;
  bool wasCalled = false;

  @override
  Future<Map<String, dynamic>> registerPatient({
    required String fullName,
    required String email,
    required String phone,
    required String password,
  }) async {
    wasCalled = true;
    if (exceptionToThrow != null) {
      throw exceptionToThrow!;
    }
    return {
      'message': 'Patient registered successfully.',
      'user': {
        'id': 'p1',
        'email': email,
        'role': 'PATIENT',
        'emailVerified': false,
        'accountStatus': 'PENDING',
      }
    };
  }
}

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  Widget buildTestWidget(MockAuthApiServiceForRegister mockService) {
    return ChangeNotifierProvider<AuthProvider>(
      create: (_) => AuthProvider(authApiService: mockService),
      child: const MaterialApp(
        home: CreateAccountScreen(),
      ),
    );
  }

  group('CreateAccountScreen user-friendly validation tests', () {
    testWidgets('1. Client-side invalid email displays "Please enter a valid email address."',
        (tester) async {
      final mockService = MockAuthApiServiceForRegister();
      await tester.pumpWidget(buildTestWidget(mockService));
      await tester.pumpAndSettle();

      await tester.enterText(
          find.byKey(const Key('register_full_name_input')), 'John Doe');
      await tester.enterText(
          find.byKey(const Key('register_email_input')), 'invalid-email-format');
      await tester.enterText(
          find.byKey(const Key('register_phone_input')), '0771234567');
      await tester.enterText(
          find.byKey(const Key('register_password_input')), 'Password@123');
      await tester.enterText(
          find.byKey(const Key('register_confirm_password_input')), 'Password@123');

      // Submit
      await tester.ensureVisible(find.byType(ElevatedButton));
      await tester.tap(find.byType(ElevatedButton));
      await tester.pumpAndSettle();

      expect(find.text('Please enter a valid email address.'), findsOneWidget);
      expect(mockService.wasCalled, isFalse);
    });

    testWidgets('2. Backend 422 invalid email returns friendly message without Pydantic internals',
        (tester) async {
      final mockService = MockAuthApiServiceForRegister();
      mockService.exceptionToThrow = const ValidationException(
        message: 'Please enter a valid email address.',
        statusCode: 422,
        details: {
          'detail': [
            {
              'type': 'value_error',
              'loc': ['body', 'email'],
              'msg':
                  'value is not a valid email address: The part after the @-sign is a special-use or reserved name that cannot be used with email.',
              'input': 'patient@reserved.invalid'
            }
          ]
        },
      );

      await tester.pumpWidget(buildTestWidget(mockService));
      await tester.pumpAndSettle();

      await tester.enterText(
          find.byKey(const Key('register_full_name_input')), 'John Doe');
      await tester.enterText(
          find.byKey(const Key('register_email_input')), 'patient@reserved.invalid');
      await tester.enterText(
          find.byKey(const Key('register_phone_input')), '0771234567');
      await tester.enterText(
          find.byKey(const Key('register_password_input')), 'Password@123');
      await tester.enterText(
          find.byKey(const Key('register_confirm_password_input')), 'Password@123');

      await tester.ensureVisible(find.byType(ElevatedButton));
      await tester.tap(find.byType(ElevatedButton));
      await tester.pumpAndSettle();

      expect(mockService.wasCalled, isTrue);
      expect(find.text('Please enter a valid email address.'), findsWidgets);
      expect(find.textContaining('special-use or reserved name'), findsNothing);
      expect(find.textContaining('value is not a valid email address'), findsNothing);
    });

    testWidgets('3. Duplicate email (409) displays "An account with this email already exists."',
        (tester) async {
      final mockService = MockAuthApiServiceForRegister();
      mockService.exceptionToThrow = const ConflictException(
        message: 'An account with this email already exists.',
        statusCode: 409,
      );

      await tester.pumpWidget(buildTestWidget(mockService));
      await tester.pumpAndSettle();

      await tester.enterText(
          find.byKey(const Key('register_full_name_input')), 'John Doe');
      await tester.enterText(
          find.byKey(const Key('register_email_input')), 'existing@mediconnect.lk');
      await tester.enterText(
          find.byKey(const Key('register_phone_input')), '0771234567');
      await tester.enterText(
          find.byKey(const Key('register_password_input')), 'Password@123');
      await tester.enterText(
          find.byKey(const Key('register_confirm_password_input')), 'Password@123');

      await tester.ensureVisible(find.byType(ElevatedButton));
      await tester.tap(find.byType(ElevatedButton));
      await tester.pumpAndSettle();

      expect(find.text('An account with this email already exists.'), findsWidgets);
    });

    testWidgets('4. Invalid phone displays friendly mobile number validation',
        (tester) async {
      final mockService = MockAuthApiServiceForRegister();

      await tester.pumpWidget(buildTestWidget(mockService));
      await tester.pumpAndSettle();

      await tester.enterText(
          find.byKey(const Key('register_full_name_input')), 'John Doe');
      await tester.enterText(
          find.byKey(const Key('register_email_input')), 'valid@mediconnect.lk');
      await tester.enterText(
          find.byKey(const Key('register_phone_input')), '12345');
      await tester.enterText(
          find.byKey(const Key('register_password_input')), 'Password@123');
      await tester.enterText(
          find.byKey(const Key('register_confirm_password_input')), 'Password@123');

      await tester.ensureVisible(find.byType(ElevatedButton));
      await tester.tap(find.byType(ElevatedButton));
      await tester.pumpAndSettle();

      expect(find.textContaining('valid Sri Lankan mobile number'), findsOneWidget);
      expect(mockService.wasCalled, isFalse);
    });

    testWidgets('5. Weak password displays friendly password validation',
        (tester) async {
      final mockService = MockAuthApiServiceForRegister();

      await tester.pumpWidget(buildTestWidget(mockService));
      await tester.pumpAndSettle();

      await tester.enterText(
          find.byKey(const Key('register_full_name_input')), 'John Doe');
      await tester.enterText(
          find.byKey(const Key('register_email_input')), 'valid@mediconnect.lk');
      await tester.enterText(
          find.byKey(const Key('register_phone_input')), '0771234567');
      await tester.enterText(
          find.byKey(const Key('register_password_input')), 'weak');
      await tester.enterText(
          find.byKey(const Key('register_confirm_password_input')), 'weak');

      await tester.ensureVisible(find.byType(ElevatedButton));
      await tester.tap(find.byType(ElevatedButton));
      await tester.pumpAndSettle();

      expect(find.text('Password must be at least 8 characters long.'), findsOneWidget);
      expect(mockService.wasCalled, isFalse);
    });

    testWidgets('6. Backend offline displays connection failure message',
        (tester) async {
      final mockService = MockAuthApiServiceForRegister();
      mockService.exceptionToThrow = const NetworkException();

      await tester.pumpWidget(buildTestWidget(mockService));
      await tester.pumpAndSettle();

      await tester.enterText(
          find.byKey(const Key('register_full_name_input')), 'John Doe');
      await tester.enterText(
          find.byKey(const Key('register_email_input')), 'valid@mediconnect.lk');
      await tester.enterText(
          find.byKey(const Key('register_phone_input')), '0771234567');
      await tester.enterText(
          find.byKey(const Key('register_password_input')), 'Password@123');
      await tester.enterText(
          find.byKey(const Key('register_confirm_password_input')), 'Password@123');

      await tester.ensureVisible(find.byType(ElevatedButton));
      await tester.tap(find.byType(ElevatedButton));
      await tester.pumpAndSettle();

      expect(find.text('Unable to connect to MediConnect. Please try again.'), findsOneWidget);
    });

    testWidgets('7. Valid registration succeeds and navigates',
        (tester) async {
      final mockService = MockAuthApiServiceForRegister();

      await tester.pumpWidget(buildTestWidget(mockService));
      await tester.pumpAndSettle();

      await tester.enterText(
          find.byKey(const Key('register_full_name_input')), 'John Doe');
      await tester.enterText(
          find.byKey(const Key('register_email_input')), 'valid@mediconnect.lk');
      await tester.enterText(
          find.byKey(const Key('register_phone_input')), '0771234567');
      await tester.enterText(
          find.byKey(const Key('register_password_input')), 'Password@123');
      await tester.enterText(
          find.byKey(const Key('register_confirm_password_input')), 'Password@123');

      await tester.ensureVisible(find.byType(ElevatedButton));
      await tester.tap(find.byType(ElevatedButton));
      await tester.pumpAndSettle();

      expect(mockService.wasCalled, isTrue);
      // Navigated to EmailVerificationScreen
      expect(find.byType(EmailVerificationScreen), findsOneWidget);
    });
  });
}
