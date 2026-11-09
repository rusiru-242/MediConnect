import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/notification_provider.dart';
import '../../providers/theme_provider.dart';
import '../../widgets/medical_widgets.dart';
import '../../widgets/mediconnect_logo.dart';
import '../../widgets/notification_bell_button.dart';
import '../../widgets/server_settings_sheet.dart';

/// Doctor Home Dashboard redesigned with Google Stitch Clinical Clarity design system (Phase 41).
class DoctorHomeScreen extends StatefulWidget {
  const DoctorHomeScreen({super.key});

  @override
  State<DoctorHomeScreen> createState() => _DoctorHomeScreenState();
}

class _DoctorHomeScreenState extends State<DoctorHomeScreen> {
  bool _isOnDuty = true;
  bool _showAlert = true;

  Future<void> _handleLogout(BuildContext context) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Confirm Logout', style: TextStyle(fontWeight: FontWeight.bold)),
        content: const Text('Are you sure you want to log out of your Doctor account?'),
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
    if (!context.mounted) return;

    final authProvider = context.read<AuthProvider>();
    await authProvider.logout();
    if (!context.mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/welcome', (route) => false);
  }

  void _showDoctorProfile(BuildContext context) {
    final authProvider = context.read<AuthProvider>();
    final user = authProvider.user;
    final appStatus = authProvider.doctorApplicationStatus;

    final doctorName = user?.fullName.isNotEmpty == true
        ? (user!.fullName.startsWith('Dr.') ? user.fullName : 'Dr. ${user.fullName}')
        : 'Dr. Doctor';

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
                  radius: 30,
                  backgroundColor: isDark ? AppTheme.darkPrimaryContainer : AppTheme.primaryContainer,
                  child: Icon(Icons.medical_services_rounded, size: 32, color: isDark ? AppTheme.darkPrimaryBlue : AppTheme.primaryBlue),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        doctorName,
                        style: TextStyle(
                          fontSize: 19,
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
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: isDark ? AppTheme.darkSuccessContainer : AppTheme.successContainer,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          appStatus?.verificationStatus.toUpperCase() ?? 'VERIFIED & ACTIVE',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: isDark ? AppTheme.darkSuccess : AppTheme.stitchTertiary,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            Divider(height: 28, color: isDark ? AppTheme.darkBorder : AppTheme.border),
            SwitchListTile.adaptive(
              key: const Key('doctor_home_dark_mode_switch'),
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
            if (appStatus?.specialty != null && appStatus!.specialty.isNotEmpty)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.local_hospital_rounded, color: AppTheme.primaryBlue),
                title: const Text('Specialty', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                subtitle: Text(appStatus.specialty, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
              ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.assignment_ind_rounded, color: AppTheme.primaryBlue),
              title: const Text('Verification & Documents', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              subtitle: const Text('View accreditation history and certificate status', style: TextStyle(fontSize: 14)),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () {
                Navigator.pop(ctx);
                Navigator.of(context).pushNamed('/doctor/application-status');
              },
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.dns_rounded, color: Colors.blueGrey),
              title: const Text('Server & Connectivity Settings', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              subtitle: const Text('Change host URL or toggle ADB reverse', style: TextStyle(fontSize: 14)),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () {
                Navigator.pop(ctx);
                ServerSettingsSheet.show(context);
              },
            ),
            const SizedBox(height: 16),
            const Center(
              child: Text(
                'MediConnect Doctor Portal v2.4 (Clinical Clarity)',
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

  @override
  Widget build(BuildContext context) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      try {
        Provider.of<NotificationProvider>(context, listen: false).refreshUnreadCount();
      } catch (_) {}
    });

    final authProvider = context.watch<AuthProvider>();
    final user = authProvider.user;
    final doctorName = user?.fullName.isNotEmpty == true
        ? (user!.fullName.startsWith('Dr.') ? user.fullName : 'Dr. ${user.fullName}')
        : 'Dr. Doctor';
    final specialty = authProvider.doctorApplicationStatus?.specialty ?? 'Cardiology Specialist';

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
            const MediConnectLogo(size: 26),
            const SizedBox(width: 8),
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
                  'Doctor Dashboard',
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
            tooltip: 'Logout',
            icon: const Icon(Icons.logout_rounded),
            onPressed: () => _handleLogout(context),
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 1. Clinician Header Card
              StitchCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Stack(
                          clipBehavior: Clip.none,
                          children: [
                            Container(
                              width: 54,
                              height: 54,
                              decoration: BoxDecoration(
                                color: AppTheme.primaryContainer,
                                borderRadius: BorderRadius.circular(14),
                              ),
                              alignment: Alignment.center,
                              child: const Icon(Icons.medical_services_rounded, size: 28, color: AppTheme.primaryBlue),
                            ),
                            Positioned(
                              bottom: -2,
                              right: -2,
                              child: Container(
                                width: 16,
                                height: 16,
                                decoration: const BoxDecoration(
                                  color: AppTheme.success,
                                  shape: BoxShape.circle,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Flexible(
                                    child: Text(
                                      doctorName,
                                      style: const TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.w700,
                                        color: AppTheme.textPrimary,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  const SizedBox(width: 4),
                                  const Icon(Icons.verified_rounded, size: 16, color: AppTheme.primaryBlue),
                                ],
                              ),
                              const SizedBox(height: 2),
                              Text(
                                specialty,
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.secondaryBlue,
                                ),
                              ),
                            ],
                          ),
                        ),
                        // On Duty Pulse Toggle Button
                        InkWell(
                          onTap: () {
                            setState(() => _isOnDuty = !_isOnDuty);
                          },
                          borderRadius: BorderRadius.circular(9999),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                            decoration: BoxDecoration(
                              color: _isOnDuty ? AppTheme.successContainer : AppTheme.surfaceContainerLow,
                              borderRadius: BorderRadius.circular(9999),
                              border: Border.all(
                                color: _isOnDuty ? AppTheme.success.withValues(alpha: 0.3) : AppTheme.border,
                              ),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Container(
                                  width: 6,
                                  height: 6,
                                  decoration: BoxDecoration(
                                    color: _isOnDuty ? AppTheme.success : AppTheme.textMuted,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                                const SizedBox(width: 5),
                                Text(
                                  _isOnDuty ? 'On Duty' : 'Off Duty',
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700,
                                    color: _isOnDuty ? AppTheme.stitchTertiary : AppTheme.textMuted,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                    const Divider(height: 24),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: const [
                            Icon(Icons.apartment_rounded, size: 15, color: AppTheme.secondaryBlue),
                            SizedBox(width: 4),
                            Text('National Hospital Center', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                          ],
                        ),
                        Row(
                          children: const [
                            Icon(Icons.today_rounded, size: 15, color: AppTheme.textSecondary),
                            SizedBox(width: 4),
                            Text('Today\'s Practice', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
                          ],
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),

              // 2. Urgent Clinical Alert Banner (Stitch)
              if (_showAlert) ...[
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppTheme.errorContainer,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppTheme.error.withValues(alpha: 0.2)),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(6),
                        decoration: const BoxDecoration(
                          color: AppTheme.error,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.warning_amber_rounded, color: Colors.white, size: 18),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text(
                                  'CRITICAL TELEMETRY ALERT',
                                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppTheme.error, letterSpacing: 0.5),
                                ),
                                const Text('3m ago', style: TextStyle(fontSize: 10, color: AppTheme.error)),
                              ],
                            ),
                            const SizedBox(height: 3),
                            const Text(
                              'ECG anomaly detected on Patient #9401 monitor. ST-elevation trigger requires physician review.',
                              style: TextStyle(fontSize: 12, color: Color(0xFF93000A), height: 1.3),
                            ),
                            const SizedBox(height: 10),
                            Row(
                              children: [
                                ElevatedButton.icon(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppTheme.error,
                                    foregroundColor: Colors.white,
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                    visualDensity: VisualDensity.compact,
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                                  ),
                                  onPressed: () {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(content: Text('Opening telemetry ECG strip viewer...')),
                                    );
                                  },
                                  icon: const Icon(Icons.monitor_heart_rounded, size: 14),
                                  label: const Text('Review Strip', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                                ),
                                const SizedBox(width: 8),
                                TextButton(
                                  style: TextButton.styleFrom(
                                    visualDensity: VisualDensity.compact,
                                    foregroundColor: AppTheme.error,
                                  ),
                                  onPressed: () => setState(() => _showAlert = false),
                                  child: const Text('Dismiss', style: TextStyle(fontSize: 11)),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
              ],

              // 3. Practice Overview KPI Metrics (2x2 Grid)
              const Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Practice Overview',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  StitchPulseBadge(label: 'LIVE STREAM', dotColor: AppTheme.secondaryBlue, backgroundColor: AppTheme.surfaceContainerLow),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: StitchCard(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: const [
                              Text('Appointments', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                              Icon(Icons.calendar_today_rounded, size: 16, color: AppTheme.primaryBlue),
                            ],
                          ),
                          const SizedBox(height: 8),
                          const Text('12 Patients', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppTheme.textPrimary)),
                          const SizedBox(height: 2),
                          const Text('4 video • 8 clinic', style: TextStyle(fontSize: 10, color: AppTheme.secondaryBlue)),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: StitchCard(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: const [
                              Text('Waiting Room', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                              Icon(Icons.hourglass_top_rounded, size: 16, color: AppTheme.secondaryBlue),
                            ],
                          ),
                          const SizedBox(height: 8),
                          const Text('3 In Queue', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppTheme.textPrimary)),
                          const SizedBox(height: 2),
                          const Text('Est. wait ~12m', style: TextStyle(fontSize: 10, color: AppTheme.success, fontWeight: FontWeight.w600)),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: StitchCard(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: const [
                              Text('Lab Reviews', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                              Icon(Icons.biotech_rounded, size: 16, color: AppTheme.textSecondary),
                            ],
                          ),
                          const SizedBox(height: 8),
                          const Text('5 Reports', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppTheme.textPrimary)),
                          const SizedBox(height: 2),
                          const Text('2 urgent results', style: TextStyle(fontSize: 10, color: AppTheme.error, fontWeight: FontWeight.w600)),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: StitchCard(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: const [
                              Text('Today\'s Total', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                              Icon(Icons.payments_rounded, size: 16, color: AppTheme.success),
                            ],
                          ),
                          const SizedBox(height: 8),
                          const Text('LKR 18,500', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppTheme.textPrimary)),
                          const SizedBox(height: 2),
                          const Text('+18% vs avg', style: TextStyle(fontSize: 10, color: AppTheme.success, fontWeight: FontWeight.w600)),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),

              // 4. Clinical Operations
              const Text(
                'Clinical Operations',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 10),

              // 1. Appointments Card
              _buildSectionCard(
                key: const Key('doctor_home_appointments_card'),
                icon: Icons.calendar_month_rounded,
                iconColor: AppTheme.primaryBlue,
                title: 'Appointments',
                subtitle: 'Review incoming requests, confirm, complete, or cancel bookings',
                onTap: () {
                  Navigator.of(context).pushNamed('/doctor/appointments');
                },
              ),
              const SizedBox(height: 10),

              // 2. Consultation Documentation & Prescriptions
              _buildSectionCard(
                key: const Key('doctor_home_consultations_card'),
                icon: Icons.edit_note_rounded,
                iconColor: AppTheme.secondaryBlue,
                title: 'Consultations & Prescriptions',
                subtitle: 'Document clinical notes, assessment, treatment plans & issue digital prescriptions',
                badgeText: 'Phase 21',
                badgeColor: AppTheme.primaryBlue,
                onTap: () {
                  Navigator.of(context).pushNamed('/doctor/consultations');
                },
              ),
              const SizedBox(height: 10),

              // 3. Manage Availability Card
              _buildSectionCard(
                key: const Key('doctor_home_manage_availability_card'),
                icon: Icons.event_available_rounded,
                iconColor: AppTheme.success,
                title: 'Manage Availability',
                subtitle: 'Configure upcoming working dates, hours, and slot durations',
                badgeText: 'Active',
                badgeColor: AppTheme.success,
                onTap: () {
                  Navigator.of(context).pushNamed('/doctor/manage-availability');
                },
              ),
              const SizedBox(height: 10),

              // 4. My Profile Card
              _buildSectionCard(
                key: const Key('doctor_home_my_profile_card'),
                icon: Icons.person_outline_rounded,
                iconColor: Colors.deepPurple,
                title: 'My Profile & Credentials',
                subtitle: 'View professional credentials, specialty, and clinic affiliation',
                onTap: () => _showDoctorProfile(context),
              ),
              const SizedBox(height: 10),

              // 5. Patient Reviews & Ratings
              _buildSectionCard(
                key: const Key('doctor_home_reviews_card'),
                icon: Icons.star_rounded,
                iconColor: Colors.amber.shade800,
                title: 'Patient Reviews & Ratings',
                subtitle: 'View verified patient feedback and rating distribution',
                onTap: () {
                  final auth = context.read<AuthProvider>();
                  Navigator.of(context).pushNamed(
                    '/patient/doctor-detail',
                    arguments: auth.user?.id,
                  );
                },
              ),
              const SizedBox(height: 10),

              // 6. Application Status Card
              _buildSectionCard(
                key: const Key('doctor_home_application_status_card'),
                icon: Icons.assignment_turned_in_outlined,
                iconColor: AppTheme.secondaryBlue,
                title: 'Application Status',
                subtitle: 'Review verification history and admin accreditation status',
                onTap: () {
                  Navigator.of(context).pushNamed('/doctor/application-status');
                },
              ),
              const SizedBox(height: 24),

              // 7. Logout Action Button
              OutlinedButton.icon(
                key: const Key('doctor_home_logout_button'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.error,
                  side: BorderSide(color: AppTheme.error.withValues(alpha: 0.3)),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () => _handleLogout(context),
                icon: const Icon(Icons.logout_rounded, size: 18),
                label: const Text('Sign Out of Doctor Portal', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionCard({
    required Key key,
    required IconData icon,
    required Color iconColor,
    required String title,
    required String subtitle,
    String? badgeText,
    Color? badgeColor,
    required VoidCallback onTap,
  }) {
    return StitchCard(
      key: key,
      onTap: onTap,
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: iconColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 24, color: iconColor),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    if (badgeText != null) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: (badgeColor ?? AppTheme.primaryBlue).withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          badgeText,
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: badgeColor ?? AppTheme.primaryBlue,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  subtitle,
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded, color: AppTheme.textSecondary),
        ],
      ),
    );
  }
}
