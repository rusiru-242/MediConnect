import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

/// Reusable branded logo and medical icon for MediConnect.
class MediConnectLogo extends StatelessWidget {
  final double size;
  final bool showText;
  final bool isDark;

  const MediConnectLogo({
    super.key,
    this.size = 64,
    this.showText = false,
    this.isDark = false,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [
                AppTheme.primary,
                AppTheme.primaryLight,
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(size * 0.28),
            boxShadow: [
              BoxShadow(
                color: AppTheme.primary.withValues(alpha: 0.25),
                blurRadius: 16,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Center(
            child: Icon(
              Icons.health_and_safety_rounded,
              color: Colors.white,
              size: size * 0.58,
            ),
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
              color: isDark ? Colors.white : AppTheme.textPrimary,
            ),
          ),
        ],
      ],
    );
  }
}
