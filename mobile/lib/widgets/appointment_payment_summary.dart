import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/theme/app_theme.dart';
import '../models/appointment.dart';

/// "LKR 2,500" style formatting; null stays "Not available" (no invented amounts).
String formatMoney(double? amount, {String? currency}) {
  if (amount == null) return 'Not available';
  final code = (currency == null || currency.isEmpty ? 'lkr' : currency).toUpperCase();
  final whole = amount.truncateToDouble() == amount;
  final digits = amount.toStringAsFixed(whole ? 0 : 2);
  final parts = digits.split('.');
  final grouped = parts[0].replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},');
  return '$code $grouped${parts.length > 1 ? '.${parts[1]}' : ''}';
}

String paymentStatusLabel(Appointment a) {
  switch (a.paymentStatus) {
    case 'PAID':
      return 'Paid';
    case 'REFUNDED':
      return 'Refunded';
    case 'PENDING':
      return 'Payment pending';
    case 'FAILED':
      return 'Payment failed';
    case 'NOT_REQUIRED':
      return 'No payment required';
    default:
      return 'Not paid';
  }
}

/// Booking, payment and refund facts for one appointment (BUG-058 patient view, BUG-059 doctor view).
class AppointmentPaymentSummary extends StatelessWidget {
  final Appointment appointment;
  final bool showReference;

  const AppointmentPaymentSummary({super.key, required this.appointment, this.showReference = true});

  @override
  Widget build(BuildContext context) {
    final a = appointment;
    final rows = <Widget>[
      _row('Visit type', 'In-person visit', key: const Key('appt_visit_type')),
      _row('Consultation fee', formatMoney(a.bookedFee, currency: a.currency), key: const Key('appt_fee')),
      _row('Payment status', paymentStatusLabel(a),
          key: const Key('appt_payment_status'),
          color: a.isPaid ? AppTheme.success : (a.paymentStatus == 'REFUNDED' ? AppTheme.textSecondary : Colors.orange)),
      if (a.amountPaid != null)
        _row('Amount paid', formatMoney(a.amountPaid, currency: a.currency), key: const Key('appt_amount_paid')),
      if (a.paidAt != null)
        _row('Paid on', _date(a.paidAt!), key: const Key('appt_paid_at')),
      if (a.refundStatus != null)
        _row('Refund', _refund(a), key: const Key('appt_refund_status')),
    ];
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceVariant.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ...rows,
          if (showReference) ...[
            const Divider(height: 20),
            const Text('Booking reference', style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
            Row(
              children: [
                Expanded(
                  child: SelectableText(a.reference,
                      key: const Key('appt_booking_reference'),
                      style: const TextStyle(fontFamily: 'monospace', fontSize: 13, fontWeight: FontWeight.w600)),
                ),
                IconButton(
                  key: const Key('appt_copy_reference'),
                  tooltip: 'Copy booking reference',
                  icon: const Icon(Icons.copy_rounded, size: 18),
                  onPressed: () async {
                    await Clipboard.setData(ClipboardData(text: a.reference));
                    if (!context.mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Booking reference copied.')),
                    );
                  },
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  static String _date(DateTime t) {
    final l = t.toLocal();
    String two(int v) => v.toString().padLeft(2, '0');
    return '${l.year}-${two(l.month)}-${two(l.day)} ${two(l.hour)}:${two(l.minute)}';
  }

  static String _refund(Appointment a) {
    final amount = a.refundedAmount != null ? ' (${formatMoney(a.refundedAmount, currency: a.currency)})' : '';
    switch (a.refundStatus) {
      case 'requested':
      case 'under_review':
        return 'Requested - awaiting review';
      case 'processing':
        return 'Processing$amount';
      case 'succeeded':
        return 'Refunded$amount';
      case 'rejected':
        return 'Not approved';
      case 'failed':
        return 'Refund failed - support will follow up';
      default:
        return a.refundStatus!;
    }
  }

  Widget _row(String label, String value, {Key? key, Color? color}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: Text(label, style: const TextStyle(fontSize: 14, color: AppTheme.textSecondary))),
            Flexible(
              child: Text(value,
                  key: key,
                  textAlign: TextAlign.end,
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: color ?? AppTheme.textPrimary)),
            ),
          ],
        ),
      );
}
