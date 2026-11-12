import 'package:flutter/material.dart';
import '../core/storage/secure_storage_service.dart';

/// Supported application locales for MediConnect.
enum AppLanguage {
  english('en', 'English'),
  sinhala('si', 'සිංහල'),
  tamil('ta', 'தமிழ்');

  final String code;
  final String displayName;

  const AppLanguage(this.code, this.displayName);

  static AppLanguage fromCode(String? code) {
    switch (code) {
      case 'si':
        return AppLanguage.sinhala;
      case 'ta':
        return AppLanguage.tamil;
      case 'en':
      default:
        return AppLanguage.english;
    }
  }

  Locale get locale => Locale(code);
}

/// Provider managing active application Locale and local persistence.
class LocaleProvider extends ChangeNotifier {
  final SecureStorageService _storage;
  Locale _locale = const Locale('en');
  bool _hasUserSetLocale = false;

  static const List<Locale> supportedLocales = [
    Locale('en'),
    Locale('si'),
    Locale('ta'),
  ];

  LocaleProvider({SecureStorageService? storage})
      : _storage = storage ?? SecureStorageService() {
    _loadLocale();
  }

  Locale get locale => _locale;
  AppLanguage get currentLanguage => AppLanguage.fromCode(_locale.languageCode);

  Future<void> _loadLocale() async {
    try {
      final savedCode = await _storage.getLocale();
      if (_hasUserSetLocale) return;
      if (savedCode != null && (savedCode == 'en' || savedCode == 'si' || savedCode == 'ta')) {
        _locale = Locale(savedCode);
        notifyListeners();
        return;
      }
      // If no saved locale, match platform dispatcher if supported
      final systemLocale = WidgetsBinding.instance.platformDispatcher.locale;
      if (systemLocale.languageCode == 'si' || systemLocale.languageCode == 'ta') {
        _locale = Locale(systemLocale.languageCode);
        notifyListeners();
        return;
      }
    } catch (_) {
      // Fallback to English
    }
    if (!_hasUserSetLocale) {
      _locale = const Locale('en');
      notifyListeners();
    }
  }

  Future<void> setLocale(Locale newLocale) async {
    if (!['en', 'si', 'ta'].contains(newLocale.languageCode)) {
      return;
    }
    _hasUserSetLocale = true;
    if (_locale.languageCode == newLocale.languageCode) {
      return;
    }
    _locale = newLocale;
    notifyListeners();
    try {
      await _storage.saveLocale(newLocale.languageCode);
    } catch (_) {}
  }

  Future<void> setLanguage(AppLanguage language) async {
    await setLocale(language.locale);
  }
}
