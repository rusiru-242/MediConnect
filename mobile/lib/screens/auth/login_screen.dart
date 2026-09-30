import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/mediconnect_logo.dart';

/// Patient login screen providing email/password authentication, validation,
/// loading states, and error handling against FastAPI backend.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _obscurePassword = true;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  String? _validateEmail(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Email address is required.';
    }
    final emailRegex = RegExp(
      r'^[a-zA-Z0-9.!#$%&’*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$',
    );
    if (!emailRegex.hasMatch(value.trim())) {
      return 'Please enter a valid email address.';
    }
    return null;
  }

  String? _validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Password is required.';
    }
    return null;
  }

  Future<void> _handleSubmit() async {
    // Clear any previous error before submitting
    final authProvider = context.read<AuthProvider>();
    authProvider.clearError();

    if (!_formKey.currentState!.validate()) {
      return;
    }

    // Dismiss keyboard
    FocusScope.of(context).unfocus();

    final success = await authProvider.login(
      email: _emailController.text.trim(),
      password: _passwordController.text,
    );

    if (!mounted) return;

    if (success) {
      Navigator.of(context).pushNamedAndRemoveUntil(
        '/patient/home',
        (route) => false,
      );
    }
  }

  void _onForgotPassword() {
    Navigator.of(context).pushNamed('/forgot-password');
  }

  void _onGoogleSignIn() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Google Sign-In will be available soon.'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _onCreateAccount() {
    Navigator.of(context).pushNamed('/register');
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final isLoading = authProvider.isLoading;
    final errorMessage = authProvider.errorMessage;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Patient Login'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
          onPressed: isLoading ? null : () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 16),
                const Center(
                  child: MediConnectLogo(size: 64),
                ),
                const SizedBox(height: 20),
                const Text(
                  'Welcome Back',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                    letterSpacing: -0.5,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Log in to access your healthcare portal.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 15,
                    color: AppTheme.textSecondary,
                  ),
                ),
                const SizedBox(height: 28),

                // Error Banner
                if (errorMessage != null) ...[
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppTheme.errorContainer,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: AppTheme.error.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(
                          Icons.error_outline_rounded,
                          color: AppTheme.error,
                          size: 20,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            errorMessage,
                            style: const TextStyle(
                              color: AppTheme.error,
                              fontSize: 14,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),
                ],

                // Email Field
                TextFormField(
                  key: const Key('login_email_input'),
                  controller: _emailController,
                  enabled: !isLoading,
                  keyboardType: TextInputType.emailAddress,
                  autocorrect: false,
                  textInputAction: TextInputAction.next,
                  decoration: const InputDecoration(
                    labelText: 'Email Address',
                    hintText: 'patient@example.com',
                    prefixIcon: Icon(Icons.email_outlined, size: 20),
                  ),
                  validator: _validateEmail,
                ),
                const SizedBox(height: 16),

                // Password Field
                TextFormField(
                  key: const Key('login_password_input'),
                  controller: _passwordController,
                  enabled: !isLoading,
                  obscureText: _obscurePassword,
                  textInputAction: TextInputAction.done,
                  onFieldSubmitted: (_) => _handleSubmit(),
                  decoration: InputDecoration(
                    labelText: 'Password',
                    hintText: 'Enter your password',
                    prefixIcon: const Icon(Icons.lock_outline_rounded, size: 20),
                    suffixIcon: IconButton(
                      icon: Icon(
                        _obscurePassword
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                        size: 20,
                      ),
                      onPressed: () {
                        setState(() {
                          _obscurePassword = !_obscurePassword;
                        });
                      },
                    ),
                  ),
                  validator: _validatePassword,
                ),
                const SizedBox(height: 8),

                // Forgot Password
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    key: const Key('login_forgot_password_button'),
                    onPressed: isLoading ? null : _onForgotPassword,
                    child: const Text('Forgot Password?'),
                  ),
                ),
                const SizedBox(height: 16),

                // Login Submit Button
                ElevatedButton(
                  key: const Key('login_submit_button'),
                  onPressed: isLoading ? null : _handleSubmit,
                  child: isLoading
                      ? const SizedBox(
                          height: 22,
                          width: 22,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.5,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Text('Login'),
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

                // Continue with Google Button
                OutlinedButton.icon(
                  key: const Key('login_google_button'),
                  onPressed: isLoading ? null : _onGoogleSignIn,
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
                const SizedBox(height: 24),

                // Create Account Link
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text(
                      "Don't have an account? ",
                      style: TextStyle(
                        fontSize: 14,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                    GestureDetector(
                      onTap: isLoading ? null : _onCreateAccount,
                      child: const Text(
                        'Create Account',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.primary,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
