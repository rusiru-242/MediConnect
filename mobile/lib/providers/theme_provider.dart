import 'package:flutter/material.dart';
import '../core/storage/secure_storage_service.dart';

/// Provider for managing and persisting the application ThemeMode (Light / Dark / System).
class ThemeProvider extends ChangeNotifier {
  final SecureStorageService _storage;
  ThemeMode _themeMode = ThemeMode.light;

  ThemeProvider({SecureStorageService? storage})
      : _storage = storage ?? SecureStorageService() {
    _loadThemeMode();
  }

  ThemeMode get themeMode => _themeMode;

  bool isDark(BuildContext context) {
    if (_themeMode == ThemeMode.dark) return true;
    if (_themeMode == ThemeMode.light) return false;
    return MediaQuery.platformBrightnessOf(context) == Brightness.dark;
  }

  Future<void> _loadThemeMode() async {
    try {
      final saved = await _storage.getThemeMode();
      if (saved == 'dark') {
        _themeMode = ThemeMode.dark;
        notifyListeners();
      } else if (saved == 'system') {
        _themeMode = ThemeMode.system;
        notifyListeners();
      } else if (saved == 'light') {
        _themeMode = ThemeMode.light;
        notifyListeners();
      }
    } catch (_) {
      // Default to light
    }
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    _themeMode = mode;
    notifyListeners();
    String modeString;
    switch (mode) {
      case ThemeMode.dark:
        modeString = 'dark';
        break;
      case ThemeMode.light:
        modeString = 'light';
        break;
      case ThemeMode.system:
        modeString = 'system';
        break;
    }
    try {
      await _storage.saveThemeMode(modeString);
    } catch (_) {}
  }

  Future<void> toggleTheme([BuildContext? context]) async {
    if (context != null) {
      final currentlyDark = isDark(context);
      await setThemeMode(currentlyDark ? ThemeMode.light : ThemeMode.dark);
    } else {
      await setThemeMode(
        _themeMode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark,
      );
    }
  }
}
