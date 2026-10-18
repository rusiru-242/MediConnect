import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/notification_provider.dart';
import '../../widgets/notification_bell_button.dart';
import '../../widgets/server_settings_sheet.dart';

/// Doctor Home Screen foundation displaying welcome greeting and key operational cards.
class DoctorHomeScreen extends StatelessWidget {
  const DoctorHomeScreen({super.key});

  Future<void> _handleLogout(BuildContext context) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirm Logout'),
        content: const Text('Are you sure you want to log out of your Doctor account?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
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

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
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
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            Row(
              children: [
                CircleAvatar(
                  radius: 30,
                  backgroundColor: AppTheme.primaryContainer,
                  child: const Icon(Icons.medical_services_rounded, size: 32, color: AppTheme.onPrimaryContainer),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        doctorName,
                        style: const TextStyle(fontSize: 19, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        user?.email ?? '',
                        style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                      ),
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.green.shade100,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          appStatus?.verificationStatus.toUpperCase() ?? 'VERIFIED & ACTIVE',
                          style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.green.shade800),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const Divider(height: 32),
            if (appStatus?.specialty != null && appStatus!.specialty.isNotEmpty)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.local_hospital_rounded, color: AppTheme.primary),
                title: const Text('Specialty', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                subtitle: Text(appStatus.specialty, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
              ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.assignment_ind_rounded, color: Colors.teal),
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
                'MediConnect Doctor Portal v1.0.0 (RC-1)',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
            ),
            const SizedBox(height: 8),
          ],
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

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('MediConnect Doctor'),
        actions: [
          const NotificationBellButton(),
          IconButton(
            tooltip: 'Logout',
            icon: const Icon(Icons.logout_rounded),
            onPressed: () => _handleLogout(context),
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Welcome Header Card
              Card(
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                elevation: 1,
                child: Padding(
                  padding: const EdgeInsets.all(20.0),
                  child: Row(
                    children: [
                      CircleAvatar(
                        radius: 28,
                        backgroundColor: AppTheme.primaryContainer,
                        child: const Icon(
                          Icons.medical_services_rounded,
                          size: 30,
                          color: AppTheme.onPrimaryContainer,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Welcome, $doctorName',
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              user?.email ?? '',
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppTheme.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 24),

              const Text(
                'Dashboard Sections',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 12),

              // 1. Appointments Card
              _buildSectionCard(
                key: const Key('doctor_home_appointments_card'),
                icon: Icons.calendar_month_rounded,
                iconColor: Colors.blueAccent,
                title: 'Appointments',
                subtitle: 'Review incoming requests, confirm, complete, or cancel bookings',
                onTap: () {
                  Navigator.of(context).pushNamed('/doctor/appointments');
                },
              ),

              const SizedBox(height: 12),

              // Consultation Documentation & Prescriptions (Phase 21)
              _buildSectionCard(
                key: const Key('doctor_home_consultations_card'),
                icon: Icons.edit_note_rounded,
                iconColor: Colors.teal,
                title: 'Consultations & Prescriptions',
                subtitle: 'Document clinical notes, assessment, treatment plans & issue digital prescriptions',
                badgeText: 'Phase 21',
                badgeColor: AppTheme.primary,
                onTap: () {
                  Navigator.of(context).pushNamed('/doctor/consultations');
                },
              ),

              const SizedBox(height: 12),

              // 2. Manage Availability Card (FULLY FUNCTIONAL)
              _buildSectionCard(
                key: const Key('doctor_home_manage_availability_card'),
                icon: Icons.event_available_rounded,
                iconColor: AppTheme.primary,
                title: 'Manage Availability',
                subtitle: 'Configure upcoming working dates, hours, and slot durations',
                badgeText: 'Active',
                badgeColor: AppTheme.success,
                onTap: () {
                  Navigator.of(context).pushNamed('/doctor/manage-availability');
                },
              ),

              const SizedBox(height: 12),

              // 2. My Profile Card
              _buildSectionCard(
                key: const Key('doctor_home_my_profile_card'),
                icon: Icons.person_outline_rounded,
                iconColor: Colors.deepPurple,
                title: 'My Profile',
                subtitle: 'View professional credentials, specialty, and clinic affiliation',
                onTap: () => _showDoctorProfile(context),
              ),

              const SizedBox(height: 12),

              // Patient Reviews & Ratings (Phase 23)
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

              const SizedBox(height: 12),

              // 3. Application Status Card
              _buildSectionCard(
                key: const Key('doctor_home_application_status_card'),
                icon: Icons.assignment_turned_in_outlined,
                iconColor: Colors.teal,
                title: 'Application Status',
                subtitle: 'Review verification history and admin accreditation status',
                onTap: () {
                  Navigator.of(context).pushNamed('/doctor/application-status');
                },
              ),

              const SizedBox(height: 32),

              // 4. Logout Action
              OutlinedButton.icon(
                key: const Key('doctor_home_logout_button'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.error,
                  side: const BorderSide(color: AppTheme.error),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: () => _handleLogout(context),
                icon: const Icon(Icons.logout_rounded, size: 18),
                label: const Text('Logout', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
              ),
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
    return Card(
      key: key,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 1,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: iconColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, size: 26, color: iconColor),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          title,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                        if (badgeText != null) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: (badgeColor ?? AppTheme.primary).withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              badgeText,
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                                color: badgeColor ?? AppTheme.primary,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 4),
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
        ),
      ),
    );
  }
}
