package com.mediconnect.mediconnect

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterFragmentActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        // Emergency dialer (BUG-042): ACTION_DIAL only pre-fills the number in the dialer.
        // The patient must press call; the app has no CALL_PHONE permission.
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "mediconnect/emergency_dialer")
            .setMethodCallHandler { call, result ->
                if (call.method != "dial") {
                    result.notImplemented()
                    return@setMethodCallHandler
                }
                val number = call.argument<String>("number")
                if (number == null || !number.matches(Regex("^[0-9]{3,6}$"))) {
                    result.error("invalid_number", "Only short emergency numbers are allowed", null)
                    return@setMethodCallHandler
                }
                try {
                    startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$number")))
                    result.success(true)
                } catch (e: ActivityNotFoundException) {
                    result.success(false)
                }
            }
    }
}
