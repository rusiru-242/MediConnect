import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme/app_theme.dart';
import '../l10n/app_localizations.dart';
import '../providers/locale_provider.dart';

/// Modal bottom sheet and inline bar for switching languages between English, Sinhala, and Tamil.
class LanguageSelectorSheet {
  static Future<void> show(BuildContext context) async {
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) {
        final isDark = Theme.of(ctx).brightness == Brightness.dark;
        return Consumer<LocaleProvider>(
          builder: (context, localeProvider, _) {
            final l10n = AppLocalizations.of(context);
            final currentCode = localeProvider.locale.languageCode;

            return Container(
              decoration: BoxDecoration(
                color: isDark ? AppTheme.darkSurface : Colors.white,
                borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      margin: const EdgeInsets.only(bottom: 20),
                      decoration: BoxDecoration(
                        color: isDark ? AppTheme.darkBorder : Colors.grey.shade300,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: isDark ? AppTheme.darkPrimaryContainer : AppTheme.primaryContainer,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(
                          Icons.language_rounded,
                          color: isDark ? AppTheme.darkPrimaryBlue : AppTheme.primary,
                          size: 24,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              l10n?.chooseLanguage ?? 'Choose Your Language',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                              ),
                            ),
                            Text(
                              l10n?.selectLanguage ?? 'Select Language',
                              style: TextStyle(
                                fontSize: 13,
                                color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        icon: Icon(Icons.close_rounded, color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary),
                        onPressed: () => Navigator.pop(ctx),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  _buildLanguageOption(
                    context: ctx,
                    title: 'English',
                    subtitle: 'English',
                    code: 'en',
                    isSelected: currentCode == 'en',
                    isDark: isDark,
                    onTap: () {
                      localeProvider.setLocale(const Locale('en'));
                      Navigator.pop(ctx);
                    },
                  ),
                  const SizedBox(height: 10),
                  _buildLanguageOption(
                    context: ctx,
                    title: 'සිංහල',
                    subtitle: 'Sinhala',
                    code: 'si',
                    isSelected: currentCode == 'si',
                    isDark: isDark,
                    onTap: () {
                      localeProvider.setLocale(const Locale('si'));
                      Navigator.pop(ctx);
                    },
                  ),
                  const SizedBox(height: 10),
                  _buildLanguageOption(
                    context: ctx,
                    title: 'தமிழ்',
                    subtitle: 'Tamil',
                    code: 'ta',
                    isSelected: currentCode == 'ta',
                    isDark: isDark,
                    onTap: () {
                      localeProvider.setLocale(const Locale('ta'));
                      Navigator.pop(ctx);
                    },
                  ),
                  const SizedBox(height: 16),
                ],
              ),
            );
          },
        );
      },
    );
  }

  static Widget _buildLanguageOption({
    required BuildContext context,
    required String title,
    required String subtitle,
    required String code,
    required bool isSelected,
    required VoidCallback onTap,
    bool isDark = false,
  }) {
    final bgColor = isSelected
        ? (isDark ? AppTheme.darkPrimaryContainer.withValues(alpha: 0.3) : AppTheme.primaryContainer.withAlpha(60))
        : (isDark ? AppTheme.darkSurfaceContainerLow : Colors.white);
    final borderColor = isSelected
        ? (isDark ? AppTheme.darkPrimaryBlue : AppTheme.primary)
        : (isDark ? AppTheme.darkBorder : AppTheme.border);
    final titleColor = isSelected
        ? (isDark ? AppTheme.darkPrimaryBlue : AppTheme.primary)
        : (isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary);
    final subtitleColor = isSelected
        ? (isDark ? AppTheme.darkPrimaryBlue.withValues(alpha: 0.8) : AppTheme.primary.withAlpha(180))
        : (isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary);

    return Material(
      color: bgColor,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: borderColor,
              width: isSelected ? 1.8 : 1.0,
            ),
          ),
          child: Row(
            children: [
              Text(
                title,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                  color: titleColor,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '($subtitle)',
                style: TextStyle(
                  fontSize: 13,
                  color: subtitleColor,
                ),
              ),
              const Spacer(),
              if (isSelected)
                Icon(
                  Icons.check_circle_rounded,
                  color: isDark ? AppTheme.darkPrimaryBlue : AppTheme.primary,
                  size: 22,
                )
              else
                Icon(
                  Icons.circle_outlined,
                  color: isDark ? AppTheme.darkBorder : Colors.grey.shade400,
                  size: 22,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Lightweight horizontal chip selector for Welcome Screen or compact headers.
class WelcomeLanguageBar extends StatelessWidget {
  const WelcomeLanguageBar({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<LocaleProvider>(
      builder: (context, provider, _) {
        final currentCode = provider.locale.languageCode;

        return Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _buildChip(
              context: context,
              label: 'English',
              code: 'en',
              isSelected: currentCode == 'en',
              onTap: () => provider.setLocale(const Locale('en')),
            ),
            const SizedBox(width: 8),
            _buildChip(
              context: context,
              label: 'සිංහල',
              code: 'si',
              isSelected: currentCode == 'si',
              onTap: () => provider.setLocale(const Locale('si')),
            ),
            const SizedBox(width: 8),
            _buildChip(
              context: context,
              label: 'தமிழ்',
              code: 'ta',
              isSelected: currentCode == 'ta',
              onTap: () => provider.setLocale(const Locale('ta')),
            ),
          ],
        );
      },
    );
  }

  Widget _buildChip({
    required BuildContext context,
    required String label,
    required String code,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primary : (isDark ? AppTheme.darkSurfaceContainerLow : Colors.white),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? AppTheme.primary : (isDark ? AppTheme.darkBorder : AppTheme.border),
            width: 1,
          ),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: AppTheme.primary.withAlpha(40),
                    blurRadius: 6,
                    offset: const Offset(0, 2),
                  ),
                ]
              : null,
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
            color: isSelected ? Colors.white : (isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary),
          ),
        ),
      ),
    );
  }
}
