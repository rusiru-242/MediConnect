import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import 'my_appointments_screen.dart';

/// Screen displayed after backend confirms payment succeeded and appointment is confirmed.
class PaymentSuccessScreen extends StatelessWidget {
  final String appointmentId;
  final String paymentId;
  final String doctorName;
  final String specialty;
  final String date;
  final String time;
  final double amount;
  final String currency;

  const PaymentSuccessScreen({
    super.key,
    required this.appointmentId,
    required this.paymentId,
    required this.doctorName,
    required this.specialty,
    required this.date,
    required this.time,
    required this.amount,
    this.currency = 'LKR',
  });

  @override
  Widget build(BuildContext context) {
    final formattedAmount =
        '${currency.toUpperCase()} ${amount.toStringAsFixed(2)}';

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) {
          Navigator.of(context).popUntil((route) => route.isFirst);
        }
      },
      child: Scaffold(
        backgroundColor: Colors.grey[50],
        appBar: AppBar(
          title: const Text('Confirmation'),
          automaticallyImplyLeading: false,
          elevation: 0,
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                const SizedBox(height: 20),
                // Success Badge
                Container(
                  width: 90,
                  height: 90,
                  decoration: BoxDecoration(
                    color: AppTheme.success.withValues(alpha: 0.12),
                    shape: BoxShape.circle,
                  ),
                  child: const Center(
                    child: Icon(
                      Icons.check_circle_rounded,
                      size: 64,
                      color: AppTheme.success,
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                const Text(
                  'Payment Successful',
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: Colors.black87,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Appointment Confirmed',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.primary,
                  ),
                ),
                const SizedBox(height: 32),

                // Details Card
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.04),
                        blurRadius: 12,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Column(
                    children: [
                      _buildDetailRow(
                        icon: Icons.person_outline,
                        label: 'Doctor',
                        value: doctorName.startsWith('Dr.')
                            ? doctorName
                            : 'Dr. $doctorName',
                        subtitle: specialty,
                      ),
                      const Divider(height: 28),
                      _buildDetailRow(
                        icon: Icons.calendar_today_outlined,
                        label: 'Date & Time',
                        value: '$date at $time',
                      ),
                      const Divider(height: 28),
                      _buildDetailRow(
                        icon: Icons.payments_outlined,
                        label: 'Amount Paid',
                        value: formattedAmount,
                        valueColor: AppTheme.success,
                      ),
                      const Divider(height: 28),
                      _buildDetailRow(
                        icon: Icons.tag,
                        label: 'Appointment ID',
                        value: appointmentId.length > 12
                            ? '${appointmentId.substring(0, 10)}...'
                            : appointmentId,
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 40),

                // Primary Button: View My Appointments
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton(
                    onPressed: () {
                      Navigator.pushAndRemoveUntil(
                        context,
                        MaterialPageRoute(
                          builder: (_) => const MyAppointmentsScreen(),
                        ),
                        (route) => route.isFirst,
                      );
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primary,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      elevation: 0,
                    ),
                    child: const Text(
                      'View My Appointments',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),

                // Secondary Button: Back to Home
                TextButton(
                  onPressed: () {
                    Navigator.of(context).popUntil((route) => route.isFirst);
                  },
                  child: Text(
                    'Back to Home',
                    style: TextStyle(
                      color: Colors.grey[700],
                      fontSize: 15,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDetailRow({
    required IconData icon,
    required String label,
    required String value,
    String? subtitle,
    Color? valueColor,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 20, color: Colors.grey[600]),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey[600],
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                value,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: valueColor ?? Colors.black87,
                ),
              ),
              if (subtitle != null && subtitle.isNotEmpty) ...[
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.grey[600],
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}
