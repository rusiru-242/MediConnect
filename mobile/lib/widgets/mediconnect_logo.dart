import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

/// MediConnect brand symbol (R01): the heart, ECG waveform, medical cross and orbit from the official logo.
///
/// The asset is the symbol only (no wordmark), so it can sit beside existing "MediConnect" title text without
/// repeating the name. It keeps its original proportions inside a [size] x [size] box and reads on both light and
/// dark backgrounds. Source and generator: branding/generate_brand_assets.py.
class MediConnectLogo extends StatelessWidget {
  static const String assetPath = 'assets/branding/mediconnect_symbol.png';

  final double size;
  final bool showText;
  final bool isDark;

  /// Spoken label. Null (default) marks the symbol as decorative, because every placement already shows the
  /// "MediConnect" name as text next to it.
  final String? semanticLabel;

  const MediConnectLogo({
    super.key,
    this.size = 64,
    this.showText = false,
    this.isDark = false,
    this.semanticLabel,
  });

  @override
  Widget build(BuildContext context) {
    final dark = isDark || Theme.of(context).brightness == Brightness.dark;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          key: const Key('mediconnect_logo_symbol'),
          width: size,
          height: size,
          child: Image.asset(
            assetPath,
            fit: BoxFit.contain,
            filterQuality: FilterQuality.medium,
            semanticLabel: semanticLabel,
            excludeFromSemantics: semanticLabel == null,
            gaplessPlayback: true,
          ),
        ),
        if (showText) ...[
          const SizedBox(height: 12),
          Text(
            'MediConnect',
            style: TextStyle(
              fontSize: size * 0.38,
              fontWeight: FontWeight.bold,
              letterSpacing: -0.5,
              color: dark ? Colors.white : AppTheme.textPrimary,
            ),
          ),
        ],
      ],
    );
  }
}
