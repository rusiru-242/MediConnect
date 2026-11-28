// R02: profile data integrity (A05-O1), profile picture management, avatar caching and isolation,
// responsive patient navigation (R01-O1) and dark-mode authentication screens (R01-O2).
// Synthetic data only; no network (fake services and an injected avatar fetch).
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:mediconnect/core/network/api_client.dart';
import 'package:mediconnect/core/theme/app_theme.dart';
import 'package:mediconnect/models/appointment.dart';
import 'package:mediconnect/models/auth_session.dart';
import 'package:mediconnect/models/patient_profile.dart';
import 'package:mediconnect/models/user_model.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/auth/login_screen.dart';
import 'package:mediconnect/screens/patient/edit_patient_profile_screen.dart';
import 'package:mediconnect/screens/patient/patient_home_screen.dart';
import 'package:mediconnect/screens/patient/patient_profile_screen.dart';
import 'package:mediconnect/screens/welcome_screen.dart';
import 'package:mediconnect/widgets/profile_picture_editor.dart';
import 'package:mediconnect/widgets/user_avatar.dart';
import 'package:provider/provider.dart';

import '../helpers/fake_profile_service.dart';
import 'doctor_discovery_availability_test.dart' show MockAuthApiService, createTestApp;

final Uint8List _png = base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAACgAAAAUCAIAAABwJOjsAAAAP0lEQVR4nO3NMRUAIAzE0HJCKguRKEEWcxk7hIH7e17GzoyuGavdKh6RxxRhp4vHGHGrymOMuFXlMUbcKj4fH5W/AizMkkF7AAAAAElFTkSuQmCC');

class _FakePicker extends Fake implements ImagePicker {
  final Future<XFile?> Function(ImageSource) onPick;
  _FakePicker(this.onPick);

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) =>
      onPick(source);
}

AuthProvider _auth({String role = 'PATIENT', String? image}) {
  final provider = AuthProvider(authApiService: MockAuthApiService());
  provider.setSessionForTesting(AuthSession(
    message: 'ok', accessToken: 't', refreshToken: 'r', expiresIn: 3600,
    user: UserModel(id: 'PAT-1', fullName: 'Jane Doe', email: 'jane@example.com', role: role, emailVerified: true,
        accountStatus: 'ACTIVE', createdAt: DateTime.now(), profileImage: image),
  ));
  return provider;
}

Widget _profileApp(FakeProfileService service, AuthProvider auth) => MultiProvider(
      providers: [ChangeNotifierProvider<AuthProvider>.value(value: auth)],
      child: MaterialApp(theme: AppTheme.lightTheme, home: PatientProfileScreen(service: service)),
    );

const _fabricated = ['Penicillin', 'MEDICONNECT PASS', 'BlueCross MediConnect', '#MC-88392', '#9482-108',
  '28 yrs • Female • Blood Type: O+', 'Emergency Contact: Spouse', 'ACTIVE TIER 1', '170 cm', 'lbs (Stable)',
  '+94 77 123 4567', 'Updated 3 days ago • Full history', '2 current medications'];

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    AvatarCache.clear();
    AvatarCache.fetchOverride = null;
  });

  group('R02-P profile data integrity (A05-O1)', () {
    testWidgets('P01-P06: an empty profile shows "Not provided" and none of the old invented values', (tester) async {
      await tester.pumpWidget(_profileApp(FakeProfileService(), _auth()));
      await tester.pumpAndSettle();
      for (final key in ['stat_height', 'stat_weight', 'stat_bmi']) {
        expect(find.descendant(of: find.byKey(Key(key)), matching: find.text('Not provided')), findsOneWidget, reason: key);
      }
      expect(find.text('Reported by you: Not provided'), findsOneWidget);
      expect(find.byKey(const Key('emergency_not_provided')), findsOneWidget);
      expect(find.byKey(const Key('stat_bmi_note')), findsNothing);
      for (final text in _fabricated) {
        expect(find.textContaining(text), findsNothing, reason: text);
      }
    });

    testWidgets('P03/P04: real values, BMI with its note, explicit "No known allergies" and recorded allergies',
        (tester) async {
      final service = FakeProfileService(profile: PatientProfile.fromJson({
        'fullName': 'Jane Doe',
        'healthProfile': {'heightCm': 170, 'weightKg': 65, 'bmi': 22.5, 'bmiNote': 'Calculated ... not a diagnosis.',
          'allergyStatus': 'none_known', 'allergies': [],
          'emergencyContact': {'name': 'Synthetic Contact', 'relationship': 'Sibling', 'phone': '+94 71 000 0000'}},
        'recordedAllergies': [{'allergen': 'Sulfonamides', 'severity': 'moderate', 'sourceLabel': 'Recorded by a clinician',
          'clinicalDate': '2026-11-01'}],
      }));
      await tester.pumpWidget(_profileApp(service, _auth()));
      await tester.pumpAndSettle();
      expect(find.text('170 cm'), findsOneWidget);
      expect(find.text('65 kg'), findsOneWidget);
      expect(find.text('22.5'), findsOneWidget);
      expect(find.byKey(const Key('stat_bmi_note')), findsOneWidget);
      expect(find.text('Normal'), findsNothing); // no BMI category or diagnosis
      expect(find.text('Reported by you: No known allergies'), findsOneWidget);
      expect(find.textContaining('Sulfonamides (moderate) - Recorded by a clinician'), findsOneWidget);
      expect(find.text('Synthetic Contact (Sibling)'), findsOneWidget);
      expect(find.textContaining('Penicillin'), findsNothing);
    });

    testWidgets('a failed load is reported truthfully and can be retried', (tester) async {
      final service = FakeProfileService()..failLoad = true;
      await tester.pumpWidget(_profileApp(service, _auth()));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('profile_error')), findsOneWidget);
      expect(find.text('Not provided'), findsNothing); // no values are guessed while unknown
      service.failLoad = false;
      await tester.tap(find.byKey(const Key('profile_retry')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('stat_height')), findsOneWidget);
    });

    testWidgets('P07/P08: the edit form validates and sends only changed fields', (tester) async {
      final service = FakeProfileService();
      PatientProfile? result;
      await tester.pumpWidget(MaterialApp(home: Builder(builder: (context) => TextButton(
            onPressed: () async => result = await Navigator.of(context).push<PatientProfile>(MaterialPageRoute(
                builder: (_) => EditPatientProfileScreen(profile: service.profile, service: service))),
            child: const Text('open'),
          ))));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('edit_height')), '20');
      await tester.tap(find.byKey(const Key('allergy_has')));
      await tester.pump();
      await tester.ensureVisible(find.byKey(const Key('edit_save')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('edit_save')));
      await tester.pumpAndSettle();
      expect(find.text('Height must be between 50 and 250'), findsOneWidget);
      expect(find.text('List at least one allergy'), findsOneWidget);
      expect(service.lastChanges, isNull); // nothing sent while invalid
      await tester.ensureVisible(find.byKey(const Key('edit_height')));
      await tester.enterText(find.byKey(const Key('edit_height')), '170');
      await tester.ensureVisible(find.byKey(const Key('edit_allergies')));
      await tester.enterText(find.byKey(const Key('edit_allergies')), 'Latex, Peanuts');
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pumpAndSettle();
      // Invoke Save directly: with the test keyboard open the scroll position can leave the button outside the
      // hit-test area of the 800x600 test window (the first Save above is a real tap).
      tester.widget<FilledButton>(find.byKey(const Key('edit_save'))).onPressed!();
      await tester.pumpAndSettle();
      expect(service.lastChanges, {'heightCm': 170.0, 'allergyStatus': 'has_allergies', 'allergies': ['Latex', 'Peanuts']});
      expect(result?.heightCm, 170);
    });
  });

  group('R02-I profile picture', () {
    testWidgets('I07/I24: no picture, or an unavailable one, shows the neutral default avatar', (tester) async {
      AvatarCache.fetchOverride = (_) async => throw Exception('404');
      await tester.pumpWidget(const MaterialApp(home: Column(children: [
        UserAvatar(key: Key('a'), imageUrl: null, size: 40, fallback: Icon(Icons.person, key: Key('fb_a'))),
        UserAvatar(key: Key('b'), imageUrl: '/api/profile/pictures/X?v=1', size: 40, fallback: Icon(Icons.person, key: Key('fb_b'))),
        UserAvatar(key: Key('c'), imageUrl: 'javascript:alert(1)', size: 40, fallback: Icon(Icons.person, key: Key('fb_c'))),
      ])));
      await tester.pumpAndSettle();
      for (final k in ['fb_a', 'fb_b', 'fb_c']) {
        expect(find.byKey(Key(k)), findsOneWidget, reason: k);
      }
      expect(tester.takeException(), isNull);
    });

    testWidgets('I04/I19: an API picture is fetched with the session; a new version is fetched again', (tester) async {
      final fetched = <String>[];
      AvatarCache.fetchOverride = (endpoint) async {
        fetched.add(endpoint);
        return _png;
      };
      Widget avatar(String url) => MaterialApp(
          home: UserAvatar(imageUrl: url, size: 40, fallback: const Icon(Icons.person, key: Key('fb'))));
      await tester.pumpWidget(avatar('/api/profile/pictures/PAT-1?v=1'));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('avatar_image_/api/profile/pictures/PAT-1?v=1')), findsOneWidget);
      await tester.pumpWidget(avatar('/api/profile/pictures/PAT-1?v=1'));
      await tester.pumpAndSettle();
      expect(fetched, ['/profile/pictures/PAT-1?v=1']); // cached
      await tester.pumpWidget(avatar('/api/profile/pictures/PAT-1?v=2'));
      await tester.pumpAndSettle();
      expect(fetched, ['/profile/pictures/PAT-1?v=1', '/profile/pictures/PAT-1?v=2']); // replacement -> new bytes
    });

    test('I20: logout/login clears cached private pictures (account switching)', () async {
      TestWidgetsFlutterBinding.ensureInitialized();
      AvatarCache.fetchOverride = (_) async => _png;
      await AvatarCache.load('/api/profile/pictures/A?v=1', ApiClient());
      expect(AvatarCache.peek('/api/profile/pictures/A?v=1'), isNotNull);
      final auth = _auth();
      await auth.logout();
      expect(AvatarCache.peek('/api/profile/pictures/A?v=1'), isNull);
    });

    testWidgets('I21: cancelling the sheet or the picker changes nothing', (tester) async {
      final service = FakeProfileService();
      var changes = 0;
      ProfilePictureEditor.pickerFactory = () => _FakePicker((_) async => null);
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (context) => TextButton(
            onPressed: () => ProfilePictureEditor.open(context,
                currentUrl: '/api/profile/pictures/PAT-1?v=old', service: service, onChanged: (_) => changes++),
            child: const Text('edit'),
          )))));
      await tester.tap(find.text('edit'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('photo_cancel')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('edit'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('photo_gallery')));
      await tester.pumpAndSettle();
      expect(changes, 0);
      expect(service.uploads, 0);
      expect(service.removals, 0);
    });

    testWidgets('I23: a denied permission or missing camera gives a clear message, no change', (tester) async {
      final service = FakeProfileService();
      var changes = 0;
      ProfilePictureEditor.pickerFactory = () => _FakePicker((source) async => throw PlatformException(
          code: source == ImageSource.camera ? 'camera_access_denied' : 'photo_access_denied'));
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (context) => TextButton(
            onPressed: () => ProfilePictureEditor.open(context, currentUrl: null, service: service, onChanged: (_) => changes++),
            child: const Text('edit'),
          )))));
      await tester.tap(find.text('edit'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('photo_remove')), findsNothing); // nothing to remove yet
      await tester.tap(find.byKey(const Key('photo_camera')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Camera access was not allowed'), findsOneWidget);
      expect(changes, 0);
    });

    testWidgets('I01/I03/I04/I22: pick, adjust, upload with progress, recover from a failed upload', (tester) async {
      final service = FakeProfileService()..uploadFailuresLeft = 1;
      String? changed = 'unchanged';
      ProfilePictureEditor.pickerFactory = () => _FakePicker((_) async => XFile.fromData(_png, name: 'synthetic.png'));
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (context) => TextButton(
            onPressed: () => ProfilePictureEditor.open(context,
                currentUrl: null, service: service, onChanged: (url) => changed = url),
            child: const Text('edit'),
          )))));
      await tester.tap(find.text('edit'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('photo_gallery')));
      // Picking and decoding the image complete on real async time; pump until the adjust view is shown.
      for (var i = 0; i < 40 && find.byKey(const Key('avatar_crop_view')).evaluate().isEmpty; i++) {
        await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 50)));
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(find.byKey(const Key('avatar_crop_view')), findsOneWidget);
      await tester.ensureVisible(find.byKey(const Key('avatar_crop_confirm')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('avatar_crop_confirm')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('avatar_upload_error')), findsOneWidget); // I22 failure shown
      expect(changed, 'unchanged'); // previous picture kept
      await tester.ensureVisible(find.byKey(const Key('avatar_upload_retry')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('avatar_upload_retry')));
      await tester.pumpAndSettle();
      expect(service.uploads, 2);
      expect(changed, service.nextUrl);
      // Default view = centred square of the 40x20 image: x 0.25, y 0, size 1 (of the short side).
      expect(service.lastCrop!['x'], closeTo(0.25, 0.01));
      expect(service.lastCrop!['y'], closeTo(0, 0.01));
      expect(service.lastCrop!['size'], closeTo(1, 0.01));
    });

    testWidgets('I06: removing asks for confirmation and restores the default', (tester) async {
      final service = FakeProfileService();
      String? changed = 'unchanged';
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (context) => TextButton(
            onPressed: () => ProfilePictureEditor.open(context,
                currentUrl: '/api/profile/pictures/PAT-1?v=1', service: service, onChanged: (url) => changed = url),
            child: const Text('edit'),
          )))));
      await tester.tap(find.text('edit'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('photo_remove')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('photo_remove_cancel')));
      await tester.pumpAndSettle();
      expect(service.removals, 0);
      await tester.tap(find.text('edit'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('photo_remove')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('photo_remove_confirm')));
      await tester.pumpAndSettle();
      expect(service.removals, 1);
      expect(changed, isNull);
    });

    testWidgets('U07: the profile avatar is separate from the MediConnect logo and updates after upload',
        (tester) async {
      AvatarCache.fetchOverride = (_) async => _png;
      final auth = _auth();
      await tester.pumpWidget(_profileApp(FakeProfileService(), auth));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('mediconnect_logo_symbol')), findsOneWidget);
      expect(find.byKey(const Key('profile_avatar')), findsOneWidget);
      auth.updateProfileImage('/api/profile/pictures/PAT-1?v=9');
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('avatar_image_/api/profile/pictures/PAT-1?v=9')), findsOneWidget);
      expect(find.byKey(const Key('mediconnect_logo_symbol')), findsOneWidget); // branding untouched
    });
  });

  group('R02-U navigation and dark theme', () {
    for (final (label, width, scale) in [
      ('U01 320 dp', 320.0, 1.0), ('U02 360 dp', 360.0, 1.0), ('U03 412 dp', 412.0, 1.0),
      ('U01 320 dp, text 1.3x', 320.0, 1.3), ('U02 360 dp, text 1.3x', 360.0, 1.3),
    ]) {
      testWidgets('patient bottom navigation fits: $label', (tester) async {
        tester.view.devicePixelRatio = 3;
        tester.view.physicalSize = Size(width * 3, 800 * 3);
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final errors = <String>[];
        final previous = FlutterError.onError;
        FlutterError.onError = (d) => errors.add(d.toString());
        try {
          await tester.pumpWidget(MediaQuery(
            data: MediaQueryData(size: Size(width, 800), textScaler: TextScaler.linear(scale)),
            child: createTestApp(
                child: PatientHomeScreen(appointmentsLoader: () async => <Appointment>[]), authProvider: _auth()),
          ));
          await tester.pumpAndSettle();
        } finally {
          FlutterError.onError = previous;
        }
        final navBar = find.byWidgetPredicate((w) => w is SafeArea && w.top == true).last;
        expect(navBar, findsWidgets);
        for (final text in ['Home', 'Profile']) {
          final rect = tester.getRect(find.text(text).last);
          expect(rect.left >= 0 && rect.right <= width, isTrue, reason: '$text inside the screen: $rect');
        }
        expect(errors.where((e) => e.contains('overflowed') && e.contains('_buildNavItem')), isEmpty);
        expect(errors.where((e) => e.contains('overflowed') && e.contains('patient_home_screen.dart:7')), isEmpty);
      });
    }

    testWidgets('U05/U06: welcome and login follow the dark theme (background, title, outlined button)',
        (tester) async {
      Future<void> pump(Widget screen) => tester.pumpWidget(MultiProvider(
            providers: [ChangeNotifierProvider<AuthProvider>(create: (_) => AuthProvider(authApiService: MockAuthApiService()))],
            child: MaterialApp(theme: AppTheme.lightTheme, darkTheme: AppTheme.darkTheme, themeMode: ThemeMode.dark, home: screen),
          ));
      await pump(const WelcomeScreen());
      await tester.pump();
      expect(tester.widget<Scaffold>(find.byType(Scaffold).first).backgroundColor, AppTheme.darkBackground);
      expect(tester.widget<Text>(find.text('MediConnect')).style!.color, AppTheme.darkTextPrimary);
      final createAccount = find.byKey(const Key('welcome_create_account_button'));
      final textColor = DefaultTextStyle.of(tester.element(find.descendant(of: createAccount, matching: find.byType(Text)))).style.color;
      expect(textColor, isNotNull);
      expect(_contrast(textColor!, AppTheme.darkBackground), greaterThan(4.5)); // readable outlined button text
      await pump(const LoginScreen());
      await tester.pump();
      expect(tester.widget<Scaffold>(find.byType(Scaffold).first).backgroundColor, AppTheme.darkBackground);
      expect(tester.widget<Text>(find.text('MediConnect')).style!.color, AppTheme.darkTextPrimary);
      expect(find.byKey(const Key('mediconnect_logo_symbol')), findsOneWidget);
    });

    testWidgets('U04: light theme login keeps the existing light colours', (tester) async {
      await tester.pumpWidget(MultiProvider(
        providers: [ChangeNotifierProvider<AuthProvider>(create: (_) => AuthProvider(authApiService: MockAuthApiService()))],
        child: MaterialApp(theme: AppTheme.lightTheme, home: const LoginScreen()),
      ));
      await tester.pump();
      expect(tester.widget<Scaffold>(find.byType(Scaffold).first).backgroundColor, AppTheme.background);
      expect(tester.widget<Text>(find.text('MediConnect')).style!.color, AppTheme.textPrimary);
    });
  });
}

double _lum(Color c) {
  double lin(double v) => v <= 0.03928 ? v / 12.92 : math.pow((v + 0.055) / 1.055, 2.4).toDouble();
  return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
}

double _contrast(Color a, Color b) {
  final la = _lum(a), lb = _lum(b);
  final hi = math.max(la, lb), lo = math.min(la, lb);
  return (hi + 0.05) / (lo + 0.05);
}
