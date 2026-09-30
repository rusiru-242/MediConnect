import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import 'core/theme/app_theme.dart';
import 'providers/auth_provider.dart';
import 'screens/auth/create_account_screen.dart';
import 'screens/auth/forgot_password_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/patient/patient_home_screen.dart';
import 'screens/splash_screen.dart';
import 'screens/welcome_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  // Set system UI overlay style for modern look
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
    ),
  );

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
      ],
      child: MaterialApp(
        title: 'MediConnect',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        initialRoute: '/',
        routes: {
          '/': (context) => const SplashScreen(),
          '/welcome': (context) => const WelcomeScreen(),
          '/register': (context) => const CreateAccountScreen(),
          '/forgot-password': (context) => const ForgotPasswordScreen(),
          '/login': (context) => const LoginScreen(),
          '/patient/home': (context) => const PatientHomeScreen(),
        },
      ),
    );
  }
}
