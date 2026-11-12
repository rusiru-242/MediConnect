import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/l10n/app_localizations.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/providers/locale_provider.dart';
import 'package:mediconnect/providers/theme_provider.dart';
import 'package:mediconnect/screens/auth/login_screen.dart';
import 'package:mediconnect/screens/welcome_screen.dart';
import 'package:provider/provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  FlutterSecureStorage.setMockInitialValues({});

  group('LocaleProvider Tests', () {
    setUp(() {
      FlutterSecureStorage.setMockInitialValues({});
    });

    test('Default locale is English', () {
      final provider = LocaleProvider();
      expect(provider.locale.languageCode, 'en');
      expect(provider.currentLanguage, AppLanguage.english);
    });

    test('Switch to Sinhala updates locale and currentLanguage', () async {
      final provider = LocaleProvider();
      await provider.setLocale(const Locale('si'));
      expect(provider.locale.languageCode, 'si');
      expect(provider.currentLanguage, AppLanguage.sinhala);
    });

    test('Switch to Tamil updates locale and currentLanguage', () async {
      final provider = LocaleProvider();
      await provider.setLocale(const Locale('ta'));
      expect(provider.locale.languageCode, 'ta');
      expect(provider.currentLanguage, AppLanguage.tamil);
    });

    test('Unsupported locale is rejected', () async {
      final provider = LocaleProvider();
      await provider.setLocale(const Locale('fr'));
      expect(provider.locale.languageCode, 'en');
    });
  });

  group('Widget Localization & Instant Language Switching Tests', () {
    late LocaleProvider localeProvider;
    late AuthProvider authProvider;
    late ThemeProvider themeProvider;

    setUp(() {
      FlutterSecureStorage.setMockInitialValues({});
      localeProvider = LocaleProvider();
      authProvider = AuthProvider();
      themeProvider = ThemeProvider();
    });

    Widget createTestApp(Widget child) {
      return MultiProvider(
        providers: [
          ChangeNotifierProvider<LocaleProvider>.value(value: localeProvider),
          ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
          ChangeNotifierProvider<ThemeProvider>.value(value: themeProvider),
        ],
        child: Consumer<LocaleProvider>(
          builder: (context, locProvider, _) => MaterialApp(
            locale: locProvider.locale,
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: child,
          ),
        ),
      );
    }

    testWidgets('WelcomeScreen renders English and switches immediately to Sinhala and Tamil', (tester) async {
      await tester.pumpWidget(createTestApp(const WelcomeScreen()));
      await tester.pumpAndSettle();

      // 1. English verification
      expect(find.text('Login'), findsOneWidget);
      expect(find.text('Create Account'), findsOneWidget);
      expect(find.text('Choose Your Language'), findsOneWidget);

      // 2. Tap Sinhala chip on WelcomeLanguageBar
      await tester.tap(find.text('සිංහල'));
      await tester.pumpAndSettle();

      expect(localeProvider.locale.languageCode, 'si');
      expect(find.text('පිවිසෙන්න'), findsOneWidget);
      expect(find.text('ගිණුමක් සාදන්න'), findsOneWidget);
      expect(find.text('ඔබගේ භාෂාව තෝරන්න'), findsOneWidget);

      // 3. Tap Tamil chip on WelcomeLanguageBar
      await tester.tap(find.text('தமிழ்'));
      await tester.pumpAndSettle();

      expect(localeProvider.locale.languageCode, 'ta');
      expect(find.text('உள்நுழைக'), findsOneWidget);
      expect(find.text('கணக்கை உருவாக்கவும்'), findsOneWidget);
      expect(find.text('உங்கள் மொழியைத் தேர்ந்தெடுக்கவும்'), findsOneWidget);
    });

    testWidgets('LoginScreen renders English and updates instantaneously when language changes', (tester) async {
      await tester.pumpWidget(createTestApp(const LoginScreen()));
      await tester.pumpAndSettle();

      // Initial English
      expect(find.text('Patient'), findsOneWidget);
      expect(find.text('Doctor'), findsOneWidget);
      expect(find.text('Forgot Password?'), findsOneWidget);

      // Change to Sinhala via provider
      await localeProvider.setLocale(const Locale('si'));
      await tester.pumpAndSettle();

      expect(find.text('රෝගියා'), findsOneWidget);
      expect(find.text('වෛද්‍යවරයා'), findsOneWidget);
      expect(find.text('මුරපදය අමතකද?'), findsOneWidget);

      // Change to Tamil via provider
      await localeProvider.setLocale(const Locale('ta'));
      await tester.pumpAndSettle();

      expect(find.text('நோயாளி'), findsOneWidget);
      expect(find.text('மருத்துவர்'), findsOneWidget);
      expect(find.text('கடவுச்சொல் மறந்துவிட்டதா?'), findsOneWidget);
    });
  });
}
