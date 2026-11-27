import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme/app_theme.dart';
import '../providers/auth_provider.dart';
import '../widgets/mediconnect_logo.dart';

/// Splash screen that displays MediConnect branding and determines auth state.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initializeAuth();
    });
  }

  Future<void> _initializeAuth() async {
    final authProvider = context.read<AuthProvider>();

    // Run auth session check and guarantee minimum splash duration for smooth UX
    await Future.wait([
      authProvider.checkAuthSession(),
      Future.delayed(const Duration(milliseconds: 1200)),
    ]);

    if (!mounted) return;

    if (authProvider.isAuthenticated) {
      if (authProvider.user?.role == 'DOCTOR') {
        final status = authProvider.doctorApplicationStatus;
        if (status?.isApproved == true) {
          Navigator.of(context).pushReplacementNamed('/doctor/home');
        } else {
          Navigator.of(context).pushReplacementNamed('/doctor/application-status');
        }
      } else if (authProvider.user?.role == 'PATIENT') {
        Navigator.of(context).pushReplacementNamed('/patient/home');
      } else {
        // Phase 32: Mobile only supports Patient and Doctor. Clear any other role.
        await authProvider.logout();
        if (!mounted) return;
        Navigator.of(context).pushReplacementNamed('/welcome');
      }
    } else {
      Navigator.of(context).pushReplacementNamed('/welcome');
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      backgroundColor: isDark ? AppTheme.darkBackground : AppTheme.background,
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Spacer(),
              const MediConnectLogo(size: 112),
              const SizedBox(height: 20),
              Text(
                'MediConnect',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  letterSpacing: -0.5,
                  color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Text(
                  'Intelligent Healthcare. Connected Workflows.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                    color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                    letterSpacing: 0.1,
                  ),
                ),
              ),
              const Spacer(),
              SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(
                  strokeWidth: 2.5,
                  valueColor: AlwaysStoppedAnimation<Color>(isDark ? AppTheme.darkPrimaryBlue : AppTheme.primary),
                ),
              ),
              const SizedBox(height: 48),
            ],
          ),
        ),
      ),
    );
  }
}
