import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';
import '../models/appointment.dart';
import '../services/appointment_service.dart';

/// Next upcoming appointment from the patient's real bookings (Phase 01).
///
/// Replaces a hard-coded "Dr. Alexander Wright" video-consultation card. MediConnect bookings are in-person
/// clinic visits, so no video badge or "Join Call" button is shown. When there is no upcoming appointment, or the
/// list cannot be loaded, a truthful empty/error state is shown instead of placeholder data.
class UpcomingAppointmentCard extends StatefulWidget {
  /// Loads the patient's appointments; defaults to [AppointmentService.getMyAppointments]. Injected in tests.
  final Future<List<Appointment>> Function()? loader;
  final bool isSi;
  final bool isTa;

  /// Localized section title from the app's l10n (falls back to built-in text).
  final String? title;

  const UpcomingAppointmentCard({super.key, this.loader, this.isSi = false, this.isTa = false, this.title});

  @override
  State<UpcomingAppointmentCard> createState() => _UpcomingAppointmentCardState();
}

class _UpcomingAppointmentCardState extends State<UpcomingAppointmentCard> {
  late Future<Appointment?> _next;

  @override
  void initState() {
    super.initState();
    _next = _loadNext();
  }

  Future<Appointment?> _loadNext() async {
    final items = await (widget.loader ?? () async => (await AppointmentService().getMyAppointments(limit: 50)).items)();
    final now = DateTime.now();
    DateTime? startOf(Appointment a) => DateTime.tryParse('${a.appointmentDate}T${a.startTime.length == 5 ? '${a.startTime}:00' : a.startTime}');
    final upcoming = items.where((a) {
      final status = a.status.toUpperCase();
      final start = startOf(a);
      return (status == 'CONFIRMED' || status == 'PENDING') && start != null && start.isAfter(now);
    }).toList()
      ..sort((a, b) => startOf(a)!.compareTo(startOf(b)!));
    return upcoming.isEmpty ? null : upcoming.first;
  }

  String _t(String en, String si, String ta) => widget.isSi ? si : (widget.isTa ? ta : en);

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      key: const Key('upcoming_appointment_card'),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? AppTheme.darkSurface : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: isDark ? AppTheme.darkBorder : AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  widget.title ?? _t('Upcoming Appointments', 'ඉදිරි හමුවීම්', 'வரவிருக்கும் சந்திப்புகள்'),
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
              ),
              TextButton(
                onPressed: () => Navigator.of(context).pushNamed('/patient/my-appointments'),
                child: Text(_t('View All', 'සියල්ල', 'அனைத்தும்')),
              ),
            ],
          ),
          const SizedBox(height: 8),
          FutureBuilder<Appointment?>(
            future: _next,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Center(child: SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2))),
                );
              }
              if (snapshot.hasError) {
                return _message(
                  key: const Key('upcoming_appointment_error'),
                  icon: Icons.cloud_off_rounded,
                  text: _t('Your appointments could not be loaded. Open My Appointments to try again.',
                      'ඔබගේ වෛද්‍ය හමුවීම් ලබාගත නොහැකි විය. නැවත උත්සාහ කිරීමට My Appointments විවෘත කරන්න.',
                      'உங்கள் சந்திப்புகளை ஏற்ற முடியவில்லை. மீண்டும் முயற்சிக்க My Appointments ஐத் திறக்கவும்.'),
                );
              }
              final appointment = snapshot.data;
              if (appointment == null) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _message(
                      key: const Key('upcoming_appointment_empty'),
                      icon: Icons.event_available_outlined,
                      text: _t('You have no upcoming appointments.', 'ඔබට ඉදිරි වෛද්‍ය හමුවීම් නැත.',
                          'உங்களுக்கு வரவிருக்கும் சந்திப்புகள் இல்லை.'),
                    ),
                    const SizedBox(height: 8),
                    OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(minimumSize: const Size(double.infinity, 44)),
                      onPressed: () => Navigator.of(context).pushNamed('/patient/find-doctor'),
                      icon: const Icon(Icons.search_rounded, size: 18),
                      label: Text(_t('Find a Doctor', 'වෛද්‍යවරයෙකු සොයන්න', 'மருத்துவரைத் தேடுங்கள்')),
                    ),
                  ],
                );
              }
              final pending = appointment.status.toUpperCase() == 'PENDING';
              return Row(
                key: const Key('upcoming_appointment_item'),
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 46,
                    height: 46,
                    decoration: BoxDecoration(color: AppTheme.primaryContainer, borderRadius: BorderRadius.circular(12)),
                    child: const Icon(Icons.local_hospital_rounded, color: AppTheme.primaryBlue),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(appointment.doctorName ?? _t('Doctor', 'වෛද්‍යවරයා', 'மருத்துவர்'),
                            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                        if ((appointment.specialty ?? '').isNotEmpty)
                          Text(appointment.specialty!, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                        const SizedBox(height: 4),
                        Text('${appointment.appointmentDate} · ${appointment.startTime}–${appointment.endTime}',
                            style: const TextStyle(fontSize: 13)),
                        Text(
                          [
                            _t('In-person visit', 'රෝහලේදී හමුව', 'நேரில் சந்திப்பு'),
                            if ((appointment.hospitalOrClinic ?? '').isNotEmpty) appointment.hospitalOrClinic!,
                          ].join(' · '),
                          style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
                        ),
                        if (pending)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(_t('Awaiting payment confirmation', 'ගෙවීම තහවුරු වෙමින් පවතී', 'கட்டண உறுதிப்படுத்தல் நிலுவையில்'),
                                style: const TextStyle(fontSize: 12, color: AppTheme.warning, fontWeight: FontWeight.w600)),
                          ),
                      ],
                    ),
                  ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _message({required Key key, required IconData icon, required String text}) {
    return Row(
      key: key,
      children: [
        Icon(icon, size: 20, color: AppTheme.textSecondary),
        const SizedBox(width: 8),
        Expanded(child: Text(text, style: const TextStyle(fontSize: 13.5, color: AppTheme.textSecondary))),
      ],
    );
  }
}
