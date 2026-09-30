import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/validators.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/mediconnect_logo.dart';
import 'reset_otp_screen.dart';

/// Screen allowing patients to request a password reset code for their registered email.
/// Backend returns a generic response to avoid account enumeration.
class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _handleSendResetCode() async {
    final authProvider = context.read<AuthProvider>();
    authProvider.clearError();

    if (!_formKey.currentState!.validate()) {
      return;
    }

    FocusScope.of(context).unfocus();

    final email = _emailController.text.trim().toLowerCase();

    final message = await authProvider.forgotPassword(email: email);

    if (!mounted) return;

    if (message != null) {
      // Navigate to ResetOtpScreen passing only email
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (context) => ResetOtpScreen(email: email),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final isLoading = authProvider.isLoading;
    final errorMessage = authProvider.errorMessage;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Forgot Password'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
          onPressed: isLoading ? null : () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 20.0),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 16),
                const Center(
                  child: MediConnectLogo(size: 64),
                ),
                const SizedBox(height: 24),
                const Text(
                  'Forgot Password?',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                    letterSpacing: -0.5,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 10),
                const Text(
                  "Enter your registered email address and we'll send you a verification code to reset your password.",
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 15,
                    height: 1.5,
                    color: AppTheme.textSecondary,
                  ),
                ),
                const SizedBox(height: 32),

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
                  const SizedBox(height: 24),
                ],

                // Email Field
                TextFormField(
                  key: const Key('forgot_password_email_input'),
                  controller: _emailController,
                  enabled: !isLoading,
                  keyboardType: TextInputType.emailAddress,
                  autocorrect: false,
                  textInputAction: TextInputAction.done,
                  onFieldSubmitted: (_) => _handleSendResetCode(),
                  decoration: const InputDecoration(
                    labelText: 'Email Address',
                    hintText: 'patient@example.com',
                    prefixIcon: Icon(Icons.email_outlined, size: 20),
                  ),
                  validator: Validators.validateEmail,
                ),
                const SizedBox(height: 28),

                // Submit Button
                ElevatedButton(
                  key: const Key('send_reset_code_button'),
                  onPressed: isLoading ? null : _handleSendResetCode,
                  child: isLoading
                      ? const SizedBox(
                          height: 22,
                          width: 22,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.5,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Text('Send Reset Code'),
                ),
                const SizedBox(height: 24),

                // Back to Login Link
                Center(
                  child: TextButton(
                    key: const Key('forgot_password_back_to_login'),
                    onPressed: isLoading ? null : () => Navigator.of(context).pop(),
                    child: const Text('Back to Login'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
