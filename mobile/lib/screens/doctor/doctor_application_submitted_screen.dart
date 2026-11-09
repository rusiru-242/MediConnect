import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

/// Screen displayed immediately after a doctor submits their registration application.
/// Informs the doctor that their application is under administrative review and that
/// upon approval, an email will be sent with their registration details and doctor portal login link.
class DoctorApplicationSubmittedScreen extends StatelessWidget {
  final String fullName;
  final String email;
  final String? phone;
  final String specialty;
  final String medicalRegistrationNumber;
  final String hospitalOrClinic;

  const DoctorApplicationSubmittedScreen({
    super.key,
    required this.fullName,
    required this.email,
    this.phone,
    required this.specialty,
    required this.medicalRegistrationNumber,
    required this.hospitalOrClinic,
  });

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) {
          Navigator.of(context).pushNamedAndRemoveUntil('/welcome', (route) => false);
        }
      },
      child: Scaffold(
        backgroundColor: AppTheme.background,
        appBar: AppBar(
          title: const Text('Application Submitted'),
          automaticallyImplyLeading: false,
          centerTitle: true,
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 20.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 12),

                // Success Icon & Title Header
                Center(
                  child: Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryLight.withValues(alpha: 0.15),
                      shape: BoxShape.circle,
                      border: Border.all(color: AppTheme.primary.withValues(alpha: 0.3), width: 2),
                    ),
                    child: const Icon(
                      Icons.hourglass_top_rounded,
                      size: 56,
                      color: AppTheme.primary,
                    ),
                  ),
                ),
                const SizedBox(height: 20),

                Text(
                  'Application Submitted Successfully!',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                ),
                const SizedBox(height: 8),

                Text(
                  'Dear Dr. $fullName, thank you for applying to join the MediConnect medical network.',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 15,
                    color: AppTheme.textSecondary,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 24),

                // Approval Process Banner
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.amber.shade50,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.amber.shade300),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.mark_email_read_outlined, color: Colors.amber.shade900, size: 24),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Awaiting Administrative Review',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.bold,
                                color: Colors.amber.shade900,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              'Your credentials and verification documents are under review by the MediConnect administration team. '
                              'Once approved, an official confirmation email will be sent to your personal email ($email) '
                              'with your registered details and the doctor portal login link.',
                              style: TextStyle(
                                fontSize: 13,
                                color: Colors.brown.shade800,
                                height: 1.4,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),

                // Submitted Registration Details Card
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.border),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.04),
                        blurRadius: 10,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Submitted Details',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.amber.shade100,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.schedule_rounded, size: 14, color: Colors.amber.shade900),
                                const SizedBox(width: 4),
                                Text(
                                  'Pending Review',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: Colors.amber.shade900,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const Divider(height: 24),
                      _buildDetailRow('Doctor Name', 'Dr. $fullName'),
                      _buildDetailRow('Personal Email', email),
                      if (phone != null && phone!.isNotEmpty)
                        _buildDetailRow('Phone Number', phone!),
                      _buildDetailRow('Medical Reg No (SLMC)', medicalRegistrationNumber, highlight: true),
                      _buildDetailRow('Specialty', specialty),
                      _buildDetailRow('Hospital / Clinic', hospitalOrClinic),
                    ],
                  ),
                ),
                const SizedBox(height: 24),

                // What Happens Next Section
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'What happens next?',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 12),
                      _buildStepItem(
                        step: '1',
                        title: 'Document & SLMC Verification',
                        description: 'Administration staff will verify your medical license and submitted documents.',
                      ),
                      const SizedBox(height: 10),
                      _buildStepItem(
                        step: '2',
                        title: 'Approval Email Dispatched',
                        description: 'You will receive an approval confirmation email containing your registration summary and direct portal login link.',
                      ),
                      const SizedBox(height: 10),
                      _buildStepItem(
                        step: '3',
                        title: 'Clinical Dashboard Access',
                        description: 'Log into your doctor dashboard on web or mobile to configure your schedule and accept consultations.',
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 32),

                // Action Buttons
                ElevatedButton.icon(
                  key: const Key('submitted_back_to_login_button'),
                  onPressed: () {
                    Navigator.of(context).pushNamedAndRemoveUntil(
                      '/login',
                      (route) => false,
                    );
                  },
                  icon: const Icon(Icons.login_rounded, size: 20),
                  label: const Text('Back to Login'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                ),
                const SizedBox(height: 12),

                OutlinedButton.icon(
                  key: const Key('submitted_back_to_home_button'),
                  onPressed: () {
                    Navigator.of(context).pushNamedAndRemoveUntil(
                      '/welcome',
                      (route) => false,
                    );
                  },
                  icon: const Icon(Icons.home_outlined, size: 20),
                  label: const Text('Return to Home'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value, {bool highlight = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 130,
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 13,
                color: AppTheme.textSecondary,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 14,
                fontWeight: highlight ? FontWeight.bold : FontWeight.w600,
                color: highlight ? AppTheme.primary : AppTheme.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStepItem({
    required String step,
    required String title,
    required String description,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 22,
          height: 22,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: AppTheme.primary.withValues(alpha: 0.1),
            shape: BoxShape.circle,
          ),
          child: Text(
            step,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.bold,
              color: AppTheme.primary,
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                description,
                style: const TextStyle(
                  fontSize: 12,
                  color: AppTheme.textSecondary,
                  height: 1.3,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

