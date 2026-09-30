import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';
import '../widgets/mediconnect_logo.dart';

/// Welcome screen introducing MediConnect with entry points to Login and Registration.
class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  void _onGooglePressed(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Google Sign-In will be available soon.'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _onCreateAccountPressed(BuildContext context) {
    Navigator.of(context).pushNamed('/register');
  }

  @override
  Widget build(BuildContext context) {
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
                onPressed: () {
                  Navigator.of(context).pushNamed('/login');
                },
                child: const Text('Login'),
              ),
              const SizedBox(height: 12),
              // Create Account Button
              OutlinedButton(
                key: const Key('welcome_create_account_button'),
                onPressed: () => _onCreateAccountPressed(context),
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
              // Google Visual Button (Placeholder)
              OutlinedButton.icon(
                key: const Key('welcome_google_button'),
                onPressed: () => _onGooglePressed(context),
                icon: Image.network(
                  'https://www.gstatic.com/images/branding/product/1x/gsa_512dp.png',
                  width: 20,
                  height: 20,
                  errorBuilder: (context, error, stackTrace) => const Icon(
                    Icons.account_circle_outlined,
                    size: 20,
                    color: AppTheme.textSecondary,
                  ),
                ),
                label: const Text(
                  'Continue with Google',
                  style: TextStyle(
                    color: AppTheme.textPrimary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              const Spacer(),
            ],
          ),
        ),
      ),
    );
  }
}
