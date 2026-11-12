import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../l10n/app_localizations.dart';
import '../../providers/auth_provider.dart';
import '../../providers/locale_provider.dart';
import '../../providers/notification_provider.dart';
import '../../providers/theme_provider.dart';
import '../../widgets/language_selector_sheet.dart';
import '../../widgets/medical_widgets.dart';
import '../../widgets/mediconnect_logo.dart';
import '../../widgets/notification_bell_button.dart';
import '../../widgets/server_settings_sheet.dart';

/// Patient Home Dashboard redesigned with Google Stitch Clinical Clarity design system.
/// Single visible AI Entry Point: "MediConnect AI Assistant" (Phase 40 & Phase 41).
class PatientHomeScreen extends StatefulWidget {
  const PatientHomeScreen({super.key});

  @override
  State<PatientHomeScreen> createState() => _PatientHomeScreenState();
}

class _PatientHomeScreenState extends State<PatientHomeScreen> {
  bool _isLoggingOut = false;
  int _selectedNavIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      try {
        Provider.of<NotificationProvider>(context, listen: false).refreshUnreadCount();
      } catch (_) {}
    });
  }

  Future<void> _handleLogout() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Confirm Logout', style: TextStyle(fontWeight: FontWeight.bold)),
        content: const Text('Are you sure you want to log out of MediConnect?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.error,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Logout'),
          ),
        ],
      ),
    );

    if (confirm != true) return;
    if (!mounted) return;

    setState(() {
      _isLoggingOut = true;
    });

    final authProvider = context.read<AuthProvider>();
    await authProvider.logout();

    if (!mounted) return;

    Navigator.of(context).pushNamedAndRemoveUntil(
      '/welcome',
      (route) => false,
    );
  }

  void _showSettingsAndProfile() {
    final authProvider = context.read<AuthProvider>();
    final user = authProvider.user;
    final l10n = AppLocalizations.of(context);

    ThemeProvider? themeProvider;
    try {
      themeProvider = Provider.of<ThemeProvider>(context, listen: false);
    } catch (_) {
      themeProvider = null;
    }
    final isDark = themeProvider != null
        ? themeProvider.isDark(context)
        : Theme.of(context).brightness == Brightness.dark;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Material(
        color: isDark ? AppTheme.darkSurface : Colors.white,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        clipBehavior: Clip.antiAlias,
        child: Padding(
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
                CircleAvatar(
                  radius: 28,
                  backgroundColor: isDark ? AppTheme.darkPrimaryContainer : AppTheme.primaryContainer,
                  child: Icon(Icons.person_rounded, size: 32, color: isDark ? AppTheme.darkPrimaryBlue : AppTheme.primaryBlue),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user?.fullName ?? 'Patient',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        user?.email ?? '',
                        style: TextStyle(
                          fontSize: 13,
                          color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            Divider(height: 28, color: isDark ? AppTheme.darkBorder : AppTheme.border),
            SwitchListTile.adaptive(
              key: const Key('patient_home_dark_mode_switch'),
              contentPadding: EdgeInsets.zero,
              secondary: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: isDark
                      ? AppTheme.darkPrimaryContainer
                      : AppTheme.primaryContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  isDark ? Icons.dark_mode_rounded : Icons.light_mode_rounded,
                  color: isDark ? const Color(0xFF38BDF8) : AppTheme.primaryBlue,
                  size: 20,
                ),
              ),
              title: Text(
                'Dark Theme',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                ),
              ),
              subtitle: Text(
                isDark ? 'Medical Dark Slate active' : 'Clinical Light active',
                style: TextStyle(
                  fontSize: 12,
                  color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                ),
              ),
              value: isDark,
              onChanged: themeProvider != null
                  ? (val) {
                      themeProvider?.setThemeMode(val ? ThemeMode.dark : ThemeMode.light);
                      Navigator.pop(ctx);
                    }
                  : null,
            ),
            Divider(height: 16, color: isDark ? AppTheme.darkBorder : AppTheme.border),
            Consumer<LocaleProvider>(
              builder: (context, localeProvider, _) {
                final langName = localeProvider.currentLanguage.displayName;
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryContainer,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.language_rounded, color: AppTheme.primaryBlue),
                  ),
                  title: Text(l10n?.language ?? 'Language', style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text(langName, style: const TextStyle(color: AppTheme.primaryBlue, fontWeight: FontWeight.w600)),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () {
                    Navigator.pop(ctx);
                    LanguageSelectorSheet.show(context);
                  },
                );
              },
            ),
            Divider(height: 16, color: isDark ? AppTheme.darkBorder : AppTheme.border),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.primaryContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.person_outline_rounded, color: AppTheme.primaryBlue),
              ),
              title: const Text('My Patient Profile', style: TextStyle(fontWeight: FontWeight.w600)),
              subtitle: const Text('Digital Health ID, medical history, stats'),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () {
                Navigator.pop(ctx);
                Navigator.of(context).pushNamed('/patient/profile');
              },
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.indigo.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.alarm_rounded, color: Colors.indigo),
              ),
              title: const Text('Medication Reminders', style: TextStyle(fontWeight: FontWeight.w600)),
              subtitle: const Text('Active schedules, adherence, and reminders'),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () {
                Navigator.pop(ctx);
                Navigator.of(context).pushNamed('/patient/medication-reminders');
              },
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.green.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.receipt_long_rounded, color: Colors.green),
              ),
              title: const Text('Payment History & Receipts', style: TextStyle(fontWeight: FontWeight.w600)),
              subtitle: const Text('Stripe consultation fee transactions'),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () {
                Navigator.pop(ctx);
                Navigator.of(context).pushNamed('/patient/payments');
              },
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.blueGrey.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.dns_rounded, color: Colors.blueGrey),
              ),
              title: const Text('Server & Connectivity Settings', style: TextStyle(fontWeight: FontWeight.w600)),
              subtitle: const Text('Change host URL or toggle ADB reverse'),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () {
                Navigator.pop(ctx);
                ServerSettingsSheet.show(context);
              },
            ),
            const SizedBox(height: 16),
            const Center(
              child: Text(
                'MediConnect Clinical Clarity v2.4 (HIPAA Compliant)',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    ),
  );
  }

  void _triggerEmergencyAlert() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: AppTheme.errorContainer,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.emergency_rounded, color: AppTheme.error, size: 24),
            ),
            const SizedBox(width: 10),
            const Text('Emergency SOS', style: TextStyle(fontWeight: FontWeight.bold)),
          ],
        ),
        content: const Text(
          'For acute, life-threatening medical emergencies, immediate dispatched assistance is available:\n\n'
          '• National Ambulance Service: 1990\n'
          '• General Emergency: 911 / 119\n\n'
          'Would you like to initiate an emergency phone call now?',
          style: TextStyle(fontSize: 14, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Dismiss'),
          ),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.error,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Calling National Ambulance Service (1990)...'),
                  backgroundColor: AppTheme.error,
                ),
              );
            },
            icon: const Icon(Icons.phone_in_talk_rounded, size: 18),
            label: const Text('Call 1990'),
          ),
        ],
      ),
    );
  }

  String _getTimeGreeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final user = authProvider.user;
    final userName = user?.fullName.isNotEmpty == true ? user!.fullName : 'Patient';

    ThemeProvider? themeProvider;
    try {
      themeProvider = Provider.of<ThemeProvider>(context);
    } catch (_) {
      themeProvider = null;
    }
    final isDark = themeProvider != null
        ? themeProvider.isDark(context)
        : Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark ? AppTheme.darkBackground : AppTheme.background,
      appBar: AppBar(
        backgroundColor: isDark ? AppTheme.darkSurface : Colors.white,
        elevation: 0,
        scrolledUnderElevation: 1,
        titleSpacing: 16,
        title: Row(
          children: [
            const MediConnectLogo(size: 28),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'MEDICONNECT',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.2,
                    color: isDark ? AppTheme.darkPrimaryBlue : AppTheme.primaryBlue,
                  ),
                ),
                Text(
                  'Patient Dashboard',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                  ),
                ),
              ],
            ),
          ],
        ),
        actions: [
          const NotificationBellButton(),
          IconButton(
            key: const Key('patient_home_settings_button'),
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Profile & Settings',
            onPressed: _showSettingsAndProfile,
          ),
          IconButton(
            key: const Key('patient_home_logout_icon_button'),
            icon: const Icon(Icons.logout_rounded),
            tooltip: 'Logout',
            onPressed: _isLoggingOut ? null : _handleLogout,
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16.0, 6.0, 16.0, 12.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 1. Welcome & Vitals Header
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${_getTimeGreeting()}, $userName 👋',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w700,
                            color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                            letterSpacing: -0.3,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 1),
                        Text(
                          'How are you feeling today?',
                          style: TextStyle(
                            fontSize: 13,
                            color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  const StitchPulseBadge(
                    label: 'VITALS: NORMAL',
                    dotColor: AppTheme.success,
                    backgroundColor: AppTheme.successContainer,
                    textColor: AppTheme.stitchTertiary,
                  ),
                ],
              ),
              const SizedBox(height: 10),

              // 2. CRITICAL HERO CARD: MediConnect AI Assistant
              _buildStitchAiHeroCard(context),
              const SizedBox(height: 16),

              // 3. Quick Services (2x2 Grid)
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Quick Services',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              _buildQuickServicesGrid(context),
              const SizedBox(height: 16),

              // 4. Upcoming Appointment Card
              _buildUpcomingAppointmentCard(context),
              const SizedBox(height: 16),

              // 5. Today's Vitals Tracking Bar
              _buildVitalsTrackerCard(context),
              const SizedBox(height: 20),

              // 6. Additional Care Services (Records, Reviews, Wellness, Payments)
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Care Management',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _buildCareManagementCards(context),
              const SizedBox(height: 24),

              // 7. Logout Action Button (Preserved for tests)
              OutlinedButton.icon(
                key: const Key('patient_home_logout_button'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.error,
                  side: BorderSide(color: AppTheme.error.withValues(alpha: 0.3), width: 1.5),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  minimumSize: const Size(double.infinity, 48),
                ),
                onPressed: _isLoggingOut ? null : _handleLogout,
                icon: _isLoggingOut
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(AppTheme.error),
                        ),
                      )
                    : const Icon(Icons.logout_rounded, size: 20),
                label: Text(
                  _isLoggingOut ? 'Logging out...' : 'Sign Out of MediConnect',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: isDark ? AppTheme.darkSurface : Colors.white,
          border: Border(
            top: BorderSide(
              color: isDark ? AppTheme.darkBorder : AppTheme.border,
              width: 1,
            ),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.05),
              blurRadius: 16,
              offset: const Offset(0, -4),
            ),
          ],
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildNavItem(
                  icon: Icons.home_rounded,
                  label: 'Home',
                  isSelected: _selectedNavIndex == 0,
                  isDark: isDark,
                  onTap: () => setState(() => _selectedNavIndex = 0),
                ),
                _buildNavItem(
                  icon: Icons.calendar_month_rounded,
                  label: 'Appointments',
                  isSelected: _selectedNavIndex == 1,
                  isDark: isDark,
                  onTap: () {
                    Navigator.of(context).pushNamed('/patient/my-appointments');
                  },
                ),
                _buildNavItem(
                  icon: Icons.medical_services_rounded,
                  label: 'Doctors',
                  isSelected: _selectedNavIndex == 2,
                  isDark: isDark,
                  onTap: () {
                    Navigator.of(context).pushNamed('/patient/find-doctor');
                  },
                ),
                _buildNavItem(
                  icon: Icons.person_rounded,
                  label: 'Profile',
                  isSelected: _selectedNavIndex == 3,
                  isDark: isDark,
                  onTap: () {
                    Navigator.of(context).pushNamed('/patient/profile');
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNavItem({
    required IconData icon,
    required String label,
    required bool isSelected,
    required VoidCallback onTap,
    bool isDark = false,
  }) {
    final activeBg = isDark ? AppTheme.darkPrimaryContainer : AppTheme.primaryContainer;
    final activeFg = isDark ? AppTheme.darkPrimaryBlue : AppTheme.primaryBlue;
    final inactiveFg = isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(20),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 52,
              height: 28,
              decoration: BoxDecoration(
                color: isSelected ? activeBg : Colors.transparent,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(
                icon,
                color: isSelected ? activeFg : inactiveFg,
                size: 22,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                color: isSelected ? activeFg : inactiveFg,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// CRITICAL HERO CARD: MediConnect AI Assistant
  Widget _buildStitchAiHeroCard(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(
          colors: [
            Color(0xFF004D99), // Stitch Primary
            Color(0xFF1565C0), // Primary Blue
            Color(0xFF2196F3), // Bright Azure
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF004D99).withValues(alpha: 0.35),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          // Ambient blur circles
          Positioned(
            right: -20,
            top: -20,
            child: Container(
              width: 140,
              height: 140,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withValues(alpha: 0.1),
              ),
            ),
          ),
          Positioned(
            left: -15,
            bottom: -15,
            child: Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withValues(alpha: 0.08),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14.0, vertical: 12.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Top Pill Badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.18),
                    borderRadius: BorderRadius.circular(9999),
                    border: Border.all(color: Colors.white.withValues(alpha: 0.25)),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.auto_awesome, size: 12, color: Colors.amberAccent),
                      SizedBox(width: 5),
                      Text(
                        'MEDICONNECT AI COMPANION',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 9.5,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.6,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Need Instant Medical Guidance?',
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    letterSpacing: -0.3,
                  ),
                ),
                const SizedBox(height: 2),
                const Text(
                  'Describe symptoms, check medication, or analyze lab reports in one chat.',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.white70,
                    height: 1.25,
                  ),
                ),
                const SizedBox(height: 8),
                // Main Action Button (Preserves Key for existing tests)
                ElevatedButton(
                  key: const Key('patient_home_ai_assistant_button'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: AppTheme.primaryBlue,
                    elevation: 3,
                    shadowColor: Colors.black26,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(9999),
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    minimumSize: const Size(double.infinity, 40),
                  ),
                  onPressed: () {
                    Navigator.of(context).pushNamed('/patient/ai-assistant');
                  },
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.smart_toy_rounded, size: 20, color: AppTheme.primaryBlue),
                          SizedBox(width: 10),
                          Text(
                            'Start AI Consultation',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.primaryBlue,
                            ),
                          ),
                        ],
                      ),
                      Icon(Icons.arrow_forward_rounded, size: 20, color: AppTheme.primaryBlue),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                // Quick prompt pill tags
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    _buildHeroPromptChip(context, Icons.medical_services_rounded, 'Check Symptoms', 'I have a fever and headache'),
                    _buildHeroPromptChip(context, Icons.monitor_heart_rounded, 'Analyze Blood Test', 'Help analyze my recent lab report'),
                    _buildHeroPromptChip(context, Icons.medication_rounded, 'Medication Info', 'What are the precautions for amoxicillin?'),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeroPromptChip(BuildContext context, IconData icon, String label, String prompt) {
    return InkWell(
      onTap: () {
        Navigator.of(context).pushNamed(
          '/patient/ai-assistant',
          arguments: {'initialPrompt': prompt},
        );
      },
      borderRadius: BorderRadius.circular(9999),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(9999),
          border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 13, color: Colors.white),
            const SizedBox(width: 5),
            Text(
              label,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Upcoming Appointment Card
  Widget _buildUpcomingAppointmentCard(BuildContext context) {
    final isDark = AppTheme.isDark(context);
    return StitchCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Upcoming Appointment',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                ),
              ),
              InkWell(
                key: const Key('patient_home_my_appointments_button'),
                onTap: () {
                  Navigator.of(context).pushNamed('/patient/my-appointments');
                },
                child: const Text(
                  'View all',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.primaryBlue,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: AppTheme.primaryContainer,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(Icons.person_rounded, size: 30, color: AppTheme.primaryBlue),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppTheme.secondaryContainer,
                        borderRadius: BorderRadius.circular(9999),
                      ),
                      child: const Text(
                        'Tomorrow • 10:30 AM',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.onSecondaryContainer,
                        ),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Dr. Alexander Wright',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                      ),
                    ),
                    Text(
                      'Cardiologist • St. Jude Hospital',
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Mode banner
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: isDark ? AppTheme.darkSurfaceContainerLow : AppTheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Row(
                    children: [
                      const Icon(Icons.videocam_rounded, size: 18, color: AppTheme.primaryBlue),
                      const SizedBox(width: 8),
                      Flexible(
                        child: Text(
                          'Encrypted Video Consultation',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                const StitchPulseBadge(label: 'READY', dotColor: AppTheme.success),
              ],
            ),
          ),
          const SizedBox(height: 12),
          // Actions
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.textPrimary,
                    side: const BorderSide(color: AppTheme.border, width: 1),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    minimumSize: const Size(0, 42),
                  ),
                  onPressed: () {
                    Navigator.of(context).pushNamed('/patient/my-appointments');
                  },
                  icon: const Icon(Icons.event_repeat_rounded, size: 16),
                  label: const Text('Reschedule', style: TextStyle(fontSize: 13)),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryBlue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    minimumSize: const Size(0, 42),
                  ),
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Video consultation link will become active 10 minutes prior to session.')),
                    );
                  },
                  icon: const Icon(Icons.videocam_rounded, size: 18),
                  label: const Text('Join Call', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Quick Services 2x2 Grid
  Widget _buildQuickServicesGrid(BuildContext context) {
    final isDark = AppTheme.isDark(context);
    return GridView.count(
      crossAxisCount: 2,
      crossAxisSpacing: 10,
      mainAxisSpacing: 10,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      childAspectRatio: 1.35,
      children: [
        // 1. Book Doctor
        StitchCard(
          key: const Key('patient_home_find_doctor_button'),
          onTap: () {
            Navigator.of(context).pushNamed('/patient/find-doctor');
          },
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: AppTheme.primaryContainer,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.calendar_month_rounded, size: 22, color: AppTheme.primaryBlue),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Find a Doctor',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '120+ Specialists',
                    style: TextStyle(
                      fontSize: 11,
                      color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),

        // 2. Lab & Records
        StitchCard(
          key: const Key('patient_home_medical_records_button'),
          onTap: () {
            Navigator.of(context).pushNamed('/patient/medical-records');
          },
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: const Color(0xFFE1F5FE),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.receipt_long_rounded, size: 22, color: Color(0xFF0288D1)),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Lab & Records',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Prescriptions & PDFs',
                    style: TextStyle(
                      fontSize: 11,
                      color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),

        // 3. Prescriptions & Reminders
        StitchCard(
          key: const Key('patient_home_medication_reminders_button'),
          onTap: () {
            Navigator.of(context).pushNamed('/patient/medication-reminders');
          },
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: AppTheme.successContainer,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.alarm_on_rounded, size: 22, color: AppTheme.success),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Prescriptions',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Dose schedules',
                    style: TextStyle(
                      fontSize: 11,
                      color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),

        // 4. Emergency SOS
        StitchCard(
          onTap: _triggerEmergencyAlert,
          backgroundColor: AppTheme.errorContainer.withValues(alpha: 0.3),
          border: BorderSide(color: AppTheme.error.withValues(alpha: 0.25)),
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: AppTheme.errorContainer,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.emergency_rounded, size: 22, color: AppTheme.error),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Emergency SOS',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkError : AppTheme.error,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Call 1990 Dispatcher',
                    style: TextStyle(
                      fontSize: 11,
                      color: isDark ? AppTheme.darkError : AppTheme.error,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }

  /// Today's Vitals Tracking Bar
  Widget _buildVitalsTrackerCard(BuildContext context) {
    final isDark = AppTheme.isDark(context);
    return StitchCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: const [
              Text(
                'Today\'s Vitals',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              Text(
                'Synced 12m ago',
                style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              // Heart rate
              Expanded(
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: const [
                        Icon(Icons.favorite_rounded, size: 14, color: AppTheme.error),
                        SizedBox(width: 4),
                        Text('Heart Rate', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text('72', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary)),
                    Text('bpm', style: TextStyle(fontSize: 11, color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary)),
                  ],
                ),
              ),
              Container(width: 1, height: 40, color: isDark ? AppTheme.darkBorder : AppTheme.border),
              // Blood pressure
              Expanded(
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: const [
                        Icon(Icons.speed_rounded, size: 14, color: AppTheme.primaryBlue),
                        SizedBox(width: 4),
                        Text('Blood Pres.', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text('118/78', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary)),
                    Text('mmHg', style: TextStyle(fontSize: 11, color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary)),
                  ],
                ),
              ),
              Container(width: 1, height: 40, color: isDark ? AppTheme.darkBorder : AppTheme.border),
              // Sleep
              Expanded(
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: const [
                        Icon(Icons.bedtime_rounded, size: 14, color: AppTheme.secondaryBlue),
                        SizedBox(width: 4),
                        Text('Sleep', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text('7h 45m', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary)),
                    Text('Restorative', style: TextStyle(fontSize: 11, color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary)),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Additional Care Management features
  Widget _buildCareManagementCards(BuildContext context) {
    final isDark = AppTheme.isDark(context);
    return Column(
      children: [
        // Doctor Reviews
        StitchCard(
          key: const Key('patient_home_my_reviews_button'),
          onTap: () {
            Navigator.of(context).pushNamed('/patient/my-reviews');
          },
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.amber.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.star_rounded, size: 22, color: Colors.amber.shade800),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'My Doctor Reviews',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                      ),
                    ),
                    Text(
                      'Rate consultations & read feedback',
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary),
            ],
          ),
        ),
        const SizedBox(height: 10),

        // Health & Wellness
        StitchCard(
          key: const Key('patient_home_health_wellness_button'),
          onTap: () {
            Navigator.of(context).pushNamed('/patient/health-wellness');
          },
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.primaryContainer,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.spa_rounded, size: 22, color: AppTheme.primaryBlue),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Health & Wellness Guides',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                      ),
                    ),
                    Text(
                      'Nutrition, fitness & preventive care',
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary),
            ],
          ),
        ),
        const SizedBox(height: 10),

        // Payments & Receipts
        StitchCard(
          key: const Key('patient_home_payments_button'),
          onTap: () {
            Navigator.of(context).pushNamed('/patient/payments');
          },
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.green.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.receipt_long_rounded, size: 22, color: Colors.green),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Payment History & Receipts',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                      ),
                    ),
                    Text(
                      'Stripe receipts & consultation invoices',
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary),
            ],
          ),
        ),
      ],
    );
  }
}
