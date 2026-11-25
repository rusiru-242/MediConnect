import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Opens the phone dialer pre-filled with an emergency number (BUG-042).
///
/// On Android this uses `Intent.ACTION_DIAL`, which only shows the number in the dialer: the call
/// starts only when the patient presses the call button. The app holds no `CALL_PHONE` permission,
/// so it cannot place a call by itself.
class EmergencyDialer {
  EmergencyDialer._();

  static const MethodChannel _channel = MethodChannel('mediconnect/emergency_dialer');

  /// Returns true when the dialer opened. Returns false (never throws) when no dialer is available,
  /// so the caller can tell the patient to dial the number manually.
  static Future<bool> open(String number) async {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) return false;
    try {
      return await _channel.invokeMethod<bool>('dial', {'number': number}) ?? false;
    } on PlatformException catch (e) {
      debugPrint('[EmergencyDialer] dialer unavailable: ${e.code}');
      return false;
    } on MissingPluginException {
      debugPrint('[EmergencyDialer] dialer channel not registered');
      return false;
    }
  }
}
