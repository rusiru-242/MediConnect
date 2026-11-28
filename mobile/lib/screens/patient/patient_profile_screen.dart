import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../l10n/app_localizations.dart';
import '../../models/patient_profile.dart';
import '../../providers/auth_provider.dart';
import '../../providers/locale_provider.dart';
import '../../services/profile_service.dart';
import '../../widgets/language_selector_sheet.dart';
import '../../widgets/medical_widgets.dart';
import '../../widgets/mediconnect_logo.dart';
import '../../widgets/profile_picture_editor.dart';
import '../../widgets/server_settings_sheet.dart';
import '../../widgets/user_avatar.dart';
import 'edit_patient_profile_screen.dart';

/// Patient profile (R02).
///
/// Shows only data the patient or their clinicians actually recorded. The previous version displayed invented
/// values (A05-O1): height, weight, BMI "Normal", a "Penicillin" allergy, a spouse emergency contact, an insurance
/// policy, a patient number, age, sex and blood type, and record counts. Missing values now read "Not provided".
class PatientProfileScreen extends StatefulWidget {
  final ProfileService? service;

  const PatientProfileScreen({super.key, this.service});

  @override
  State<PatientProfileScreen> createState() => _PatientProfileScreenState();
}

class _PatientProfileScreenState extends State<PatientProfileScreen> {
  static const notProvided = 'Not provided';
  late final ProfileService _service = widget.service ?? ProfileService();
  bool _isLoggingOut = false;
  bool _loading = true;
  String? _loadError;
  PatientProfile? _profile;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final profile = await _service.myProfile();
      if (!mounted) return;
      setState(() {
        _profile = profile;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _loadError = 'Your profile details could not be loaded.';
      });
    }
  }

  Future<void> _handleLogout() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Confirm Logout', style: TextStyle(fontWeight: FontWeight.bold)),
        content: const Text('Are you sure you want to log out of MediConnect?'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
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
    if (confirm != true || !mounted) return;
    setState(() => _isLoggingOut = true);
    await context.read<AuthProvider>().logout();
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/welcome', (route) => false);
  }

  Future<void> _edit() async {
    final current = _profile;
    if (current == null) return;
    final updated = await Navigator.of(context).push<PatientProfile>(MaterialPageRoute(
      builder: (_) => EditPatientProfileScreen(profile: current, service: _service),
    ));
    if (updated != null && mounted) {
      setState(() => _profile = updated);
      context.read<AuthProvider>().updateFullName(updated.fullName);
    }
  }

  void _changePhoto(String? currentUrl) {
    ProfilePictureEditor.open(
      context,
      currentUrl: currentUrl,
      service: _service,
      onChanged: (url) => context.read<AuthProvider>().updateProfileImage(url),
    );
  }

  String _fmt(double? v, String unit) =>
      v == null ? notProvided : '${v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(1)} $unit';

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    final l10n = AppLocalizations.of(context);
    final name = (_profile?.fullName.isNotEmpty == true ? _profile!.fullName : user?.fullName) ?? '';
    final email = _profile?.email ?? user?.email;
    final phone = _profile?.phone ?? user?.phone;
    final avatarUrl = user?.profileImage;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        scrolledUnderElevation: 1,
        title: Row(
          children: [
            const MediConnectLogo(size: 34),
            const SizedBox(width: 8),
            Text(
              l10n?.profile ?? 'Patient Profile',
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: AppTheme.textPrimary),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.language_rounded),
            tooltip: l10n?.language ?? 'Language',
            onPressed: () => LanguageSelectorSheet.show(context),
          ),
          IconButton(
            icon: const Icon(Icons.dns_rounded),
            tooltip: 'Server Settings',
            onPressed: () => ServerSettingsSheet.show(context),
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            tooltip: l10n?.logout ?? 'Logout',
            onPressed: _isLoggingOut ? null : _handleLogout,
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // 1. Identity card
                StitchCard(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Semantics(
                        button: true,
                        label: 'Change profile photo',
                        child: InkWell(
                          key: const Key('profile_avatar_edit'),
                          customBorder: const CircleBorder(),
                          onTap: () => _changePhoto(avatarUrl),
                          child: Stack(
                            clipBehavior: Clip.none,
                            children: [
                              Container(
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  border: Border.all(color: AppTheme.primaryBlue.withValues(alpha: 0.3), width: 2),
                                ),
                                child: UserAvatar(
                                  key: const Key('profile_avatar'),
                                  imageUrl: avatarUrl,
                                  size: 68,
                                  fallback: const ColoredBox(
                                    color: AppTheme.primaryContainer,
                                    child: Icon(Icons.person_rounded, size: 40, color: AppTheme.primaryBlue),
                                  ),
                                ),
                              ),
                              Positioned(
                                bottom: -2,
                                right: -2,
                                child: Container(
                                  width: 26,
                                  height: 26,
                                  decoration: BoxDecoration(
                                    color: AppTheme.primaryBlue,
                                    shape: BoxShape.circle,
                                    border: Border.all(color: Colors.white, width: 2),
                                  ),
                                  child: const Icon(Icons.photo_camera_rounded, size: 14, color: Colors.white),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              name.isNotEmpty ? name : notProvided,
                              key: const Key('profile_name'),
                              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: AppTheme.textPrimary),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            const SizedBox(height: 3),
                            Text(email?.isNotEmpty == true ? email! : notProvided,
                                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                            const SizedBox(height: 2),
                            Text(phone?.isNotEmpty == true ? phone! : 'Phone: $notProvided',
                                key: const Key('profile_phone'),
                                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                            const SizedBox(height: 10),
                            OutlinedButton.icon(
                              key: const Key('profile_edit'),
                              style: OutlinedButton.styleFrom(
                                minimumSize: const Size(0, 40),
                                foregroundColor: AppTheme.primaryBlue,
                                side: const BorderSide(color: AppTheme.border),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9999)),
                              ),
                              onPressed: _profile == null ? null : _edit,
                              icon: const Icon(Icons.edit_outlined, size: 16),
                              label: const Text('Edit Profile', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 18),

                // 2. Health summary (patient-reported)
                Row(
                  children: [
                    const Expanded(
                      child: Text('Health Summary',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                    ),
                    if (_profile != null)
                      const Text('Entered by you', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                  ],
                ),
                const SizedBox(height: 10),
                if (_loading)
                  const Padding(
                    padding: EdgeInsets.all(16),
                    child: Center(child: CircularProgressIndicator(key: Key('profile_loading'))),
                  )
                else if (_loadError != null)
                  StitchCard(
                    key: const Key('profile_error'),
                    child: Column(
                      children: [
                        Text(_loadError!, textAlign: TextAlign.center),
                        const SizedBox(height: 8),
                        TextButton.icon(
                          key: const Key('profile_retry'),
                          onPressed: _load,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Retry'),
                        ),
                      ],
                    ),
                  )
                else ...[
                  Row(
                    children: [
                      _statTile('Height', _fmt(_profile!.heightCm, 'cm'), const Key('stat_height')),
                      const SizedBox(width: 8),
                      _statTile('Weight', _fmt(_profile!.weightKg, 'kg'), const Key('stat_weight')),
                      const SizedBox(width: 8),
                      _statTile('BMI', _profile!.bmi == null ? notProvided : _profile!.bmi!.toStringAsFixed(1),
                          const Key('stat_bmi')),
                    ],
                  ),
                  if (_profile!.bmiNote != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(_profile!.bmiNote!,
                          key: const Key('stat_bmi_note'),
                          style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                    ),
                  const SizedBox(height: 12),
                  _allergyCard(_profile!),
                ],
                const SizedBox(height: 18),

                // 3. Records (navigation only; no invented counts or dates)
                const Text('Health Records & Documents',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                const SizedBox(height: 10),
                StitchCard(
                  padding: EdgeInsets.zero,
                  child: Column(
                    children: [
                      _tile(icon: Icons.history_edu_rounded, title: 'Medical Records',
                          subtitle: 'Your records, reports and uploaded documents',
                          onTap: () => Navigator.of(context).pushNamed('/patient/medical-records')),
                      const Divider(height: 1),
                      _tile(icon: Icons.receipt_long_rounded, title: 'Medication Reminders',
                          subtitle: 'Your medicines and reminder schedule',
                          onTap: () => Navigator.of(context).pushNamed('/patient/medication-reminders')),
                      const Divider(height: 1),
                      _tile(icon: Icons.payments_outlined, title: 'Payment History',
                          subtitle: 'Consultation payments and receipts',
                          onTap: () => Navigator.of(context).pushNamed('/patient/payments')),
                    ],
                  ),
                ),
                const SizedBox(height: 18),

                // A05 (Agent 26): Help & Support
                StitchCard(
                  padding: EdgeInsets.zero,
                  child: _tile(
                    key: const Key('profile_help_support'),
                    icon: Icons.support_agent_rounded,
                    title: 'Help & Support',
                    subtitle: 'Your support tickets and replies',
                    onTap: () => Navigator.of(context).pushNamed('/patient/support'),
                  ),
                ),
                const SizedBox(height: 18),

                // 4. Emergency contact (only what the patient entered)
                const Text('Emergency Contact',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                const SizedBox(height: 10),
                StitchCard(
                  key: const Key('profile_emergency_contact'),
                  padding: const EdgeInsets.all(14),
                  child: Row(
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: AppTheme.errorContainer,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.contact_phone_rounded, color: AppTheme.error, size: 20),
                      ),
                      const SizedBox(width: 12),
                      Expanded(child: _emergencyText()),
                      if (_profile != null)
                        TextButton(
                          onPressed: _edit,
                          child: Text(_profile!.emergencyContact == null ? 'Add' : 'Edit'),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),

                // 5. Settings
                Text(l10n?.settings ?? 'Settings',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                const SizedBox(height: 10),
                StitchCard(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  child: Builder(builder: (context) {
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
                        width: 38,
                        height: 38,
                        decoration: BoxDecoration(
                          color: AppTheme.primaryContainer,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.language_rounded, color: AppTheme.primary, size: 20),
                      ),
                      title: Text(l10n?.language ?? 'Language',
                          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                      subtitle: Text(langName,
                          style: const TextStyle(fontSize: 12, color: AppTheme.primary, fontWeight: FontWeight.w600)),
                      trailing: const Icon(Icons.chevron_right_rounded, color: AppTheme.textSecondary),
                      onTap: () => LanguageSelectorSheet.show(context),
                    );
                  }),
                ),
                const SizedBox(height: 24),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.error,
                    side: BorderSide(color: AppTheme.error.withValues(alpha: 0.3)),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    minimumSize: const Size(double.infinity, 46),
                  ),
                  onPressed: _isLoggingOut ? null : _handleLogout,
                  icon: const Icon(Icons.logout_rounded, size: 18),
                  label: const Text('Log Out', style: TextStyle(fontWeight: FontWeight.w700)),
                ),
                const SizedBox(height: 20),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _emergencyText() {
    if (_profile == null) {
      // Unknown until the profile loads: never claim "Not provided" for data we have not read.
      return Text(_loading ? 'Loading...' : 'Unavailable',
          style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary));
    }
    final contact = _profile!.emergencyContact;
    if (contact == null) {
      return const Text(notProvided,
          key: Key('emergency_not_provided'),
          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textSecondary));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          contact.relationship?.isNotEmpty == true ? '${contact.name} (${contact.relationship})' : contact.name,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.textPrimary),
        ),
        const SizedBox(height: 2),
        SelectableText(contact.phone, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
      ],
    );
  }

  Widget _allergyCard(PatientProfile p) {
    final String reported;
    switch (p.allergyStatus) {
      case PatientProfile.noneKnown:
        reported = 'No known allergies';
        break;
      case PatientProfile.hasAllergies:
        reported = p.allergies.join(', ');
        break;
      default:
        reported = notProvided;
    }
    return StitchCard(
      key: const Key('profile_allergies'),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Allergies', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
          const SizedBox(height: 6),
          Text('Reported by you: $reported',
              key: const Key('allergies_reported'), style: const TextStyle(fontSize: 12, color: AppTheme.textPrimary)),
          if (p.recordedAllergies.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text('In your medical record:',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
            for (final a in p.recordedAllergies)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  '${a.allergen}${a.severity != null ? ' (${a.severity})' : ''} - ${a.sourceLabel}'
                  '${a.clinicalDate != null ? ', ${a.clinicalDate}' : ''}',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
              ),
          ],
        ],
      ),
    );
  }

  Widget _statTile(String title, String value, Key key) {
    final missing = value == notProvided;
    return Expanded(
      child: Container(
        key: key,
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 6),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.border),
        ),
        child: Column(
          children: [
            Text(title, style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text(
              value,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: missing ? 11 : 14,
                fontWeight: missing ? FontWeight.w500 : FontWeight.w800,
                color: missing ? AppTheme.textSecondary : AppTheme.textPrimary,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }

  Widget _tile({
    Key? key,
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    return ListTile(
      key: key,
      leading: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(color: AppTheme.primaryContainer, borderRadius: BorderRadius.circular(8)),
        child: Icon(icon, color: AppTheme.primaryBlue, size: 20),
      ),
      title: Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
      subtitle: Text(subtitle, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
      trailing: const Icon(Icons.chevron_right_rounded, size: 20, color: AppTheme.textSecondary),
      onTap: onTap,
    );
  }
}
