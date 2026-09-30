import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../models/admin_doctor_application.dart';
import '../../providers/admin_provider.dart';
import 'document_viewer_screen.dart';

/// Screen displaying complete details of a doctor application for administrator review.
class DoctorApplicationDetailScreen extends StatefulWidget {
  final String doctorProfileId;

  const DoctorApplicationDetailScreen({
    super.key,
    required this.doctorProfileId,
  });

  @override
  State<DoctorApplicationDetailScreen> createState() =>
      _DoctorApplicationDetailScreenState();
}

class _DoctorApplicationDetailScreenState
    extends State<DoctorApplicationDetailScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadDetail();
    });
  }

  Future<void> _loadDetail() async {
    final adminProvider = context.read<AdminProvider>();
    await adminProvider.fetchApplicationDetail(widget.doctorProfileId);
  }

  Future<void> _handleApprove() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Approve Doctor?'),
        content: const Text(
          'Are you sure you want to approve this doctor application? '
          'This will activate the doctor account and make them verified.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.success,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Approve'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;
    if (!mounted) return;

    final adminProvider = context.read<AdminProvider>();
    final success = await adminProvider.approveDoctor(widget.doctorProfileId);

    if (!mounted) return;

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Doctor application approved successfully.'),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } else if (adminProvider.errorMessage != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(adminProvider.errorMessage!),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  Future<void> _handleReject() async {
    final reasonController = TextEditingController();
    final formKey = GlobalKey<FormState>();

    final confirmedReason = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reject Application'),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Please specify the reason for rejection. This reason will be shared with the applicant.',
                style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 16),
              TextFormField(
                key: const Key('reject_reason_input'),
                controller: reasonController,
                maxLines: 3,
                decoration: const InputDecoration(
                  hintText: 'e.g. SLMC registration certificate could not be verified.',
                  labelText: 'Reason for rejection *',
                ),
                validator: (val) {
                  if (val == null || val.trim().isEmpty) {
                    return 'A reason for rejection is required.';
                  }
                  if (val.trim().length < 3) {
                    return 'Reason must be at least 3 characters.';
                  }
                  return null;
                },
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(null),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            key: const Key('confirm_reject_button'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.error,
            ),
            onPressed: () {
              if (formKey.currentState!.validate()) {
                Navigator.of(ctx).pop(reasonController.text.trim());
              }
            },
            child: const Text('Reject Application'),
          ),
        ],
      ),
    );

    if (confirmedReason == null || confirmedReason.isEmpty) return;
    if (!mounted) return;

    final adminProvider = context.read<AdminProvider>();
    final success = await adminProvider.rejectDoctor(
      widget.doctorProfileId,
      confirmedReason,
    );

    if (!mounted) return;

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Doctor application rejected.'),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } else if (adminProvider.errorMessage != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(adminProvider.errorMessage!),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  void _openDocumentViewer(AdminDoctorDocumentMetadata doc) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DocumentViewerScreen(
          doctorProfileId: widget.doctorProfileId,
          document: doc,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final adminProvider = context.watch<AdminProvider>();
    final app = adminProvider.selectedApplication;
    final isLoading = adminProvider.isLoading;
    final isActionLoading = adminProvider.isActionLoading;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Application Details'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: isLoading || isActionLoading ? null : _loadDetail,
          ),
        ],
      ),
      body: SafeArea(
        child: isLoading
            ? const Center(child: CircularProgressIndicator())
            : app == null
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.error_outline, size: 48, color: AppTheme.textSecondary),
                        const SizedBox(height: 16),
                        Text(
                          adminProvider.errorMessage ?? 'Application not found.',
                          style: const TextStyle(color: AppTheme.textSecondary),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadDetail,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  )
                : SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // Status Card
                        _buildStatusHeader(app),
                        const SizedBox(height: 20),

                        // Section 1: Personal Information
                        _buildSectionCard(
                          title: 'Personal Information',
                          icon: Icons.person_rounded,
                          items: [
                            _buildInfoRow('Full Name', app.fullName),
                            _buildInfoRow('Email Address', app.email),
                            _buildInfoRow('Phone Number', app.phone ?? 'Not provided'),
                          ],
                        ),
                        const SizedBox(height: 16),

                        // Section 2: Professional Information
                        _buildSectionCard(
                          title: 'Professional Information',
                          icon: Icons.medical_services_rounded,
                          items: [
                            _buildInfoRow('Specialty', app.specialty),
                            _buildInfoRow('SLMC Registration No.', app.medicalRegistrationNumber),
                            _buildInfoRow('Qualifications', app.qualifications),
                            _buildInfoRow('Hospital / Clinic', app.hospitalOrClinic),
                            _buildInfoRow('Experience', '${app.experienceYears} Years'),
                            if (app.bio != null && app.bio!.trim().isNotEmpty)
                              _buildInfoRow('Bio', app.bio!),
                          ],
                        ),
                        const SizedBox(height: 16),

                        // Section 3: Verification Documents
                        _buildDocumentsCard(app),
                        const SizedBox(height: 28),

                        // Action Buttons (Only when PENDING)
                        if (app.isPending) ...[
                          Row(
                            children: [
                              Expanded(
                                child: ElevatedButton.icon(
                                  key: const Key('approve_doctor_button'),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppTheme.success,
                                    padding: const EdgeInsets.symmetric(vertical: 14),
                                  ),
                                  onPressed: isActionLoading ? null : _handleApprove,
                                  icon: isActionLoading
                                      ? const SizedBox(
                                          width: 18,
                                          height: 18,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                            valueColor:
                                                AlwaysStoppedAnimation<Color>(Colors.white),
                                          ),
                                        )
                                      : const Icon(Icons.check_circle_outline, size: 20),
                                  label: const Text('Approve Doctor'),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: OutlinedButton.icon(
                                  key: const Key('reject_doctor_button'),
                                  style: OutlinedButton.styleFrom(
                                    foregroundColor: AppTheme.error,
                                    side: const BorderSide(color: AppTheme.error),
                                    padding: const EdgeInsets.symmetric(vertical: 14),
                                  ),
                                  onPressed: isActionLoading ? null : _handleReject,
                                  icon: const Icon(Icons.cancel_outlined, size: 20),
                                  label: const Text('Reject Application'),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 24),
                        ],
                      ],
                    ),
                  ),
      ),
    );
  }

  Widget _buildStatusHeader(AdminDoctorApplicationDetail app) {
    Color badgeColor;
    Color textColor;
    IconData icon;

    if (app.isApproved) {
      badgeColor = Colors.green.shade50;
      textColor = Colors.green.shade800;
      icon = Icons.check_circle_rounded;
    } else if (app.isRejected) {
      badgeColor = AppTheme.errorContainer;
      textColor = AppTheme.error;
      icon = Icons.cancel_rounded;
    } else {
      badgeColor = Colors.amber.shade50;
      textColor = Colors.amber.shade900;
      icon = Icons.hourglass_top_rounded;
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 24,
                backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
                child: const Icon(Icons.person, color: AppTheme.primary, size: 28),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      app.fullName,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      app.specialty,
                      style: const TextStyle(
                        fontSize: 14,
                        color: AppTheme.primary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: badgeColor,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(icon, size: 14, color: textColor),
                    const SizedBox(width: 4),
                    Text(
                      app.verificationStatus,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: textColor,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (app.isRejected && app.rejectionReason != null) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.errorContainer.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppTheme.error.withValues(alpha: 0.2)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Rejection Reason:',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.error,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    app.rejectionReason!,
                    style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSectionCard({
    required String title,
    required IconData icon,
    required List<Widget> items,
  }) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 20, color: AppTheme.primary),
              const SizedBox(width: 8),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ...items,
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 3),
          Text(
            value,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w500,
              color: AppTheme.textPrimary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDocumentsCard(AdminDoctorApplicationDetail app) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.file_present_rounded, size: 20, color: AppTheme.primary),
              SizedBox(width: 8),
              Text(
                'Verification Documents',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (app.documents.isEmpty)
            const Text(
              'No verification documents attached.',
              style: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
            )
          else
            ...app.documents.map((doc) => _buildDocumentTile(doc)),
        ],
      ),
    );
  }

  Widget _buildDocumentTile(AdminDoctorDocumentMetadata doc) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.background,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        children: [
          Icon(
            doc.isPdf ? Icons.picture_as_pdf_rounded : Icons.image_rounded,
            color: doc.isPdf ? AppTheme.error : AppTheme.primary,
            size: 28,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  doc.title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  doc.filename,
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          OutlinedButton(
            key: Key('view_doc_${doc.documentKey}'),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              minimumSize: const Size(60, 36),
            ),
            onPressed: () => _openDocumentViewer(doc),
            child: const Text('View Document', style: TextStyle(fontSize: 12)),
          ),
        ],
      ),
    );
  }
}
