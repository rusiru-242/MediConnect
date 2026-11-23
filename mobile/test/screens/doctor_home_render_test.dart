import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/auth_session.dart';
import 'package:mediconnect/models/doctor_application_status.dart';
import 'package:mediconnect/models/user_model.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/providers/locale_provider.dart';
import 'package:mediconnect/providers/notification_provider.dart';
import 'package:mediconnect/providers/theme_provider.dart';
import 'package:mediconnect/screens/doctor/doctor_home_screen.dart';
import 'package:mediconnect/services/auth_api_service.dart';
import 'package:mediconnect/services/notification_service.dart';
import 'package:provider/provider.dart';

class MockAuthService extends AuthApiService {
  @override
  Future<DoctorApplicationStatus> getDoctorApplicationStatus() async {
    return DoctorApplicationStatus(
      doctorId: 'DOC-093B224C',
      specialty: 'Neurologist',
      verificationStatus: 'APPROVED',
      submittedAt: DateTime.parse('2026-11-23T11:50:44Z'),
    );
  }
}

class MockNotificationService extends NotificationService {
  @override
  Future<int> getUnreadCount() async => 1;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  FlutterSecureStorage.setMockInitialValues({});

  group('DoctorHomeScreen Render & Robustness Tests', () {
    setUp(() {
      FlutterSecureStorage.setMockInitialValues({});
    });
    testWidgets('DoctorHomeScreen renders completely without any RenderFlex overflow in English', (tester) async {
      tester.view.physicalSize = const Size(360, 780); // Compact mobile screen
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final authProvider = AuthProvider(authApiService: MockAuthService());
      authProvider.setSessionForTesting(const AuthSession(
        message: 'Authenticated',
        accessToken: 'token',
        refreshToken: 'refresh',
        expiresIn: 3600,
        user: UserModel(
          id: '6b0428944305e8b7a13d76cd',
          fullName: 'Dr. Asinsa',
          email: 'rusirukarunarathna4@gmail.com',
          role: 'DOCTOR',
          emailVerified: true,
          accountStatus: 'ACTIVE',
          authProviders: ['LOCAL'],
        ),
      ));

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
            ChangeNotifierProvider<ThemeProvider>(create: (_) => ThemeProvider()),
            ChangeNotifierProvider<LocaleProvider>(create: (_) => LocaleProvider()),
            ChangeNotifierProvider<NotificationProvider>(create: (_) => NotificationProvider(notificationService: MockNotificationService())),
          ],
          child: const MaterialApp(
            home: DoctorHomeScreen(),
          ),
        ),
      );

      await tester.pump();

      expect(find.byType(DoctorHomeScreen), findsOneWidget);
      expect(find.byType(SingleChildScrollView), findsOneWidget);
      expect(find.text('Dr. Asinsa'), findsOneWidget);
      expect(find.text('National Hospital Center'), findsOneWidget);
      expect(find.text("Today's Schedule & Consultations"), findsOneWidget);
      expect(find.byKey(const Key('doctor_home_today_schedule_card')), findsOneWidget);
      expect(find.byKey(const Key('doctor_home_appointments_card')), findsOneWidget);
      expect(find.byKey(const Key('doctor_home_consultations_card')), findsOneWidget);
      expect(find.byKey(const Key('doctor_home_manage_availability_card')), findsOneWidget);
      expect(find.byKey(const Key('doctor_home_my_profile_card')), findsOneWidget);
      expect(find.byKey(const Key('doctor_home_reviews_card')), findsOneWidget);
      expect(find.byKey(const Key('doctor_home_application_status_card')), findsOneWidget);
      expect(find.byKey(const Key('doctor_home_logout_button')), findsOneWidget);
    });

    testWidgets('DoctorHomeScreen renders properly in Sinhala mode without overflow', (tester) async {
      tester.view.physicalSize = const Size(360, 780);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final authProvider = AuthProvider(authApiService: MockAuthService());
      authProvider.setSessionForTesting(const AuthSession(
        message: 'Authenticated',
        accessToken: 'token',
        refreshToken: 'refresh',
        expiresIn: 3600,
        user: UserModel(
          id: '6b0428944305e8b7a13d76cd',
          fullName: 'Dr. Asinsa',
          email: 'rusirukarunarathna4@gmail.com',
          role: 'DOCTOR',
          emailVerified: true,
          accountStatus: 'ACTIVE',
          authProviders: ['LOCAL'],
        ),
      ));

      final localeProvider = LocaleProvider();
      await localeProvider.setLanguage(AppLanguage.sinhala);

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
            ChangeNotifierProvider<ThemeProvider>(create: (_) => ThemeProvider()),
            ChangeNotifierProvider<LocaleProvider>.value(value: localeProvider),
            ChangeNotifierProvider<NotificationProvider>(create: (_) => NotificationProvider(notificationService: MockNotificationService())),
          ],
          child: const MaterialApp(
            home: DoctorHomeScreen(),
          ),
        ),
      );

      await tester.pump();

      expect(find.text('ප්‍රතිකාර දළ විශ්ලේෂණය'), findsOneWidget);
      expect(find.text('අද දින කාලසටහන සහ උපදේශන'), findsOneWidget);
      expect(find.text('හමුවීම්'), findsOneWidget);
    });
  });
}
