import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme/app_theme.dart';
import '../providers/auth_provider.dart';
import '../widgets/mediconnect_logo.dart';

/// Welcome screen introducing MediConnect with entry points to Login, Registration, and Google Sign-In.
class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  Future<void> _onGooglePressed(BuildContext context) async {
    final authProvider = context.read<AuthProvider>();
    authProvider.clearError();

    final success = await authProvider.signInWithGoogle();

    if (!context.mounted) return;

    if (success) {
      Navigator.of(context).pushNamedAndRemoveUntil(
        '/patient/home',
        (route) => false,
      );
    } else if (authProvider.errorMessage != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(authProvider.errorMessage!),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  void _onCreateAccountPressed(BuildContext context) {
    Navigator.of(context).pushNamed('/register');
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final isLoading = authProvider.isLoading;

    return Scaffold(
      backgroundColor: AppTheme.background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Spacer(flex: 2),
              const Center(
                child: MediConnectLogo(size: 80),
              ),
              const SizedBox(height: 24),
              const Center(
                child: Text(
                  'MediConnect',
                  style: TextStyle(
                    fontSize: 30,
                    fontWeight: FontWeight.bold,
                    letterSpacing: -0.5,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Healthcare made simpler.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.primary,
                  letterSpacing: -0.2,
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                'Find trusted doctors, manage appointments, and access healthcare support from one secure place.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 15,
                  height: 1.5,
                  color: AppTheme.textSecondary,
                ),
              ),
              const Spacer(flex: 3),
              // Login Button
              ElevatedButton(
                key: const Key('welcome_login_button'),
                onPressed: isLoading
                    ? null
                    : () {
                        Navigator.of(context).pushNamed('/login');
                      },
                child: const Text('Login'),
              ),
              const SizedBox(height: 12),
              // Create Account Button
              OutlinedButton(
                key: const Key('welcome_create_account_button'),
                onPressed: isLoading ? null : () => _onCreateAccountPressed(context),
                child: const Text('Create Account'),
              ),
              const SizedBox(height: 20),
              // Divider with OR
              Row(
                children: [
                  const Expanded(child: Divider()),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Text(
                      'OR',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textMuted,
                      ),
                    ),
                  ),
                  const Expanded(child: Divider()),
                ],
              ),
              const SizedBox(height: 20),
              // Google Visual Button
              OutlinedButton.icon(
                key: const Key('welcome_google_button'),
                onPressed: isLoading ? null : () => _onGooglePressed(context),
                icon: isLoading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.0,
                          valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primary),
                        ),
                      )
                    : Image.network(
                        'https://www.gstatic.com/images/branding/product/1x/gsa_512dp.png',
                        width: 20,
                        height: 20,
                        errorBuilder: (context, error, stackTrace) => const Icon(
                          Icons.account_circle_outlined,
                          size: 20,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                label: Text(
                  isLoading ? 'Connecting...' : 'Continue with Google',
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              const SizedBox(height: 24),
              // Doctor Registration Entry Point
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text(
                    'Are you a doctor? ',
                    style: TextStyle(
                      fontSize: 14,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                  GestureDetector(
                    key: const Key('welcome_doctor_register_link'),
                    onTap: isLoading
                        ? null
                        : () => Navigator.of(context).pushNamed('/doctor/register'),
                    child: const Text(
                      'Register as a Doctor',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.primary,
                      ),
                    ),
                  ),
                ],
              ),
              const Spacer(),
            ],
          ),
        ),
      ),
    );
  }
}
