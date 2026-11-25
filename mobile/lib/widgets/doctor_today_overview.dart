import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';
import '../models/appointment.dart';
import '../services/appointment_service.dart';
import 'appointment_payment_summary.dart';

/// Today's practice figures from the doctor's real appointments (Phase 02).
///
/// Replaces a hard-coded "Practice Overview" ("12 Patients · 4 video · 8 clinic", "3 In Queue", "5 Reports",
/// "LKR 18,500 +18%", "LIVE STREAM"). Visits are in-person only, the amount is the sum of verified payments for
/// today's appointments, and figures without a data source are not shown.
class DoctorTodayOverview extends StatefulWidget {
  /// Loads today's appointments (Sri Lanka date); defaults to [AppointmentService.getDoctorAppointments].
  final Future<List<Appointment>> Function(String date)? loader;
  final bool isSi;
  final bool isTa;

  const DoctorTodayOverview({super.key, this.loader, this.isSi = false, this.isTa = false});

  /// Today's date in Asia/Colombo (UTC+05:30, no daylight saving).
  static String colomboToday([DateTime? now]) {
    final t = (now ?? DateTime.now()).toUtc().add(const Duration(hours: 5, minutes: 30));
    String two(int v) => v.toString().padLeft(2, '0');
    return '${t.year}-${two(t.month)}-${two(t.day)}';
  }

  @override
  State<DoctorTodayOverview> createState() => _DoctorTodayOverviewState();
}

class _DoctorTodayOverviewState extends State<DoctorTodayOverview> {
  late Future<List<Appointment>> _today;

  @override
  void initState() {
    super.initState();
    final date = DoctorTodayOverview.colomboToday();
    _today = (widget.loader ??
        (d) async => (await AppointmentService().getDoctorAppointments(date: d, limit: 50)).items)(date);
  }

  String _t(String en, String si, String ta) => widget.isSi ? si : (widget.isTa ? ta : en);

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Appointment>>(
      future: _today,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const SizedBox(height: 72, child: Center(child: CircularProgressIndicator(strokeWidth: 2)));
        }
        if (snap.hasError) {
          return Text(
            _t("Today's figures are unavailable right now.", 'අද දින දත්ත දැනට ලබාගත නොහැක.',
                'இன்றைய தரவு தற்போது கிடைக்கவில்லை.'),
            key: const Key('doctor_today_error'),
            style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          );
        }
        final items = (snap.data ?? const <Appointment>[]).where((a) => !a.isCancelled).toList();
        final paid = items.where((a) => a.amountPaid != null).toList();
        final total = paid.fold<double>(0, (sum, a) => sum + a.amountPaid!);
        final currency = paid.isNotEmpty ? paid.first.currency : null;
        return Row(
          children: [
            Expanded(
              child: _tile(
                key: const Key('doctor_today_appointments'),
                label: _t('Appointments today', 'අද හමුවීම්', 'இன்றைய சந்திப்புகள்'),
                value: '${items.length}',
                note: _t('In-person visits', 'සායන හමුවීම්', 'நேரடி வருகைகள்'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _tile(
                key: const Key('doctor_today_paid_total'),
                label: _t('Paid today', 'අද ගෙවූ මුදල', 'இன்று செலுத்தியது'),
                value: paid.isEmpty ? formatMoney(0, currency: currency) : formatMoney(total, currency: currency),
                note: _t('${paid.length} verified payment(s)', 'තහවුරු ගෙවීම් ${paid.length}',
                    '${paid.length} உறுதிப்படுத்திய கட்டணம்'),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _tile({required Key key, required String label, required String value, required String note}) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isDark ? AppTheme.darkSurface : Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: isDark ? AppTheme.darkBorder : AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary), overflow: TextOverflow.ellipsis),
          const SizedBox(height: 6),
          Text(value, key: key, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(note, style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary), overflow: TextOverflow.ellipsis),
        ],
      ),
    );
  }
}
