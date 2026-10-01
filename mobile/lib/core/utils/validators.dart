/// Reusable form input validation rules for MediConnect.
class Validators {
  Validators._();

  /// Validates full name input
  static String? validateFullName(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Full name is required.';
    }
    final trimmed = value.trim();
    if (trimmed.length < 2) {
      return 'Full name must be at least 2 characters long.';
    }
    if (trimmed.length > 100) {
      return 'Full name cannot exceed 100 characters.';
    }
    return null;
  }

  /// Validates email address format
  static String? validateEmail(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Email address is required.';
    }
    final trimmed = value.trim();

    // Check basic email structure with single '@'
    final atIndex = trimmed.indexOf('@');
    if (atIndex <= 0 || atIndex != trimmed.lastIndexOf('@') || atIndex == trimmed.length - 1) {
      return 'Please enter a valid email address.';
    }

    final localPart = trimmed.substring(0, atIndex);
    final domainPart = trimmed.substring(atIndex + 1);

    // Disallow leading, trailing, or consecutive dots in local or domain parts
    if (localPart.startsWith('.') ||
        localPart.endsWith('.') ||
        localPart.contains('..') ||
        domainPart.startsWith('.') ||
        domainPart.endsWith('.') ||
        domainPart.contains('..')) {
      return 'Please enter a valid email address.';
    }

    final localRegex = RegExp(r'^[a-zA-Z0-9.!#$%&’*+/=?^_`{|}~-]+$');
    final domainRegex = RegExp(r'^[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$');

    if (!localRegex.hasMatch(localPart) || !domainRegex.hasMatch(domainPart)) {
      return 'Please enter a valid email address.';
    }

    return null;
  }

  /// Validates Sri Lankan mobile phone numbers (e.g. 0771234567, +94771234567, 94771234567)
  static String? validatePhone(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Phone number is required.';
    }
    final cleanPhone = value.replaceAll(RegExp(r'[\s\-()]'), '');
    final phoneRegex = RegExp(r'^(?:\+94|0094|94|0)7[0-8]\d{7}$');

    if (!phoneRegex.hasMatch(cleanPhone)) {
      return 'Enter a valid Sri Lankan mobile number (e.g. 0771234567).';
    }
    return null;
  }

  /// Validates strong password according to MediConnect security policy
  static String? validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Password is required.';
    }
    if (value.length < 8) {
      return 'Password must be at least 8 characters long.';
    }
    if (!RegExp(r'[A-Z]').hasMatch(value)) {
      return 'Password must contain at least one uppercase letter.';
    }
    if (!RegExp(r'[a-z]').hasMatch(value)) {
      return 'Password must contain at least one lowercase letter.';
    }
    if (!RegExp(r'\d').hasMatch(value)) {
      return 'Password must contain at least one number.';
    }
    if (!RegExp(r'[^A-Za-z0-9]').hasMatch(value)) {
      return 'Password must contain at least one special character.';
    }
    return null;
  }

  /// Validates that confirm password matches original password
  static String? validateConfirmPassword(String? value, String password) {
    if (value == null || value.isEmpty) {
      return 'Please confirm your password.';
    }
    if (value != password) {
      return 'Passwords do not match.';
    }
    return null;
  }

  /// Validates 6-digit numeric OTP code
  static String? validateOtp(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Verification code is required.';
    }
    final trimmed = value.trim();
    if (!RegExp(r'^\d{6}$').hasMatch(trimmed)) {
      return 'Verification code must be exactly 6 digits.';
    }
    return null;
  }
}
