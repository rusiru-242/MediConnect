import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

/// Reusable Modern Medical Card container.
class MedicalCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final Color? backgroundColor;
  final BorderSide? border;
  final double elevation;
  final BorderRadius? borderRadius;

  const MedicalCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16.0),
    this.onTap,
    this.backgroundColor,
    this.border,
    this.elevation = 0,
    this.borderRadius,
  });

  @override
  Widget build(BuildContext context) {
    final effectiveRadius = borderRadius ?? BorderRadius.circular(16);

    return Material(
      color: backgroundColor ?? AppTheme.surface,
      elevation: elevation,
      shadowColor: AppTheme.darkNavy.withValues(alpha: 0.06),
      shape: RoundedRectangleBorder(
        borderRadius: effectiveRadius,
        side: border ?? const BorderSide(color: AppTheme.border, width: 1),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: effectiveRadius,
        splashColor: AppTheme.primaryBlue.withValues(alpha: 0.08),
        highlightColor: AppTheme.primaryBlue.withValues(alpha: 0.04),
        child: Padding(
          padding: padding,
          child: child,
        ),
      ),
    );
  }
}

/// Reusable Medical Status Badge for appointments, verifications, and payments.
class MedicalStatusBadge extends StatelessWidget {
  final String status;
  final double fontSize;
  final EdgeInsetsGeometry? padding;

  const MedicalStatusBadge({
    super.key,
    required this.status,
    this.fontSize = 11,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    final normalized = status.toUpperCase().trim();
    Color bg;
    Color fg;
    Color borderColor;

    switch (normalized) {
      case 'CONFIRMED':
      case 'APPROVED':
      case 'COMPLETED':
      case 'ACTIVE':
      case 'PAID':
      case 'SUCCEEDED':
        bg = AppTheme.successContainer;
        fg = AppTheme.success;
        borderColor = AppTheme.success.withValues(alpha: 0.25);
        break;
      case 'PENDING':
      case 'SUBMITTED':
      case 'UPCOMING':
      case 'SCHEDULED':
      case 'IN_PROGRESS':
        bg = AppTheme.warningContainer;
        fg = AppTheme.warning;
        borderColor = AppTheme.warning.withValues(alpha: 0.3);
        break;
      case 'CANCELLED':
      case 'REJECTED':
      case 'SUSPENDED':
      case 'FAILED':
      case 'DEACTIVATED':
        bg = AppTheme.errorContainer;
        fg = AppTheme.error;
        borderColor = AppTheme.error.withValues(alpha: 0.25);
        break;
      default:
        bg = AppTheme.primaryContainer;
        fg = AppTheme.primaryBlue;
        borderColor = AppTheme.primaryBlue.withValues(alpha: 0.2);
    }

    return Container(
      padding: padding ?? const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: borderColor, width: 1),
      ),
      child: Text(
        normalized,
        style: TextStyle(
          color: fg,
          fontSize: fontSize,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.4,
        ),
      ),
    );
  }
}

/// Reusable Medical Stat / KPI Card.
class MedicalStatCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color? iconColor;
  final Color? iconBackgroundColor;
  final VoidCallback? onTap;

  const MedicalStatCard({
    super.key,
    required this.title,
    required this.value,
    required this.icon,
    this.iconColor,
    this.iconBackgroundColor,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final effectiveIconColor = iconColor ?? AppTheme.primaryBlue;
    final effectiveIconBg = iconBackgroundColor ?? AppTheme.primaryContainer;

    return MedicalCard(
      onTap: onTap,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: effectiveIconBg,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: effectiveIconColor, size: 22),
              ),
              const Icon(Icons.arrow_forward_ios_rounded, size: 14, color: AppTheme.textSecondary),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            value,
            style: const TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            title,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}

/// Reusable Medical Empty State.
class MedicalEmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String message;
  final String? buttonText;
  final VoidCallback? onAction;

  const MedicalEmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
    this.buttonText,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 48),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: AppTheme.primaryContainer,
                shape: BoxShape.circle,
                border: Border.all(color: AppTheme.border, width: 1.5),
              ),
              child: Icon(icon, size: 40, color: AppTheme.primaryBlue),
            ),
            const SizedBox(height: 20),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
                letterSpacing: -0.2,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 14,
                color: AppTheme.textSecondary,
                height: 1.4,
              ),
            ),
            if (buttonText != null && onAction != null) ...[
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: onAction,
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size(160, 44),
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                ),
                child: Text(buttonText!),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Reusable Medical Section Header with optional action.
class MedicalSectionHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;

  const MedicalSectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                    letterSpacing: -0.3,
                  ),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    subtitle!,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (actionLabel != null && onAction != null)
            TextButton(
              onPressed: onAction,
              style: TextButton.styleFrom(
                padding: EdgeInsets.zero,
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    actionLabel!,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.primaryBlue,
                    ),
                  ),
                  const SizedBox(width: 4),
                  const Icon(Icons.arrow_forward_rounded, size: 14, color: AppTheme.primaryBlue),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

