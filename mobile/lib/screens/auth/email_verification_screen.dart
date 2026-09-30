import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/validators.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/mediconnect_logo.dart';

/// Screen for entering and verifying 6-digit email OTP.
/// Includes cooldown timer for resending OTP and navigates to Login on success.
class EmailVerificationScreen extends StatefulWidget {
  final String email;
  final bool isDoctor;

  const EmailVerificationScreen({
    super.key,
    required this.email,
    this.isDoctor = false,
  });

  @override
  State<EmailVerificationScreen> createState() => _EmailVerificationScreenState();
}

class _EmailVerificationScreenState extends State<EmailVerificationScreen> {
  final _otpController = TextEditingController();
  final _focusNode = FocusNode();

  Timer? _timer;
  int _secondsRemaining = 60;
  bool _canResend = false;
  bool _isResending = false;
  String? _localError;

  @override
  void initState() {
    super.initState();
    _startCooldownTimer();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _otpController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _startCooldownTimer() {
    _timer?.cancel();
    setState(() {
      _secondsRemaining = 60;
      _canResend = false;
    });

    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_secondsRemaining > 1) {
        setState(() {
          _secondsRemaining--;
        });
      } else {
        timer.cancel();
        setState(() {
          _secondsRemaining = 0;
          _canResend = true;
        });
      }
    });
  }

  Future<void> _handleVerify() async {
    final otp = _otpController.text.trim();
    final otpError = Validators.validateOtp(otp);

    if (otpError != null) {
      setState(() {
        _localError = otpError;
      });
      return;
    }

    setState(() {
      _localError = null;
    });

    FocusScope.of(context).unfocus();

    final authProvider = context.read<AuthProvider>();
    authProvider.clearError();

    final success = await authProvider.verifyEmail(
      email: widget.email,
      otp: otp,
    );

    if (!mounted) return;

    if (success) {
      if (widget.isDoctor) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            backgroundColor: AppTheme.success,
            content: Text('Email verified successfully.'),
            duration: Duration(seconds: 3),
          ),
        );

        // Navigate to Doctor Application Status screen
        Navigator.of(context).pushNamedAndRemoveUntil(
          '/doctor/application-status',
          (route) => false,
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            backgroundColor: AppTheme.success,
            content: Text('Email verified successfully. You can now log in.'),
            duration: Duration(seconds: 3),
          ),
        );

        // Navigate to Login screen cleanly
        Navigator.of(context).pushNamedAndRemoveUntil(
          '/login',
          (route) => false,
        );
      }
    }
  }

  Future<void> _handleResend() async {
    if (!_canResend || _isResending) return;

    setState(() {
      _isResending = true;
      _localError = null;
    });

    final authProvider = context.read<AuthProvider>();
    authProvider.clearError();

    final message = await authProvider.resendVerificationOtp(
      email: widget.email,
    );

    if (!mounted) return;

    setState(() {
      _isResending = false;
    });

    if (message != null) {
      _otpController.clear();
      _startCooldownTimer();

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppTheme.primary,
          content: Text('A new verification code has been sent.'),
          duration: Duration(seconds: 3),
        ),
      );
    }
  }

  Widget _buildOtpBoxes() {
    final text = _otpController.text;

    return GestureDetector(
      onTap: () {
        _focusNode.requestFocus();
      },
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Visual 6-digit box indicators
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: List.generate(6, (index) {
              final isFilled = index < text.length;
              final isFocused = index == text.length && _focusNode.hasFocus;
              final char = isFilled ? text[index] : '';

              return Container(
                width: 48,
                height: 56,
                decoration: BoxDecoration(
                  color: isFocused ? AppTheme.primaryContainer.withValues(alpha: 0.3) : AppTheme.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isFocused
                        ? AppTheme.primary
                        : (isFilled ? AppTheme.primaryDark : AppTheme.border),
                    width: isFocused ? 2 : 1.5,
                  ),
                ),
                child: Center(
                  child: Text(
                    char,
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                ),
              );
            }),
          ),
          // Hidden real input field handling keyboard entry
          Opacity(
            opacity: 0.0,
            child: TextField(
              key: const Key('otp_text_field'),
              controller: _otpController,
              focusNode: _focusNode,
              keyboardType: TextInputType.number,
              inputFormatters: [
                FilteringTextInputFormatter.digitsOnly,
                LengthLimitingTextInputFormatter(6),
              ],
              onChanged: (_) {
                setState(() {
                  _localError = null;
                });
                if (_otpController.text.length == 6) {
                  _handleVerify();
                }
              },
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final isLoading = authProvider.isLoading;
    final errorMessage = _localError ?? authProvider.errorMessage;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Verify Email'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
          onPressed: isLoading ? null : () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 16),
              const Center(
                child: MediConnectLogo(size: 64),
              ),
              const SizedBox(height: 24),
              const Text(
                'Verify your email',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.bold,
                  letterSpacing: -0.5,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              RichText(
                textAlign: TextAlign.center,
                text: TextSpan(
                  style: const TextStyle(
                    fontSize: 15,
                    height: 1.5,
                    color: AppTheme.textSecondary,
                  ),
                  children: [
                    const TextSpan(text: "We've sent a 6-digit verification code to\n"),
                    TextSpan(
                      text: widget.email,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        color: AppTheme.primary,
                      ),
                    ),
                  ],
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

              // 6-digit OTP input boxes
              _buildOtpBoxes(),
              const SizedBox(height: 32),

              // Verify button
              ElevatedButton(
                key: const Key('verify_otp_button'),
                onPressed: isLoading ? null : _handleVerify,
                child: isLoading
                    ? const SizedBox(
                        height: 22,
                        width: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : const Text('Verify Email'),
              ),
              const SizedBox(height: 24),

              // Resend Code Section
              Center(
                child: _canResend
                    ? TextButton(
                        key: const Key('resend_otp_button'),
                        onPressed: (_isResending || isLoading) ? null : _handleResend,
                        child: _isResending
                            ? const SizedBox(
                                height: 16,
                                width: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primary),
                                ),
                              )
                            : const Text('Resend Code'),
                      )
                    : Text(
                        'Resend code in ${_secondsRemaining}s',
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                          color: AppTheme.textMuted,
                        ),
                      ),
              ),
              const SizedBox(height: 16),

              // Back to Login option
              Center(
                child: TextButton(
                  key: const Key('verification_back_to_login_button'),
                  onPressed: isLoading
                      ? null
                      : () {
                          Navigator.of(context).pushNamedAndRemoveUntil(
                            '/login',
                            (route) => false,
                          );
                        },
                  child: const Text('Back to Login'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
