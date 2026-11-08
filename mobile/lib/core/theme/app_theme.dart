import 'package:flutter/material.dart';

/// Centralized theme definitions for MediConnect.
/// Unified Modern Medical Professional Blue Design System (Phase 38).
class AppTheme {
  AppTheme._();

  // Core Brand Tokens (Phase 38 Unified Medical Design System)
  static const Color primaryBlue = Color(0xFF1565C0); // Primary Blue #1565C0
  static const Color primary = primaryBlue;
  static const Color primaryTeal = primaryBlue; // Backwards-compatibility alias
  static const Color secondaryBlue = Color(0xFF2196F3); // Secondary Blue #2196F3
  static const Color secondary = secondaryBlue;
  static const Color darkNavy = Color(0xFF172B4D); // Dark Navy #172B4D

  // Surfaces & Layout
  static const Color background = Color(0xFFF5F8FC); // Background #F5F8FC
  static const Color surface = Color(0xFFFFFFFF); // Surface / Cards #FFFFFF
  static const Color surfaceVariant = Color(0xFFEDF2F7); // Subtle surface tint
  static const Color border = Color(0xFFE5EAF2); // Border #E5EAF2
  static const Color outline = border;
  static const Color borderFocused = primaryBlue;

  // Typography & Text
  static const Color textPrimary = Color(0xFF172B4D); // Dark Navy text #172B4D
  static const Color textSecondary = Color(0xFF64748B); // Secondary Text #64748B
  static const Color textMuted = Color(0xFF94A3B8); // Slate 400

  // Semantic Feedback Tokens
  static const Color success = Color(0xFF16A34A); // Success #16A34A
  static const Color successContainer = Color(0xFFDCFCE7);
  static const Color warning = Color(0xFFF59E0B); // Warning #F59E0B
  static const Color warningContainer = Color(0xFFFEF3C7);
  static const Color error = Color(0xFFDC2626); // Error #DC2626
  static const Color errorContainer = Color(0xFFFEE2E2);

  // Tinted Containers & Accent Shades
  static const Color primaryContainer = Color(0xFFE3F2FD); // Blue 50
  static const Color onPrimaryContainer = Color(0xFF0D47A1); // Deep Blue 900
  static const Color secondaryContainer = Color(0xFFE1F5FE); // Light Blue 50
  static const Color onSecondaryContainer = Color(0xFF0277BD); // Light Blue 800
  static const Color primaryLight = Color(0xFF42A5F5); // Blue 400
  static const Color primaryDark = Color(0xFF0D47A1); // Blue 900

  // Shared Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [primaryBlue, secondaryBlue],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient heroGradient = LinearGradient(
    colors: [darkNavy, primaryBlue],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient cardGradient = LinearGradient(
    colors: [Color(0xFFFFFFFF), Color(0xFFF8FAFC)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  /// Light Theme Definition
  static ThemeData get lightTheme {
    final colorScheme = ColorScheme.light(
      primary: primaryBlue,
      onPrimary: Colors.white,
      primaryContainer: primaryContainer,
      onPrimaryContainer: onPrimaryContainer,
      secondary: secondaryBlue,
      onSecondary: Colors.white,
      secondaryContainer: secondaryContainer,
      onSecondaryContainer: onSecondaryContainer,
      surface: surface,
      onSurface: textPrimary,
      error: error,
      onError: Colors.white,
      errorContainer: errorContainer,
      onErrorContainer: const Color(0xFF991B1B),
      outline: border,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: background,
      fontFamily: 'Roboto', // Fallback standard font
      appBarTheme: const AppBarTheme(
        backgroundColor: surface,
        foregroundColor: textPrimary,
        elevation: 0,
        centerTitle: true,
        scrolledUnderElevation: 0.5,
        titleTextStyle: TextStyle(
          color: textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.2,
        ),
        iconTheme: IconThemeData(color: textPrimary),
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: border, width: 1),
        ),
        margin: EdgeInsets.zero,
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: surface,
        selectedItemColor: primaryBlue,
        unselectedItemColor: textSecondary,
        type: BottomNavigationBarType.fixed,
        elevation: 8,
        selectedLabelStyle: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryBlue,
          foregroundColor: Colors.white,
          elevation: 0,
          minimumSize: const Size(double.infinity, 52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.2,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          side: const BorderSide(color: border, width: 1.5),
          minimumSize: const Size(double.infinity, 52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.2,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: primaryBlue,
          textStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        hintStyle: const TextStyle(
          color: textMuted,
          fontSize: 15,
          fontWeight: FontWeight.w400,
        ),
        labelStyle: const TextStyle(
          color: textSecondary,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        prefixIconColor: textSecondary,
        suffixIconColor: textSecondary,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: border, width: 1.5),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: border, width: 1.5),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: primaryBlue, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: error, width: 1.5),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: error, width: 2),
        ),
        errorStyle: const TextStyle(
          color: error,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: border,
        thickness: 1,
        space: 24,
      ),
    );
  }
}
