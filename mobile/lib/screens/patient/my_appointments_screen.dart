import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../l10n/app_localizations.dart';
import '../../models/appointment.dart';
import '../../providers/locale_provider.dart';
import '../../services/appointment_service.dart';
import '../../widgets/medical_widgets.dart';
import 'appointment_detail_screen.dart';

/// Screen listing patient's appointments with tabs for Upcoming, Completed, and Cancelled.
/// Redesigned with Google Stitch Clinical Clarity design system (Phase 41).
class MyAppointmentsScreen extends StatefulWidget {
  final AppointmentService? appointmentService;

  const MyAppointmentsScreen({
    super.key,
    this.appointmentService,
  });

  @override
  State<MyAppointmentsScreen> createState() => _MyAppointmentsScreenState();
}

class _MyAppointmentsScreenState extends State<MyAppointmentsScreen>
    with SingleTickerProviderStateMixin {
  late final AppointmentService _appointmentService;
  late final TabController _tabController;

  bool _isLoading = false;
  String? _errorMessage;
  List<Appointment> _allAppointments = [];

  @override
  void initState() {
    super.initState();
    _appointmentService = widget.appointmentService ?? AppointmentService();
    _tabController = TabController(length: 3, vsync: this);
    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) {
        setState(() {});
      }
    });
    _loadAppointments();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAppointments() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await _appointmentService.getMyAppointments(limit: 50);
      if (!mounted) return;
      setState(() {
        _allAppointments = res.items;
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Failed to load appointments. Please check connection.';
        _isLoading = false;
      });
    }
  }

  List<Appointment> _filterAppointments(int tabIndex) {
    switch (tabIndex) {
      case 0: // Upcoming: PENDING or CONFIRMED
        return _allAppointments
            .where((a) => a.isPending || a.isConfirmed)
            .toList();
      case 1: // Completed
        return _allAppointments.where((a) => a.isCompleted).toList();
      case 2: // Cancelled
        return _allAppointments.where((a) => a.isCancelled).toList();
      default:
        return _allAppointments;
    }
  }

  Widget _buildAppointmentList(List<Appointment> appointments, AppLocalizations? l10n, LocaleProvider? localeProvider) {
    final isDark = AppTheme.isDark(context);
    final isSi = localeProvider?.currentLanguage == AppLanguage.sinhala;
    final isTa = localeProvider?.currentLanguage == AppLanguage.tamil;

    if (appointments.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.event_busy_rounded,
                size: 56,
                color: (isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary).withValues(alpha: 0.4),
              ),
              const SizedBox(height: 14),
              Text(
                isSi ? 'හමුවීම් කිසිවක් හමු නොවීය.' : (isTa ? 'சந்திப்புகள் எதுவும் இல்லை.' : 'No appointments found.'),
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                isSi
                    ? 'පහසුවෙන්ම සත්‍යාපිත විශේෂඥ වෛද්‍යවරුන් හමුවන්න.'
                    : (isTa
                        ? 'சரிபார்க்கப்பட்ட மருத்துவ நிபுணர்களுடன் எளிதாக முன்பதிவு செய்யுங்கள்.'
                        : 'Book consultations with verified medical specialists in a few taps.'),
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 13,
                  color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary,
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryBlue,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () {
                  Navigator.of(context).pushNamed('/patient/find-doctor');
                },
                icon: const Icon(Icons.add_rounded, size: 18),
                label: Text(l10n?.findDoctor ?? (isSi ? 'වෛද්‍යවරයකු සොයන්න' : (isTa ? 'மருத்துவரைத் தேடுங்கள்' : 'Find a Doctor'))),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadAppointments,
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        itemCount: appointments.length,
        itemBuilder: (context, index) {
          final appt = appointments[index];
          return _buildAppointmentCard(appt, l10n, localeProvider);
        },
      ),
    );
  }

  Widget _buildAppointmentCard(Appointment appt, AppLocalizations? l10n, LocaleProvider? localeProvider) {
    final isDark = AppTheme.isDark(context);
    final isSi = localeProvider?.currentLanguage == AppLanguage.sinhala;
    final isTa = localeProvider?.currentLanguage == AppLanguage.tamil;

    String statusLabel = appt.status.toUpperCase();
    if (appt.isConfirmed) {
      statusLabel = isSi ? 'තහවුරු විය' : (isTa ? 'உறுதியானது' : 'CONFIRMED');
    } else if (appt.isCancelled) {
      statusLabel = isSi ? 'අවලංගුයි' : (isTa ? 'ரத்து' : 'CANCELLED');
    } else if (appt.isCompleted) {
      statusLabel = isSi ? 'සම්පූර්ණයි' : (isTa ? 'முடிந்தது' : 'COMPLETED');
    } else if (appt.isPending) {
      statusLabel = isSi ? 'අපේක්ෂිත' : (isTa ? 'நிலுவை' : 'PENDING');
    }

    return StitchCard(
      key: Key('appointment_card_${appt.id}'),
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(16),
      onTap: () async {
        await Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => AppointmentDetailScreen(
              appointment: appt,
              appointmentId: appt.id,
              appointmentService: _appointmentService,
            ),
          ),
        );
        _loadAppointments();
      },
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Priority Top Status Banner
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    width: 7,
                    height: 7,
                    decoration: BoxDecoration(
                      color: appt.isConfirmed ? AppTheme.success : (appt.isCancelled ? AppTheme.error : AppTheme.warning),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    statusLabel,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.5,
                      color: appt.isConfirmed ? AppTheme.stitchTertiary : (appt.isCancelled ? AppTheme.error : AppTheme.warning),
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppTheme.primaryContainer,
                  borderRadius: BorderRadius.circular(9999),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.videocam_rounded, size: 13, color: AppTheme.primaryBlue),
                    const SizedBox(width: 4),
                    Text(
                      isSi ? 'වීඩියෝ හමුව' : (isTa ? 'வீடியோ சந்திப்பு' : 'Video Visit'),
                      style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: AppTheme.primaryBlue),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Doctor Profile Row
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: isDark ? AppTheme.darkSurfaceContainerLow : AppTheme.surfaceContainerLow,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: isDark ? AppTheme.darkBorder : AppTheme.border),
                ),
                alignment: Alignment.center,
                child: Icon(Icons.person_rounded, size: 26, color: isDark ? AppTheme.darkPrimaryBlue : AppTheme.primaryBlue),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      appt.doctorName ?? (isSi ? 'වෛද්‍ය පැතිකඩ' : (isTa ? 'மருத்துவர் சுயவிவரம்' : 'Doctor Profile')),
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      appt.specialty ?? (isSi ? 'සාමාන්‍ය වෛද්‍ය' : (isTa ? 'பொது மருத்துவம்' : 'General Medicine')),
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: isDark ? AppTheme.darkPrimaryBlue : AppTheme.secondaryBlue,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Schedule Meta Box
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: isDark ? AppTheme.darkSurfaceContainerLow : AppTheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Icon(Icons.calendar_today_rounded, size: 16, color: isDark ? AppTheme.darkPrimaryBlue : AppTheme.primaryBlue),
                    const SizedBox(width: 8),
                    Text(
                      appt.appointmentDate,
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary),
                    ),
                  ],
                ),
                Row(
                  children: [
                    Icon(Icons.access_time_rounded, size: 16, color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary),
                    const SizedBox(width: 6),
                    Text(
                      '${appt.startTime} - ${appt.endTime}',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Action Buttons
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
                    side: BorderSide(color: isDark ? AppTheme.darkBorder : AppTheme.border),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    minimumSize: const Size(0, 40),
                  ),
                  onPressed: () async {
                    await Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => AppointmentDetailScreen(
                          appointment: appt,
                          appointmentId: appt.id,
                          appointmentService: _appointmentService,
                        ),
                      ),
                    );
                    _loadAppointments();
                  },
                  child: Text(isSi ? 'විස්තර බලන්න' : (isTa ? 'விவரங்களை பார்' : 'View Details'), style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                ),
              ),
              if (appt.isConfirmed) ...[
                const SizedBox(width: 10),
                Expanded(
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primaryBlue,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      minimumSize: const Size(0, 40),
                    ),
                    onPressed: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            isSi
                                ? 'වීඩියෝ කාමරය සැසියට මිනිත්තු 10කට පෙර විවෘත වේ.'
                                : (isTa
                                    ? 'ஆலோசனை அறை 10 நிமிடங்களுக்கு முன் திறக்கப்படும்.'
                                    : 'Video session room opens 10 minutes prior to consultation.'),
                          ),
                        ),
                      );
                    },
                    icon: const Icon(Icons.videocam_rounded, size: 16),
                    label: Text(isSi ? 'සම්බන්ධ වන්න' : (isTa ? 'இணையுங்கள்' : 'Join Call'), style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = AppTheme.isDark(context);
    final l10n = AppLocalizations.of(context);
    LocaleProvider? localeProvider;
    try {
      localeProvider = Provider.of<LocaleProvider>(context);
    } catch (_) {
      localeProvider = null;
    }
    final isSi = localeProvider?.currentLanguage == AppLanguage.sinhala;
    final isTa = localeProvider?.currentLanguage == AppLanguage.tamil;

    return Scaffold(
      backgroundColor: isDark ? AppTheme.darkBackground : AppTheme.background,
      appBar: AppBar(
        backgroundColor: isDark ? AppTheme.darkSurface : Colors.white,
        elevation: 0,
        scrolledUnderElevation: 1,
        title: Text(
          l10n?.myAppointments ?? 'My Appointments',
          style: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w700,
            color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary,
          ),
        ),
        actions: [
          IconButton(
            key: const Key('my_appointments_payments_button'),
            icon: const Icon(Icons.receipt_long_rounded),
            tooltip: isSi ? 'ගෙවීම් ඉතිහාසය' : (isTa ? 'கட்டண வரலாறு' : 'Payment History'),
            onPressed: () => Navigator.of(context).pushNamed('/patient/payments'),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Subtitle & New Visit Action Row
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        isSi ? 'ඔබගේ සත්කාර ගමන' : (isTa ? 'உங்கள் பராமரிப்பு பயணம்' : 'YOUR CARE JOURNEY'),
                        style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppTheme.primaryBlue, letterSpacing: 1),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        isSi ? 'උපදේශන කාලසටහන' : (isTa ? 'ஆலோசனை அட்டவணை' : 'Consultation Schedule'),
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: isDark ? AppTheme.darkTextPrimary : AppTheme.textPrimary),
                      ),
                    ],
                  ),
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: isDark ? AppTheme.darkPrimaryContainer : AppTheme.primaryContainer,
                      foregroundColor: isDark ? AppTheme.darkPrimaryBlue : AppTheme.primaryBlue,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9999)),
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      minimumSize: Size.zero,
                    ),
                    onPressed: () {
                      Navigator.of(context).pushNamed('/patient/find-doctor');
                    },
                    icon: const Icon(Icons.add_rounded, size: 16),
                    label: Text(
                      isSi ? 'නව හමුවීමක්' : (isTa ? 'புதிய முன்பதிவு' : 'New Visit'),
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
            ),

            // Material 3 Segmented Filter Bar
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: isDark ? AppTheme.darkSurfaceContainerLow : AppTheme.surfaceContainerLow,
                borderRadius: BorderRadius.circular(9999),
              ),
              child: Row(
                children: [
                  _buildTabItem(
                    index: 0,
                    label: isSi ? 'ඉදිරි' : (isTa ? 'வரவிருக்கும்' : 'Upcoming'),
                    count: _filterAppointments(0).length,
                    isDark: isDark,
                  ),
                  _buildTabItem(
                    index: 1,
                    label: isSi ? 'සම්පූර්ණ වූ' : (isTa ? 'முடிந்தவை' : 'Completed'),
                    count: _filterAppointments(1).length,
                    isDark: isDark,
                  ),
                  _buildTabItem(
                    index: 2,
                    label: isSi ? 'අවලංගු වූ' : (isTa ? 'ரத்துசெய்தவை' : 'Cancelled'),
                    count: _filterAppointments(2).length,
                    isDark: isDark,
                  ),
                ],
              ),
            ),

            // Main Content Area
            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : _errorMessage != null
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(24),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(Icons.error_outline_rounded, color: AppTheme.error, size: 48),
                                const SizedBox(height: 12),
                                Text(
                                  _errorMessage!,
                                  textAlign: TextAlign.center,
                                  style: TextStyle(fontSize: 15, color: isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary),
                                ),
                                const SizedBox(height: 16),
                                ElevatedButton(
                                  onPressed: _loadAppointments,
                                  child: Text(l10n?.retry ?? (isSi ? 'නැවත උත්සාහ කරන්න' : (isTa ? 'மீண்டும் முயற்சி செய்க' : 'Retry'))),
                                ),
                              ],
                            ),
                          ),
                        )
                      : TabBarView(
                          controller: _tabController,
                          children: [
                            _buildAppointmentList(_filterAppointments(0), l10n, localeProvider),
                            _buildAppointmentList(_filterAppointments(1), l10n, localeProvider),
                            _buildAppointmentList(_filterAppointments(2), l10n, localeProvider),
                          ],
                        ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTabItem({required int index, required String label, required int count, bool isDark = false}) {
    final isSelected = _tabController.index == index;

    return Expanded(
      child: InkWell(
        onTap: () {
          _tabController.animateTo(index);
        },
        borderRadius: BorderRadius.circular(9999),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: isSelected ? AppTheme.primaryBlue : Colors.transparent,
            borderRadius: BorderRadius.circular(9999),
          ),
          alignment: Alignment.center,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w600,
                  color: isSelected ? Colors.white : (isDark ? AppTheme.darkTextSecondary : AppTheme.textSecondary),
                ),
              ),
              const SizedBox(width: 3),
              Text(
                '($count)',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                  color: isSelected ? Colors.white70 : (isDark ? AppTheme.darkTextMuted : AppTheme.textMuted),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
