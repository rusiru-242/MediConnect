import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/validators.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/mediconnect_logo.dart';

/// Screen allowing patient to set a new password using verified temporary resetToken.
/// On successful reset, user is routed to Login to authenticate with new credentials.
class ResetPasswordScreen extends StatefulWidget {
  final String resetToken;

  const ResetPasswordScreen({
    super.key,
    required this.resetToken,
  });

  @override
  State<ResetPasswordScreen> createState() => _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends State<ResetPasswordScreen> {
  final _formKey = GlobalKey<FormState>();

  final _newPasswordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  bool _obscureNewPassword = true;
  bool _obscureConfirmPassword = true;

  @override
  void dispose() {
    _newPasswordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _handleResetPassword() async {
    final authProvider = context.read<AuthProvider>();
    authProvider.clearError();

    if (!_formKey.currentState!.validate()) {
      return;
    }

    FocusScope.of(context).unfocus();

    final success = await authProvider.resetPassword(
      resetToken: widget.resetToken,
      newPassword: _newPasswordController.text,
      confirmPassword: _confirmPasswordController.text,
    );

    if (!mounted) return;

    if (success) {
      // Clear password controllers immediately
      _newPasswordController.clear();
      _confirmPasswordController.clear();

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppTheme.success,
          content: Text(
            'Your password has been updated. Please log in with your new password.',
          ),
          duration: Duration(seconds: 4),
        ),
      );

      // Navigate back to Login clearing the entire auth stack
      Navigator.of(context).pushNamedAndRemoveUntil(
        '/login',
        (route) => false,
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
        title: const Text('Reset Password'),
        // Prevent accidental back navigation with consumed OTP token
        automaticallyImplyLeading: false,
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
                  'Create New Password',
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
                  'Choose a strong password for your MediConnect account.',
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

                // New Password Field
                TextFormField(
                  key: const Key('reset_new_password_input'),
                  controller: _newPasswordController,
                  enabled: !isLoading,
                  obscureText: _obscureNewPassword,
                  textInputAction: TextInputAction.next,
                  decoration: InputDecoration(
                    labelText: 'New Password',
                    hintText: 'Enter new password',
                    prefixIcon: const Icon(Icons.lock_outline_rounded, size: 20),
                    suffixIcon: IconButton(
                      icon: Icon(
                        _obscureNewPassword
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                        size: 20,
                      ),
                      onPressed: () {
                        setState(() {
                          _obscureNewPassword = !_obscureNewPassword;
                        });
                      },
                    ),
                  ),
                  validator: Validators.validatePassword,
                ),
                const SizedBox(height: 16),

                // Confirm New Password Field
                TextFormField(
                  key: const Key('reset_confirm_password_input'),
                  controller: _confirmPasswordController,
                  enabled: !isLoading,
                  obscureText: _obscureConfirmPassword,
                  textInputAction: TextInputAction.done,
                  onFieldSubmitted: (_) => _handleResetPassword(),
                  decoration: InputDecoration(
                    labelText: 'Confirm New Password',
                    hintText: 'Re-enter new password',
                    prefixIcon: const Icon(Icons.lock_outline_rounded, size: 20),
                    suffixIcon: IconButton(
                      icon: Icon(
                        _obscureConfirmPassword
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                        size: 20,
                      ),
                      onPressed: () {
                        setState(() {
                          _obscureConfirmPassword = !_obscureConfirmPassword;
                        });
                      },
                    ),
                  ),
                  validator: (val) => Validators.validateConfirmPassword(
                    val,
                    _newPasswordController.text,
                  ),
                ),
                const SizedBox(height: 32),

                // Reset Password Submit Button
                ElevatedButton(
                  key: const Key('submit_reset_password_button'),
                  onPressed: isLoading ? null : _handleResetPassword,
                  child: isLoading
                      ? const SizedBox(
                          height: 22,
                          width: 22,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.5,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Text('Reset Password'),
                ),
                const SizedBox(height: 24),

                // Cancel / Back to Login
                Center(
                  child: TextButton(
                    key: const Key('reset_password_cancel_to_login'),
                    onPressed: isLoading
                        ? null
                        : () {
                            Navigator.of(context).pushNamedAndRemoveUntil(
                              '/login',
                              (route) => false,
                            );
                          },
                    child: const Text('Cancel and return to Login'),
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
