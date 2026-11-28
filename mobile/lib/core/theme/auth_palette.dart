import 'package:flutter/material.dart';

import 'app_theme.dart';

/// R02 (R01-O2): colours for the welcome and login screens that follow the active theme.
///
/// Those screens used fixed light-theme colours while their buttons and chips followed the dark theme, so in dark
/// mode the background stayed light and the outlined "Create Account" text became unreadable. Every colour here
/// comes from the existing design tokens in [AppTheme]; semantic colours (errors, success) are unchanged.
class AuthPalette {
  final bool dark;

  const AuthPalette._(this.dark);

  factory AuthPalette.of(BuildContext context) => AuthPalette._(Theme.of(context).brightness == Brightness.dark);

  Color get background => dark ? AppTheme.darkBackground : AppTheme.background;
  Color get card => dark ? AppTheme.darkSurface : Colors.white;
  Color get surfaceLow => dark ? AppTheme.darkSurfaceContainerLow : AppTheme.surfaceContainerLow;
  Color get border => dark ? AppTheme.darkBorder : AppTheme.border;
  Color get textPrimary => dark ? AppTheme.darkTextPrimary : AppTheme.textPrimary;
  Color get textSecondary => dark ? AppTheme.darkTextSecondary : AppTheme.textSecondary;
  Color get textMuted => dark ? AppTheme.darkTextSecondary : AppTheme.textMuted;

  /// Brand blue for text and icons; the lighter variant keeps contrast on the dark background.
  Color get accent => dark ? AppTheme.darkPrimaryBlue : AppTheme.primary;
}
