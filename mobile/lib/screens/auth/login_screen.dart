import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/constants/api_constants.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/mediconnect_logo.dart';
import '../../widgets/server_settings_sheet.dart';

/// Redesigned Login Screen with Google Stitch Clinical Clarity design system.
/// Supports role segmentation (Patient & Doctor), biometric quick trigger, and HIPAA badge.
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
  bool _rememberMe = true;
  String _selectedRole = 'patient'; // 'patient' or 'doctor'

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
    final authProvider = context.read<AuthProvider>();
    authProvider.clearError();

    if (!_formKey.currentState!.validate()) {
      return;
    }

    FocusScope.of(context).unfocus();

    final success = await authProvider.login(
      email: _emailController.text.trim(),
      password: _passwordController.text,
    );

    if (!mounted) return;

    if (success) {
      _navigateAfterLogin(authProvider);
    }
  }

  void _navigateAfterLogin(AuthProvider authProvider) {
    if (authProvider.user?.role == 'DOCTOR') {
      final status = authProvider.doctorApplicationStatus;
      final isApproved = status?.isApproved == true ||
          (authProvider.user?.accountStatus == 'ACTIVE' && status?.isPending != true);
      if (isApproved) {
        Navigator.of(context)
            .pushNamedAndRemoveUntil('/doctor/home', (route) => false);
      } else {
        final isRejected = status?.isRejected == true ||
            status?.verificationStatus.toUpperCase() == 'REJECTED';
        final message = isRejected
            ? 'Your doctor registration application was not approved. Please contact administrative support.'
            : 'Your doctor registration is pending admin approval.';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(message),
            backgroundColor: isRejected ? AppTheme.error : Colors.amber.shade800,
            duration: const Duration(seconds: 4),
          ),
        );
        Navigator.of(context).pushNamedAndRemoveUntil(
          '/doctor/application-status',
          (route) => false,
        );
      }
    } else if (authProvider.user?.role == 'PATIENT') {
      Navigator.of(context)
          .pushNamedAndRemoveUntil('/patient/home', (route) => false);
    } else {
      authProvider.logout();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Admin accounts are supported on the MediConnect Web Admin Portal. Please sign in through the web portal.',
          ),
          backgroundColor: AppTheme.error,
        ),
      );
    }
  }

  void _onForgotPassword() {
    Navigator.of(context).pushNamed('/forgot-password');
  }

  Future<void> _onGoogleSignIn() async {
    final authProvider = context.read<AuthProvider>();
    authProvider.clearError();

    FocusScope.of(context).unfocus();

    final success = await authProvider.signInWithGoogle();

    if (!mounted) return;

    if (success) {
      _navigateAfterLogin(authProvider);
    }
  }

  void _onCreateAccount() {
    Navigator.of(context).pushNamed('/register');
  }

  Future<void> _openServerSettings() async {
    final updated = await ServerSettingsSheet.show(context);
    if (updated == true && mounted) {
      context.read<AuthProvider>().clearError();
    }
  }

  Future<void> _retryConnection() async {
    final authProvider = context.read<AuthProvider>();
    authProvider.clearError();
    await ApiConstants.autoDetectBaseUrl();
    if (_formKey.currentState?.validate() == true) {
      _handleSubmit();
    }
  }

  void _triggerBiometric() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'Biometric authentication: Prompting Face ID / Touch ID...',
        ),
        duration: Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final isLoading = authProvider.isLoading;
    final errorMessage = authProvider.errorMessage;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
          onPressed: isLoading ? null : () => Navigator.of(context).pop(),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.dns_rounded),
            tooltip: 'Server Settings',
            onPressed: isLoading ? null : _openServerSettings,
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 2.0),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // 1. Brand Header
                Center(
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const MediConnectLogo(size: 32),
                          const SizedBox(width: 8),
                          const Text(
                            'MediConnect',
                            style: TextStyle(
                              fontSize: 22,
                              fontWeight: FontWeight.w800,
                              color: AppTheme.textPrimary,
                              letterSpacing: -0.4,
                            ),
                          ),
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: AppTheme.primaryContainer,
                              borderRadius: BorderRadius.circular(9999),
                            ),
                            child: const Text(
                              'v2.4',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.primaryBlue,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 2),
                      const Text(
                        'Your Health, Connected in Real-Time',
                        style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 6),

                // 2. Role Selector (Segmented Control)
                Container(
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceContainerLow,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: InkWell(
                          onTap: () {
                            setState(() => _selectedRole = 'patient');
                          },
                          borderRadius: BorderRadius.circular(8),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            decoration: BoxDecoration(
                              color: _selectedRole == 'patient'
                                  ? Colors.white
                                  : Colors.transparent,
                              borderRadius: BorderRadius.circular(8),
                              boxShadow: _selectedRole == 'patient'
                                  ? [
                                      BoxShadow(
                                        color: Colors.black.withValues(
                                          alpha: 0.05,
                                        ),
                                        blurRadius: 4,
                                        offset: const Offset(0, 2),
                                      ),
                                    ]
                                  : null,
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.person_rounded,
                                  size: 18,
                                  color: _selectedRole == 'patient'
                                      ? AppTheme.primaryBlue
                                      : AppTheme.textSecondary,
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  'Patient',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: _selectedRole == 'patient'
                                        ? FontWeight.w700
                                        : FontWeight.w500,
                                    color: _selectedRole == 'patient'
                                        ? AppTheme.primaryBlue
                                        : AppTheme.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      Expanded(
                        child: InkWell(
                          onTap: () {
                            setState(() => _selectedRole = 'doctor');
                          },
                          borderRadius: BorderRadius.circular(8),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            decoration: BoxDecoration(
                              color: _selectedRole == 'doctor'
                                  ? Colors.white
                                  : Colors.transparent,
                              borderRadius: BorderRadius.circular(8),
                              boxShadow: _selectedRole == 'doctor'
                                  ? [
                                      BoxShadow(
                                        color: Colors.black.withValues(
                                          alpha: 0.05,
                                        ),
                                        blurRadius: 4,
                                        offset: const Offset(0, 2),
                                      ),
                                    ]
                                  : null,
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.medical_services_outlined,
                                  size: 18,
                                  color: _selectedRole == 'doctor'
                                      ? AppTheme.primaryBlue
                                      : AppTheme.textSecondary,
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  'Doctor / Specialist',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: _selectedRole == 'doctor'
                                        ? FontWeight.w700
                                        : FontWeight.w500,
                                    color: _selectedRole == 'doctor'
                                        ? AppTheme.primaryBlue
                                        : AppTheme.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 4),

                // Error Banner
                if (errorMessage != null) ...[
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.errorContainer,
                      borderRadius: BorderRadius.circular(10),
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
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                        if (errorMessage.toLowerCase().contains('connect') ||
                            errorMessage.toLowerCase().contains('network'))
                          IconButton(
                            icon: const Icon(
                              Icons.refresh_rounded,
                              size: 18,
                              color: AppTheme.primaryBlue,
                            ),
                            onPressed: _retryConnection,
                            padding: EdgeInsets.zero,
                            constraints: const BoxConstraints(),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 4),
                ],

                // 3. Main Login Form Container
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 10,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.border, width: 1),
                    boxShadow: const [
                      BoxShadow(
                        color: Color.fromRGBO(15, 23, 42, 0.04),
                        blurRadius: 10,
                        offset: Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Email / Identifier Field
                      Text(
                        _selectedRole == 'doctor'
                            ? 'Provider Email or NPI ID'
                            : 'Medical ID, Email or Phone',
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                      const SizedBox(height: 6),
                      TextFormField(
                        key: const Key('login_email_input'),
                        controller: _emailController,
                        enabled: !isLoading,
                        keyboardType: TextInputType.emailAddress,
                        autocorrect: false,
                        textInputAction: TextInputAction.next,
                        decoration: InputDecoration(
                          hintText: _selectedRole == 'doctor'
                              ? 'doctor@hospital.com or NPI'
                              : 'name@domain.com or phone',
                          prefixIcon: const Icon(
                            Icons.alternate_email_rounded,
                            size: 20,
                          ),
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 14,
                          ),
                        ),
                        validator: _validateEmail,
                      ),
                      const SizedBox(height: 4),

                      // Password Field
                      const Text(
                        'Secure Password',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                      const SizedBox(height: 6),
                      TextFormField(
                        key: const Key('login_password_input'),
                        controller: _passwordController,
                        enabled: !isLoading,
                        obscureText: _obscurePassword,
                        textInputAction: TextInputAction.done,
                        onFieldSubmitted: (_) => _handleSubmit(),
                        decoration: InputDecoration(
                          hintText: '••••••••••••',
                          prefixIcon: const Icon(
                            Icons.lock_outline_rounded,
                            size: 20,
                          ),
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
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 14,
                          ),
                        ),
                        validator: _validatePassword,
                      ),
                      const SizedBox(height: 4),

                      // Remember Me & Forgot Password Row
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              SizedBox(
                                width: 24,
                                height: 24,
                                child: Checkbox(
                                  value: _rememberMe,
                                  activeColor: AppTheme.primaryBlue,
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  onChanged: (val) {
                                    setState(() => _rememberMe = val ?? true);
                                  },
                                ),
                              ),
                              const SizedBox(width: 6),
                              const Text(
                                'Remember me',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: AppTheme.textSecondary,
                                ),
                              ),
                            ],
                          ),
                          TextButton(
                            key: const Key('login_forgot_password_button'),
                            onPressed: isLoading ? null : _onForgotPassword,
                            style: TextButton.styleFrom(
                              padding: EdgeInsets.zero,
                              minimumSize: Size.zero,
                              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                            ),
                            child: const Text(
                              'Forgot Password?',
                              style: TextStyle(
                                fontSize: 13,
                                color: AppTheme.secondaryBlue,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Submit Gradient Button
                      Container(
                        height: 48,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(8),
                          gradient: const LinearGradient(
                            colors: [
                              AppTheme.stitchPrimary,
                              AppTheme.primaryBlue,
                            ],
                            begin: Alignment.centerLeft,
                            end: Alignment.centerRight,
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: AppTheme.primaryBlue.withValues(
                                alpha: 0.25,
                              ),
                              blurRadius: 8,
                              offset: const Offset(0, 3),
                            ),
                          ],
                        ),
                        child: ElevatedButton(
                          key: const Key('login_submit_button'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.transparent,
                            shadowColor: Colors.transparent,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                          onPressed: isLoading ? null : _handleSubmit,
                          child: isLoading
                              ? const SizedBox(
                                  height: 20,
                                  width: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    valueColor: AlwaysStoppedAnimation<Color>(
                                      Colors.white,
                                    ),
                                  ),
                                )
                              : const Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Text(
                                      'Sign In to MediConnect',
                                      style: TextStyle(
                                        fontSize: 15,
                                        fontWeight: FontWeight.w700,
                                        color: Colors.white,
                                      ),
                                    ),
                                    SizedBox(width: 8),
                                    Icon(
                                      Icons.arrow_forward_rounded,
                                      size: 18,
                                      color: Colors.white,
                                    ),
                                  ],
                                ),
                        ),
                      ),

                      if (_selectedRole == 'doctor') ...[
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: AppTheme.surfaceContainerLow,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Row(
                            children: [
                              Icon(
                                Icons.verified_user_outlined,
                                size: 18,
                                color: AppTheme.secondaryBlue,
                              ),
                              SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'Practitioner accounts require verified clinical credentials upon sign-in.',
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: AppTheme.textSecondary,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 14),

                // 4. Fast Biometric Login Row
                InkWell(
                  onTap: _triggerBiometric,
                  borderRadius: BorderRadius.circular(14),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 12,
                    ),
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            Container(
                              width: 38,
                              height: 38,
                              decoration: BoxDecoration(
                                color: AppTheme.primaryContainer,
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(
                                Icons.fingerprint_rounded,
                                size: 22,
                                color: AppTheme.primaryBlue,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: const [
                                Text(
                                  'Fast Biometric Login',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    color: AppTheme.textPrimary,
                                  ),
                                ),
                                Text(
                                  'Face ID / Touch ID Verified',
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: AppTheme.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                        const Row(
                          children: [
                            Text(
                              'Tap to scan',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.primaryBlue,
                              ),
                            ),
                            SizedBox(width: 4),
                            Icon(
                              Icons.chevron_right_rounded,
                              size: 18,
                              color: AppTheme.primaryBlue,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // 5. Divider with OR continue with
                Row(
                  children: const [
                    Expanded(child: Divider(color: AppTheme.border)),
                    Padding(
                      padding: EdgeInsets.symmetric(horizontal: 12.0),
                      child: Text(
                        'OR CONTINUE WITH',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.8,
                          color: AppTheme.textMuted,
                        ),
                      ),
                    ),
                    Expanded(child: Divider(color: AppTheme.border)),
                  ],
                ),
                const SizedBox(height: 14),

                // 6. Social Sign In Row
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        key: const Key('login_google_button'),
                        onPressed: isLoading ? null : _onGoogleSignIn,
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AppTheme.textPrimary,
                          backgroundColor: Colors.white,
                          side: const BorderSide(
                            color: AppTheme.border,
                            width: 1,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          minimumSize: const Size(0, 46),
                        ),
                        icon: Image.network(
                          'https://www.gstatic.com/images/branding/product/1x/gsa_512dp.png',
                          width: 18,
                          height: 18,
                          errorBuilder: (context, error, stackTrace) =>
                              const Icon(
                                Icons.g_mobiledata_rounded,
                                size: 22,
                                color: AppTheme.primaryBlue,
                              ),
                        ),
                        label: const Text(
                          'Google',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'Apple ID Sign-In available on iOS devices.',
                              ),
                            ),
                          );
                        },
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AppTheme.textPrimary,
                          backgroundColor: Colors.white,
                          side: const BorderSide(
                            color: AppTheme.border,
                            width: 1,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          minimumSize: const Size(0, 46),
                        ),
                        icon: const Icon(
                          Icons.apple_rounded,
                          size: 20,
                          color: AppTheme.textPrimary,
                        ),
                        label: const Text(
                          'Apple',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),

                // 7. Registration Links
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text(
                      "Don't have an account? ",
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                    GestureDetector(
                      onTap: isLoading ? null : _onCreateAccount,
                      child: const Text(
                        'Register now',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.primaryBlue,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text(
                      'Are you a medical doctor? ',
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                    GestureDetector(
                      key: const Key('login_doctor_register_link'),
                      onTap: isLoading
                          ? null
                          : () =>
                                Navigator.of(context)
                                    .pushNamed('/doctor/register'),
                      child: const Text(
                        'Register as Doctor',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.primaryBlue,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),

                // 8. HIPAA & GDPR Clinical Footer
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: const [
                    Icon(
                      Icons.lock_clock_outlined,
                      size: 14,
                      color: AppTheme.textMuted,
                    ),
                    SizedBox(width: 6),
                    Text(
                      'HIPAA & GDPR End-to-End Encrypted Portal',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                        color: AppTheme.textMuted,
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
