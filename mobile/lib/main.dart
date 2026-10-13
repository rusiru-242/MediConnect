import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_stripe/flutter_stripe.dart';
import 'package:provider/provider.dart';

import 'core/constants/api_constants.dart';
import 'core/theme/app_theme.dart';
import 'providers/admin_provider.dart';
import 'providers/auth_provider.dart';
import 'providers/notification_provider.dart';
import 'screens/admin/admin_dashboard_screen.dart';
import 'screens/admin/doctor_applications_screen.dart';
import 'screens/auth/create_account_screen.dart';
import 'screens/auth/forgot_password_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/doctor/add_availability_screen.dart';
import 'screens/doctor/doctor_application_status_screen.dart';
import 'screens/doctor/doctor_appointment_detail_screen.dart';
import 'screens/doctor/doctor_appointments_screen.dart';
import 'screens/doctor/doctor_home_screen.dart';
import 'screens/doctor/doctor_registration_screen.dart';
import 'screens/doctor/manage_availability_screen.dart';
import 'screens/notifications/notifications_screen.dart';
import 'screens/patient/ai_booking_assistant_screen.dart';
import 'screens/patient/ai_doctor_recommendation_screen.dart';
import 'screens/patient/appointment_detail_screen.dart';
import 'screens/patient/doctor_detail_screen.dart';
import 'screens/patient/find_doctor_screen.dart';
import 'screens/patient/my_appointments_screen.dart';
import 'screens/patient/patient_home_screen.dart';
import 'screens/patient/payment_history_screen.dart';
import 'screens/splash_screen.dart';
import 'screens/welcome_screen.dart';
import 'services/fcm_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Stripe SDK on supported native mobile platforms only (Android / iOS).
  // MediConnect currently targets Android for Stripe testing.
  // Native flutter_stripe is skipped cleanly on web to prevent MissingPluginException.
  final isNativeStripeSupported = !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.android ||
          defaultTargetPlatform == TargetPlatform.iOS);

  if (isNativeStripeSupported) {
    Stripe.publishableKey = ApiConstants.defaultStripePublishableKey;
    try {
      await Stripe.instance.applySettings();
    } catch (e, stackTrace) {
      // Do not swallow genuine native Stripe initialization failures silently
      debugPrint('CRITICAL: Failed to initialize Stripe on native platform: $e\n$stackTrace');
      rethrow;
    }
  } else {
    debugPrint('Stripe native initialization skipped cleanly on unsupported platform.');
  }

  // Initialize Firebase Cloud Messaging safely (graceful fallback if unconfigured)
  await FcmService().initialize();

  // Set system UI overlay style for modern look
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
    ),
  );

  // Initialize backend server URL (checks saved preferences or auto-detects reachable host)
  await ApiConstants.initialize();

  if (kDebugMode) {
    debugPrint('[ApiConfig] Active API Base URL: ${ApiConstants.baseUrl} (Host: ${ApiConstants.hostBaseUrl})');
  }

  runApp(const MediConnectApp());
}

/// Root widget for the MediConnect application.
class MediConnectApp extends StatelessWidget {
  const MediConnectApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>(
          create: (_) => AuthProvider(),
        ),
        ChangeNotifierProvider<AdminProvider>(
          create: (_) => AdminProvider(),
        ),
        ChangeNotifierProvider<NotificationProvider>(
          create: (_) => NotificationProvider(),
        ),
      ],
      child: MaterialApp(
        title: 'MediConnect',
        navigatorKey: FcmService().navigatorKey,
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        initialRoute: '/',
        routes: {
          '/': (context) => const SplashScreen(),
          '/welcome': (context) => const WelcomeScreen(),
          '/register': (context) => const CreateAccountScreen(),
          '/forgot-password': (context) => const ForgotPasswordScreen(),
          '/login': (context) => const LoginScreen(),
          '/notifications': (context) => const NotificationsScreen(),
          '/patient/home': (context) => const PatientHomeScreen(),
          '/patient/ai-recommendations': (context) => const AiDoctorRecommendationScreen(),
          '/patient/ai-booking': (context) => const AiBookingAssistantScreen(),
          '/patient/find-doctor': (context) => const FindDoctorScreen(),
          '/patient/doctor-detail': (context) => const DoctorDetailScreen(),
          '/patient/my-appointments': (context) => const MyAppointmentsScreen(),
          '/patient/appointment-detail': (context) => const AppointmentDetailScreen(),
          '/patient/payments': (context) => const PaymentHistoryScreen(),
          '/doctor/register': (context) => const DoctorRegistrationScreen(),
          '/doctor/application-status': (context) => const DoctorApplicationStatusScreen(),
          '/doctor/home': (context) => const DoctorHomeScreen(),
          '/doctor/appointments': (context) => const DoctorAppointmentsScreen(),
          '/doctor/appointment-detail': (context) => const DoctorAppointmentDetailScreen(),
          '/doctor/manage-availability': (context) => const ManageAvailabilityScreen(),
          '/doctor/add-availability': (context) => const AddAvailabilityScreen(),
          '/admin/dashboard': (context) => const AdminDashboardScreen(),
          '/admin/doctor-applications': (context) => const DoctorApplicationsScreen(),
        },
      ),
    );
  }
}
