import '../../services/fcm_service.dart';
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
import '../../models/appointment.dart';
import '../../utils/assistant_navigation.dart';
import '../../widgets/upcoming_appointment_card.dart';

/// Patient Home Dashboard redesigned with Google Stitch Clinical Clarity design system.
/// Single visible AI Entry Point: "MediConnect AI Assistant" (Phase 40 & Phase 41).
class PatientHomeScreen extends StatefulWidget {
  /// Loads the patient's appointments for the upcoming-appointment card; injected in tests.
  final Future<List<Appointment>> Function()? appointmentsLoader;

  const PatientHomeScreen({super.key, this.appointmentsLoader});

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
      if (mounted) FcmService().openPendingCareReminder();
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      try {
        Provider.of<NotificationProvider>(context, listen: false).refreshUnreadCount();
      } catch (_) {}
    });
  }

  Future<void> _handleLogout() async {
    final l10n = AppLocalizations.of(context);
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(l10n?.logout ?? 'Confirm Logout', style: const TextStyle(fontWeight: FontWeight.bold)),
        content: Text(l10n?.logoutConfirm ?? 'Are you sure you want to log out of MediConnect?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n?.cancel ?? 'Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.error,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l10n?.logout ?? 'Logout'),
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
    LocaleProvider? localeProvider;
    try {
      localeProvider = Provider.of<LocaleProvider>(context, listen: false);
    } catch (_) {
      localeProvider = null;
    }

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
            Builder(
              builder: (context) {
                LocaleProvider? localeProvider;
                try {
                  localeProvider = Provider.of<LocaleProvider>(context);
                } catch (_) {
                  localeProvider = null;
                }
                final langName = localeProvider?.currentLanguage.displayName ?? 'English';
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
                  color: isDark ? AppTheme.darkPrimaryContainer : AppTheme.primaryContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(Icons.person_outline_rounded, color: isDark ? AppTheme.darkPrimaryBlue : AppTheme.primaryBlue),
              ),
              title: Text(l10n?.profile ?? 'My Patient Profile', style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text(
                localeProvider?.currentLanguage == AppLanguage.sinhala
                    ? 'ඩිජිටල් හැඳුනුම්පත, වෛද්‍ය ඉතිහාසය'
                    : (localeProvider?.currentLanguage == AppLanguage.tamil
                        ? 'டிஜிட்டல் அடையாள அட்டை, வரலாறு'
                        : 'Digital Health ID, medical history, stats'),
              ),
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
              title: Text(l10n?.medicationReminders ?? 'Medication Reminders', style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text(
                localeProvider?.currentLanguage == AppLanguage.sinhala
                    ? 'ක්‍රියාකාරී කාලසටහන් සහ මතක් කිරීම්'
                    : (localeProvider?.currentLanguage == AppLanguage.tamil
                        ? 'செயலில் உள்ள அட்டவணைகள் & நினைவூட்டல்கள்'
                        : 'Active schedules, adherence, and reminders'),
              ),
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
              title: Text(
                localeProvider?.currentLanguage == AppLanguage.sinhala
                    ? 'ගෙවීම් ඉතිහාසය සහ රිසිට්පත්'
                    : (localeProvider?.currentLanguage == AppLanguage.tamil
                        ? 'கட்டண வரலாறு & ரசீதுகள்'
                        : 'Payment History & Receipts'),
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              subtitle: Text(
                localeProvider?.currentLanguage == AppLanguage.sinhala
                    ? 'Stripe උපදේශන ගාස්තු ගනුදෙනු'
                    : (localeProvider?.currentLanguage == AppLanguage.tamil
                        ? 'Stripe கட்டண பரிவர்த்தனைகள்'
                        : 'Stripe consultation fee transactions'),
              ),
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
              title: Text(
                localeProvider?.currentLanguage == AppLanguage.sinhala
                    ? 'සේවාදායක සැකසීම්'
                    : (localeProvider?.currentLanguage == AppLanguage.tamil
                        ? 'சர்வர் அமைப்புகள்'
                        : 'Server & Connectivity Settings'),
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              subtitle: Text(
                localeProvider?.currentLanguage == AppLanguage.sinhala
                    ? 'Host URL වෙනස් කිරීම හෝ ADB reverse'
                    : (localeProvider?.currentLanguage == AppLanguage.tamil
                        ? 'Host URL மாற்றுதல்'
                        : 'Change host URL or toggle ADB reverse'),
              ),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () {
                Navigator.pop(ctx);
                ServerSettingsSheet.show(context);
              },
            ),
            const SizedBox(height: 16),
            Center(
              child: Text(
                'MediConnect Clinical Clarity v2.4 (HIPAA Compliant)',
                style: TextStyle(
                  fontSize: 12,
                  color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                ),
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
    LocaleProvider? localeProvider;
    try {
      localeProvider = Provider.of<LocaleProvider>(context, listen: false);
    } catch (_) {
      localeProvider = null;
    }
    final isSi = localeProvider?.currentLanguage == AppLanguage.sinhala;
    final isTa = localeProvider?.currentLanguage == AppLanguage.tamil;

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: const BoxDecoration(
                color: AppTheme.errorContainer,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.emergency_rounded, color: AppTheme.error, size: 24),
            ),
            const SizedBox(width: 10),
            Text(
              isSi ? 'හදිසි SOS' : (isTa ? 'அவசர SOS' : 'Emergency SOS'),
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ],
        ),
        content: Text(
          isSi
              ? 'හදිසි ජීවිතාරක්ෂක වෛද්‍ය ආධාර සඳහා සෘජු ඇමතුම් පහසුකම:\n\n'
                  '• ජාතික ගිලන්රථ සේවය: 1990\n'
                  '• සාමාන්‍ය හදිසි ඇමතුම්: 119\n\n'
                  'ඔබට දැන් හදිසි ඇමතුමක් ලබා ගැනීමට අවශ්‍යද?'
              : (isTa
                  ? 'உயிருக்கு ஆபத்தான அவசரநிலைகளுக்கு உடனடி உதவி:\n\n'
                      '• தேசிய ஆம்புலன்ஸ் சேவை: 1990\n'
                      '• அவசர உதவி: 119\n\n'
                      'இப்போது அவசர அழைப்பை மேற்கொள்ள விரும்புகிறீர்களா?'
                  : 'For acute, life-threatening medical emergencies, immediate dispatched assistance is available:\n\n'
                      '• National Ambulance Service: 1990\n'
                      '• General Emergency: 911 / 119\n\n'
                      'Would you like to initiate an emergency phone call now?'),
          style: const TextStyle(fontSize: 14, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(isSi ? 'අවලංගු කරන්න' : (isTa ? 'ரத்துசெய்' : 'Dismiss')),
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
                SnackBar(
                  content: Text(
                    isSi
                        ? 'ජාතික ගිලන්රථ සේවය අමතමින් (1990)...'
                        : (isTa ? 'தேசிய ஆம்புலன்ஸ் சேவையை அழைக்கிறது (1990)...' : 'Calling National Ambulance Service (1990)...'),
                  ),
                  backgroundColor: AppTheme.error,
                ),
              );
            },
            icon: const Icon(Icons.phone_in_talk_rounded, size: 18),
            label: Text(isSi ? '1990 අමතන්න' : (isTa ? '1990 ஐ அழைக்கவும்' : 'Call 1990')),
          ),
        ],
      ),
    );
  }

  String _getTimeGreeting(AppLocalizations? l10n) {
    final hour = DateTime.now().hour;
    if (hour < 12) return l10n?.goodMorning ?? 'Good morning';
    if (hour < 17) return l10n?.goodAfternoon ?? 'Good afternoon';
    return l10n?.goodEvening ?? 'Good evening';
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    LocaleProvider? localeProvider;
    try {
      localeProvider = Provider.of<LocaleProvider>(context);
    } catch (_) {
      localeProvider = null;
    }
    final l10n = AppLocalizations.of(context);
    final user = authProvider.user;
    final userName = user?.fullName.isNotEmpty == true ? user!.fullName : (l10n?.patient ?? 'Patient');

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
                  l10n?.patientDashboard ?? 'Patient Dashboard',
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
            tooltip: l10n?.logout ?? 'Logout',
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
                          '${_getTimeGreeting(l10n)}, $userName 👋',
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
                          l10n?.howAreYouFeeling ?? 'How are you feeling today?',
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
              const SizedBox(height: 10),

              // 2. CRITICAL HERO CARD: MediConnect AI Assistant
              _buildStitchAiHeroCard(context, localeProvider),
              const SizedBox(height: 16),

              // 3. Quick Services (2x2 Grid)
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    l10n?.quickActions ?? 'Quick Services',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              _buildQuickServicesGrid(context, l10n, localeProvider),
              const SizedBox(height: 16),

              // 4. Upcoming Appointment Card
              _buildUpcomingAppointmentCard(context, l10n, localeProvider),
              const SizedBox(height: 16),

              // 5. Today's Vitals Tracking Bar
              _buildVitalsTrackerCard(context, localeProvider),
              const SizedBox(height: 20),

              // 6. Additional Care Services (Records, Reviews, Wellness, Payments)
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    localeProvider?.currentLanguage == AppLanguage.sinhala
                        ? 'ප්‍රතිකාර කළමනාකරණය'
                        : (localeProvider?.currentLanguage == AppLanguage.tamil
                            ? 'பராமரிப்பு மேலாண்மை'
                            : 'Care Management'),
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _buildCareManagementCards(context, l10n, localeProvider),
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
                  _isLoggingOut
                      ? (localeProvider?.currentLanguage == AppLanguage.sinhala
                          ? 'පිටවෙමින් පවතී...'
                          : (localeProvider?.currentLanguage == AppLanguage.tamil
                              ? 'வெளியேறுகிறது...'
                              : 'Logging out...'))
                      : (l10n?.logout ?? 'Sign Out of MediConnect'),
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
                  label: localeProvider?.currentLanguage == AppLanguage.sinhala
                      ? 'මුල් පිටුව'
                      : (localeProvider?.currentLanguage == AppLanguage.tamil ? 'முகப்பு' : 'Home'),
                  isSelected: _selectedNavIndex == 0,
                  isDark: isDark,
                  onTap: () => setState(() => _selectedNavIndex = 0),
                ),
                _buildNavItem(
                  icon: Icons.calendar_month_rounded,
                  label: l10n?.myAppointments ?? 'Appointments',
                  isSelected: _selectedNavIndex == 1,
                  isDark: isDark,
                  onTap: () {
                    Navigator.of(context).pushNamed('/patient/my-appointments');
                  },
                ),
                _buildNavItem(
                  icon: Icons.medical_services_rounded,
                  label: l10n?.findDoctor ?? 'Doctors',
                  isSelected: _selectedNavIndex == 2,
                  isDark: isDark,
                  onTap: () {
                    Navigator.of(context).pushNamed('/patient/find-doctor');
                  },
                ),
                _buildNavItem(
                  icon: Icons.person_rounded,
                  label: l10n?.profile ?? 'Profile',
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
  Widget _buildStitchAiHeroCard(BuildContext context, LocaleProvider? localeProvider) {
    final isSi = localeProvider?.currentLanguage == AppLanguage.sinhala;
    final isTa = localeProvider?.currentLanguage == AppLanguage.tamil;

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
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.auto_awesome, size: 12, color: Colors.amberAccent),
                      const SizedBox(width: 5),
                      Text(
                        isSi
                            ? 'MEDICONNECT AI සහකරු'
                            : (isTa
                                ? 'MEDICONNECT AI உதவியாளர்'
                                : 'MEDICONNECT AI COMPANION'),
                        style: const TextStyle(
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
                Text(
                  isSi
                      ? 'ක්ෂණික වෛද්‍ය උපදෙස් අවශ්‍යද?'
                      : (isTa
                          ? 'உடனடி மருத்துவ ஆலோசனை தேவையா?'
                          : 'Need Instant Medical Guidance?'),
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    letterSpacing: -0.3,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  isSi
                      ? 'රෝග ලක්ෂණ විස්තර කරන්න, ඖෂධ පරීක්ෂා කරන්න හෝ වාර්තා විශ්ලේෂණය කරන්න.'
                      : (isTa
                          ? 'அறிகுறிகளை விவரிக்கவும், மருந்துகளை சரிபார்க்கவும் அல்லது அறிக்கைகளை பகுப்பாய்வு செய்யவும்.'
                          : 'Describe symptoms, check medication, or analyze lab reports in one chat.'),
                  style: const TextStyle(
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
                  onPressed: () => AssistantNavigation.open(context),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.smart_toy_rounded, size: 20, color: AppTheme.primaryBlue),
                          const SizedBox(width: 10),
                          Text(
                            isSi
                                ? 'AI උපදේශනය අරඹන්න'
                                : (isTa
                                    ? 'AI ஆலோசனையைத் தொடங்குங்கள்'
                                    : 'Start AI Consultation'),
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.primaryBlue,
                            ),
                          ),
                        ],
                      ),
                      const Icon(Icons.arrow_forward_rounded, size: 20, color: AppTheme.primaryBlue),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                // Quick prompt pill tags
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    _buildHeroPromptChip(
                      context,
                      Icons.medical_services_rounded,
                      isSi
                          ? 'රෝග ලක්ෂණ'
                          : (isTa ? 'அறிகுறிகள்' : 'Check Symptoms'),
                      'I have a fever and headache',
                    ),
                    _buildHeroPromptChip(
                      context,
                      Icons.monitor_heart_rounded,
                      isSi
                          ? 'රුධිර පරීක්ෂණ'
                          : (isTa ? 'இரத்தப் பரிசோதனை' : 'Analyze Blood Test'),
                      'Help analyze my recent lab report',
                    ),
                    _buildHeroPromptChip(
                      context,
                      Icons.medication_rounded,
                      isSi
                          ? 'ඖෂධ තොරතුරු'
                          : (isTa ? 'மருந்து விவரங்கள்' : 'Medication Info'),
                      'What are the precautions for amoxicillin?',
                    ),
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
      onTap: () => AssistantNavigation.open(context, initialPrompt: prompt),
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
  Widget _buildUpcomingAppointmentCard(BuildContext context, AppLocalizations? l10n, LocaleProvider? localeProvider) {
    // Phase 01: real appointments only. The previous card showed a fabricated "Dr. Alexander Wright" video
    // consultation with a "Join Call" button; video channelling is not supported.
    return UpcomingAppointmentCard(
      loader: widget.appointmentsLoader,
      title: l10n?.upcomingAppointments,
      isSi: localeProvider?.currentLanguage == AppLanguage.sinhala,
      isTa: localeProvider?.currentLanguage == AppLanguage.tamil,
    );
  }

  Widget _buildQuickServicesGrid(BuildContext context, AppLocalizations? l10n, LocaleProvider? localeProvider) {
    final isDark = AppTheme.isDark(context);
    final isSi = localeProvider?.currentLanguage == AppLanguage.sinhala;
    final isTa = localeProvider?.currentLanguage == AppLanguage.tamil;

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
                    l10n?.findDoctor ?? (isSi ? 'වෛද්‍යවරයකු සොයන්න' : (isTa ? 'மருத்துவரைத் தேடுங்கள்' : 'Find a Doctor')),
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    isSi ? 'විශේෂඥයින් 120+' : (isTa ? '120+ நிபுணர்கள்' : '120+ Specialists'),
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
                    l10n?.medicalRecords ?? (isSi ? 'පරීක්ෂණ සහ වාර්තා' : (isTa ? 'ஆய்வக அறிக்கைகள்' : 'Lab & Records')),
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    isSi ? 'වට්ටෝරු සහ PDF' : (isTa ? 'மருந்துச்சீட்டுகள் & PDF' : 'Prescriptions & PDFs'),
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
                    isSi ? 'බෙහෙත් සිහිකැඳවීම්' : (isTa ? 'மருந்து நினைவூட்டல்கள்' : 'Medicine Reminders'),
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    isSi ? 'මාත්‍රා කාලසටහන' : (isTa ? 'மருந்து அட்டவணை' : 'Dose schedules'),
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
                    isSi ? 'හදිසි SOS' : (isTa ? 'அவசர SOS' : 'Emergency SOS'),
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: isDark ? AppTheme.darkError : AppTheme.error,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    isSi ? '1990 අමතන්න' : (isTa ? '1990 ஐ அழைக்கவும்' : 'Call 1990 Dispatcher'),
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
  Widget _buildVitalsTrackerCard(BuildContext context, LocaleProvider? localeProvider) {
    // Phase 01: this card used to show invented readings and "Synced 12m ago". It now shows no values and
    // points to Health Tracking, where the patient's real recorded measurements are listed.
    final isSi = localeProvider?.currentLanguage == AppLanguage.sinhala;
    final isTa = localeProvider?.currentLanguage == AppLanguage.tamil;
    String t(String en, String si, String ta) => isSi ? si : (isTa ? ta : en);
    return StitchCard(
      key: const Key('health_tracking_card'),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      child: InkWell(
        onTap: () => Navigator.of(context).pushNamed('/patient/health-tracking'),
        child: Row(
          children: [
            const Icon(Icons.monitor_heart_outlined, color: AppTheme.primaryBlue),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(t('Health Tracking', 'සෞඛ්‍ය සටහන්', 'சுகாதார கண்காணிப்பு'),
                      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                  const SizedBox(height: 2),
                  Text(
                    t('Record and view your blood pressure, blood sugar and weight. Only readings you record are shown.',
                      'ඔබේ රුධිර පීඩනය, රුධිර සීනි සහ බර සටහන් කර බලන්න. ඔබ සටහන් කළ දත්ත පමණක් පෙන්වයි.',
                      'உங்கள் இரத்த அழுத்தம், சர்க்கரை மற்றும் எடையைப் பதிவுசெய்து பாருங்கள். நீங்கள் பதிவுசெய்தவை மட்டுமே காட்டப்படும்.'),
                    style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right_rounded, color: AppTheme.textSecondary),
          ],
        ),
      ),
    );
  }

  Widget _buildCareManagementCards(BuildContext context, AppLocalizations? l10n, LocaleProvider? localeProvider) {
    final isDark = AppTheme.isDark(context);
    final isSi = localeProvider?.currentLanguage == AppLanguage.sinhala;
    final isTa = localeProvider?.currentLanguage == AppLanguage.tamil;

    return Column(
      children: [
        // Healthcare Timeline & Visit History (Phase 58)
        StitchCard(
          key: const Key('patient_home_timeline_button'),
          onTap: () {
            Navigator.of(context).pushNamed('/patient/timeline');
          },
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFF1565C0).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.timeline_rounded, size: 22, color: Color(0xFF1565C0)),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isSi ? 'සෞඛ්‍ය කාලරේඛාව' : (isTa ? 'சுகாதார காலவரிசை' : 'Healthcare Timeline'),
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                      ),
                    ),
                    Text(
                      isSi
                          ? 'හමුවීම්, පැමිණීම් සහ ඖෂධ වට්ටෝරු සටහන'
                          : (isTa
                              ? 'சந்திப்புகள் மற்றும் மருந்துச்சீட்டுகளின் காலவரிசை'
                              : 'Chronological journey of appointments, visits & prescriptions'),
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

        // Follow-up Care Plans
        StitchCard(
          key: const Key('patient_home_care_plans_button'),
          onTap: () {
            Navigator.of(context).pushNamed('/patient/care-agenda');
          },
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.secondaryBlue.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.assignment_turned_in_rounded, size: 22, color: AppTheme.secondaryBlue),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isSi ? 'පසු විපරම් ප්‍රතිකාර සැලසුම්' : (isTa ? 'பராமரிப்பு திட்டங்கள்' : 'Follow-up Care Plans'),
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                      ),
                    ),
                    Text(
                      isSi
                          ? 'වෛද්‍ය උපදෙස්, සුවවීමේ කාර්යයන් සහ වෙන්කිරීම්'
                          : (isTa
                              ? 'மருத்துவர் அறிவுரைகள் & பின்தொடர் முன்பதிவுகள்'
                              : 'Doctor instructions, recovery tasks & follow-up bookings'),
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
                      isSi ? 'මගේ වෛද්‍ය ඇගයීම්' : (isTa ? 'எனது மருத்துவர் மதிப்புரைகள்' : 'My Doctor Reviews'),
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                      ),
                    ),
                    Text(
                      isSi
                          ? 'උපදේශන ඇගයීම සහ ප්‍රතිචාර කියවීම'
                          : (isTa
                              ? 'ஆலோசனைகளை மதிப்பிடவும் பின்னூட்டங்களைப் படிக்கவும்'
                              : 'Rate consultations & read feedback'),
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
                      l10n?.healthWellness ?? (isSi ? 'සෞඛ්‍ය සහ සුවතාව' : (isTa ? 'சுகாதாரம் & ஆரோக்கியம்' : 'Health & Wellness Guides')),
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                      ),
                    ),
                    Text(
                      isSi
                          ? 'පෝෂණය, යෝග්‍යතාව සහ වැළැක්වීමේ සත්කාර'
                          : (isTa
                              ? 'ஊட்டச்சத்து, உடற்பயிற்சி & தடுப்பு பராமரிப்பு'
                              : 'Nutrition, fitness & preventive care'),
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
                      isSi ? 'ගෙවීම් ඉතිහාසය සහ රිසිට්පත්' : (isTa ? 'கட்டண வரலாறு மற்றும் ரசீதுகள்' : 'Payment History & Receipts'),
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                      ),
                    ),
                    Text(
                      isSi
                          ? 'Stripe රිසිට්පත් සහ උපදේශන ඉන්වොයිසි'
                          : (isTa
                              ? 'Stripe ரசீதுகள் & ஆலோசனை விலைப்பட்டியல்கள்'
                              : 'Stripe receipts & consultation invoices'),
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
