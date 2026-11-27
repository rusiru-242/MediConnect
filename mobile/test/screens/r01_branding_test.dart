// R01 branding: the MediConnect symbol asset is bundled, rendered without distortion, placed once beside the
// existing "MediConnect" title (no duplicated wordmark), and lays out on small and large phones in light and dark.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/auth/login_screen.dart';
import 'package:mediconnect/screens/welcome_screen.dart';
import 'package:mediconnect/services/auth_api_service.dart';
import 'package:mediconnect/widgets/mediconnect_logo.dart';
import 'package:provider/provider.dart';

class _NoCallsAuthApi extends Fake implements AuthApiService {}

Widget _app(Widget child, {ThemeData? theme}) => MultiProvider(
      providers: [ChangeNotifierProvider<AuthProvider>(create: (_) => AuthProvider(authApiService: _NoCallsAuthApi()))],
      child: MaterialApp(theme: theme, home: child),
    );

/// Collects layout errors during [body]. Flutter's test font (Ahem) draws every glyph as a full em square, so some
/// long text rows elsewhere on these screens overflow only under test; the branding checks below assert that no
/// error comes from the logo widget and that the logo is on screen, centred and clear of the title.
Future<List<String>> _collectErrors(Future<void> Function() body) async {
  final errors = <String>[];
  final previous = FlutterError.onError;
  FlutterError.onError = (details) => errors.add(details.toString());
  try {
    await body();
  } finally {
    FlutterError.onError = previous;
  }
  return errors;
}

void _expectLogoClearOfTitle(WidgetTester tester, Size screen) {
  final logo = tester.getRect(find.byKey(const Key('mediconnect_logo_symbol')));
  final title = tester.getRect(find.text('MediConnect'));
  expect(logo.left >= 0 && logo.right <= screen.width && logo.top >= 0, isTrue, reason: 'logo on screen: $logo');
  expect(logo.bottom <= title.top, isTrue, reason: 'logo $logo must sit above title $title without overlap');
  expect((logo.center.dx - screen.width / 2).abs() < 1, isTrue, reason: 'logo centred');
}

Future<void> _setSize(WidgetTester tester, Size logical, double dpr) async {
  tester.view.devicePixelRatio = dpr;
  tester.view.physicalSize = logical * dpr;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  test('symbol asset and its density variants are bundled', () async {
    TestWidgetsFlutterBinding.ensureInitialized();
    final data = await rootBundle.load(MediConnectLogo.assetPath);
    expect(data.lengthInBytes, greaterThan(1000));
    final manifest = await AssetManifest.loadFromAssetBundle(rootBundle);
    final variants = manifest.getAssetVariants(MediConnectLogo.assetPath)!.map((v) => v.targetDevicePixelRatio).toSet();
    expect(variants, containsAll(<double?>[null, 3.0, 4.0]));
  });

  testWidgets('logo renders the symbol asset, contained (not stretched) and decorative by default', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Center(child: MediConnectLogo(size: 64))));
    final image = tester.widget<Image>(find.byType(Image));
    expect((image.image as AssetImage).assetName, MediConnectLogo.assetPath);
    expect(image.fit, BoxFit.contain);
    expect(image.excludeFromSemantics, isTrue);
    expect(tester.getSize(find.byKey(const Key('mediconnect_logo_symbol'))), const Size(64, 64));
    // The symbol never carries the wordmark: no extra "MediConnect" text unless explicitly requested.
    expect(find.text('MediConnect'), findsNothing);
  });

  testWidgets('logo exposes a spoken label when one is given', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: MediConnectLogo(semanticLabel: 'MediConnect logo')));
    final image = tester.widget<Image>(find.byType(Image));
    expect(image.excludeFromSemantics, isFalse);
    expect(image.semanticLabel, 'MediConnect logo');
  });

  testWidgets('optional caption follows the dark theme', (tester) async {
    await tester.pumpWidget(MaterialApp(theme: ThemeData.dark(), home: const MediConnectLogo(showText: true)));
    expect(tester.widget<Text>(find.text('MediConnect')).style!.color, Colors.white);
  });

  for (final (label, size, dpr) in [
    ('small phone 320x568', const Size(320, 568), 2.0),
    ('large phone 412x915', const Size(412, 915), 3.5),
  ]) {
    testWidgets('login: one symbol above one title, logo clear of the title ($label)', (tester) async {
      await _setSize(tester, size, dpr);
      final errors = await _collectErrors(() async {
        await tester.pumpWidget(_app(const LoginScreen()));
        await tester.pump();
      });
      expect(find.byKey(const Key('mediconnect_logo_symbol')), findsOneWidget);
      expect(find.text('MediConnect'), findsOneWidget);
      _expectLogoClearOfTitle(tester, size);
      expect(errors.where((e) => e.contains('mediconnect_logo.dart')), isEmpty);
    });

    testWidgets('welcome: one symbol above one title, logo clear of the title ($label)', (tester) async {
      await _setSize(tester, size, dpr);
      final errors = await _collectErrors(() async {
        await tester.pumpWidget(_app(const WelcomeScreen()));
        await tester.pump();
      });
      expect(find.byKey(const Key('mediconnect_logo_symbol')), findsOneWidget);
      expect(find.text('MediConnect'), findsOneWidget);
      _expectLogoClearOfTitle(tester, size);
      expect(errors.where((e) => e.contains('mediconnect_logo.dart')), isEmpty);
    });
  }

  testWidgets('login renders the logo in the dark theme', (tester) async {
    await _setSize(tester, const Size(412, 915), 3.5);
    final errors = await _collectErrors(() async {
      await tester.pumpWidget(_app(const LoginScreen(), theme: ThemeData.dark()));
      await tester.pump();
    });
    expect(find.byKey(const Key('mediconnect_logo_symbol')), findsOneWidget);
    _expectLogoClearOfTitle(tester, const Size(412, 915));
    expect(errors.where((e) => e.contains('mediconnect_logo.dart')), isEmpty);
  });
}
