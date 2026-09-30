import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';

/// Screen displayed to doctors whose application is undergoing review,
/// has been rejected, or has been approved.
class DoctorApplicationStatusScreen extends StatefulWidget {
  const DoctorApplicationStatusScreen({super.key});

  @override
  State<DoctorApplicationStatusScreen> createState() =>
      _DoctorApplicationStatusScreenState();
}

class _DoctorApplicationStatusScreenState
    extends State<DoctorApplicationStatusScreen> {
  bool _isRefreshing = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadStatus();
    });
  }

  Future<void> _loadStatus() async {
    final authProvider = context.read<AuthProvider>();
    setState(() => _isRefreshing = true);
    await authProvider.fetchDoctorApplicationStatus();
    if (!mounted) return;
    setState(() => _isRefreshing = false);

    // If approved, optionally auto-route or notify
    final status = authProvider.doctorApplicationStatus;
    if (status?.isApproved == true) {
      Navigator.of(context).pushReplacementNamed('/doctor/home');
    }
  }

  Future<void> _handleLogout() async {
    final authProvider = context.read<AuthProvider>();
    await authProvider.logout();
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/welcome', (route) => false);
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final appStatus = authProvider.doctorApplicationStatus;
    final user = authProvider.user;

    final verificationStatus = appStatus?.verificationStatus.toUpperCase() ?? 'PENDING';
    final rejectionReason = appStatus?.rejectionReason;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Application Status'),
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            tooltip: 'Logout',
            icon: const Icon(Icons.logout_rounded),
            onPressed: _handleLogout,
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadStatus,
          color: AppTheme.primary,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 16),

                // Doctor Identity Header
                Center(
                  child: Column(
                    children: [
                      CircleAvatar(
                        radius: 36,
                        backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
                        child: const Icon(
                          Icons.person_rounded,
                          size: 40,
                          color: AppTheme.primary,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        user?.fullName != null ? 'Dr. ${user!.fullName}' : 'Doctor Applicant',
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      if (user?.email != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          user!.email,
                          style: const TextStyle(
                            fontSize: 14,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),

                const SizedBox(height: 32),

                // Status Content according to Verification Status
                if (verificationStatus == 'APPROVED') ...[
                  _buildApprovedCard(),
                ] else if (verificationStatus == 'REJECTED') ...[
                  _buildRejectedCard(rejectionReason),
                ] else ...[
                  _buildPendingCard(),
                ],

                const SizedBox(height: 32),

                // Action Buttons
                ElevatedButton.icon(
                  key: const Key('refresh_status_button'),
                  onPressed: _isRefreshing ? null : _loadStatus,
                  icon: _isRefreshing
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Icon(Icons.refresh_rounded, size: 20),
                  label: Text(_isRefreshing ? 'Refreshing...' : 'Refresh Status'),
                ),

                const SizedBox(height: 12),

                OutlinedButton.icon(
                  key: const Key('status_logout_button'),
                  onPressed: _handleLogout,
                  icon: const Icon(Icons.logout_rounded, size: 18),
                  label: const Text('Logout'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildPendingCard() {
    return Container(
      padding: const EdgeInsets.all(24),
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
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.amber.shade50,
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.hourglass_top_rounded,
              size: 48,
              color: Colors.amber.shade800,
            ),
          ),
          const SizedBox(height: 20),
          const Text(
            'Application Under Review',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'Your email has been verified and your doctor application has been submitted successfully.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 15,
              height: 1.5,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            'Our team will review your professional information and verification documents.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14,
              height: 1.4,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.amber.shade100,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.schedule_rounded,
                  size: 16,
                  color: Colors.amber.shade900,
                ),
                const SizedBox(width: 6),
                Text(
                  'Status: Pending',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.amber.shade900,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRejectedCard(String? rejectionReason) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.errorContainer,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.cancel_outlined,
              size: 48,
              color: AppTheme.error,
            ),
          ),
          const SizedBox(height: 20),
          const Text(
            'Application Rejected',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: AppTheme.error,
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'Unfortunately, your doctor verification application was not approved.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 15,
              height: 1.5,
              color: AppTheme.textSecondary,
            ),
          ),
          if (rejectionReason != null && rejectionReason.trim().isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppTheme.errorContainer.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.error.withValues(alpha: 0.2)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Reason for rejection:',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.error,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    rejectionReason,
                    style: const TextStyle(
                      fontSize: 14,
                      height: 1.4,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: AppTheme.errorContainer,
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.close_rounded,
                  size: 16,
                  color: AppTheme.error,
                ),
                SizedBox(width: 6),
                Text(
                  'Status: Rejected',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.error,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildApprovedCard() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.green.shade300),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.green.shade50,
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.check_circle_outline_rounded,
              size: 48,
              color: Colors.green.shade700,
            ),
          ),
          const SizedBox(height: 20),
          const Text(
            'Application Approved!',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'Congratulations, your verification has been approved. You now have full access to your doctor portal.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 15,
              height: 1.5,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: () {
              Navigator.of(context).pushReplacementNamed('/doctor/home');
            },
            child: const Text('Go to Doctor Portal'),
          ),
        ],
      ),
    );
  }
}
