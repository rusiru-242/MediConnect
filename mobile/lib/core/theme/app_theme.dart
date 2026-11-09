import 'package:flutter/material.dart';

/// Centralized theme definitions for MediConnect.
/// Unified Modern Medical Professional Blue Design System (Phase 38).
class AppTheme {
  AppTheme._();

  // Core Brand Tokens (Phase 38 Unified Medical Design System & Stitch Clinical Clarity)
  static const Color primaryBlue = Color(0xFF1565C0); // Primary Blue #1565C0
  static const Color stitchPrimary = Color(
    0xFF004D99,
  ); // Deep Clinical Blue #004D99
  static const Color primary = primaryBlue;
  static const Color primaryTeal = primaryBlue; // Backwards-compatibility alias
  static const Color secondaryBlue = Color(
    0xFF2196F3,
  ); // Secondary Blue #2196F3
  static const Color stitchSecondary = Color(
    0xFF0061A4,
  ); // Clinical Secondary #0061A4
  static const Color secondary = secondaryBlue;
  static const Color darkNavy = Color(0xFF172B4D); // Dark Navy #172B4D

  // Surfaces & Layout (Stitch Clinical Clarity)
  static const Color background = Color(0xFFFAF8FF); // Clinical Canvas #FAF8FF
  static const Color surface = Color(0xFFFFFFFF); // Surface / Cards #FFFFFF
  static const Color surfaceContainerLowest = Color(0xFFFFFFFF);
  static const Color surfaceContainerLow = Color(
    0xFFF2F3FF,
  ); // Light cool blue-gray
  static const Color surfaceContainer = Color(0xFFEAEDFF); // Soft container
  static const Color surfaceContainerHigh = Color(0xFFE2E7FF);
  static const Color surfaceContainerHighest = Color(0xFFDAE2FD);
  static const Color surfaceVariant = Color(0xFFEAEDFF);
  static const Color border = Color(
    0xFFE2E8F0,
  ); // Precise Slate Outline #E2E8F0
  static const Color outline = border;
  static const Color outlineVariant = Color(0xFFC2C6D4);
  static const Color borderFocused = primaryBlue;

  // Typography & Text (Stitch Clinical Clarity)
  static const Color textPrimary = Color(0xFF131B2E); // On-Surface #131B2E
  static const Color onSurface = textPrimary;
  static const Color textSecondary = Color(
    0xFF424752,
  ); // On-Surface-Variant #424752
  static const Color onSurfaceVariant = textSecondary;
  static const Color textMuted = Color(0xFF727783); // Outline Muted #727783

  // Semantic Feedback Tokens (Stitch Clinical Clarity)
  static const Color success = Color(0xFF10B981); // Health Green #10B981
  static const Color stitchTertiary = Color(0xFF005A3C);
  static const Color stitchTertiaryFixed = Color(0xFF6FFBBE);
  static const Color stitchTertiaryFixedDim = Color(0xFF4EDEA3);
  static const Color successContainer = Color(
    0xFFE8F8F2,
  ); // Stable / Normal #E8F8F2
  static const Color warning = Color(0xFFF59E0B); // Warning #F59E0B
  static const Color warningContainer = Color(0xFFFEF3C7);
  static const Color error = Color(0xFFBA1A1A); // Clinical Error #BA1A1A
  static const Color errorContainer = Color(0xFFFFDAD6);

  // Tinted Containers & Accent Shades
  static const Color primaryContainer = Color(
    0xFFE3F2FD,
  ); // Soft Ice Blue #E3F2FD
  static const Color onPrimaryContainer = Color(
    0xFF004D99,
  ); // Deep Blue #004D99
  static const Color secondaryContainer = Color(0xFFD1E4FF);
  static const Color onSecondaryContainer = Color(0xFF00355C);
  static const Color primaryLight = Color(0xFF42A5F5); // Blue 400
  static const Color primaryDark = Color(0xFF004D99);

  // Shared Gradients (Stitch Clinical Clarity)
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [stitchPrimary, primaryBlue, secondaryBlue],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient heroGradient = LinearGradient(
    colors: [stitchPrimary, primaryBlue, secondaryBlue],
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
          textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 16,
        ),
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
