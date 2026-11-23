import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/appointment.dart';
import '../../models/consultation.dart';
import '../../services/consultation_service.dart';
import 'create_care_plan_screen.dart';

/// Screen allowing an assigned doctor to view full consultation details, start/complete the consultation,
/// and navigate to clinical records and follow-up plans (Phase 57).
class ConsultationDetailsScreen extends StatefulWidget {
  final String appointmentId;
  final ConsultationService? consultationService;

  const ConsultationDetailsScreen({
    super.key,
    required this.appointmentId,
    this.consultationService,
  });

  @override
  State<ConsultationDetailsScreen> createState() => _ConsultationDetailsScreenState();
}

class _ConsultationDetailsScreenState extends State<ConsultationDetailsScreen> {
  late final ConsultationService _consultationService;

  ConsultationDetail? _detail;
  bool _isLoading = true;
  String? _errorMessage;
  bool _isActionInProgress = false;

  @override
  void initState() {
    super.initState();
    _consultationService = widget.consultationService ?? ConsultationService();
    _loadDetails();
  }

  Future<void> _loadDetails() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final detail = await _consultationService.getConsultationDetails(widget.appointmentId);
      if (!mounted) return;
      setState(() {
        _detail = detail;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load consultation details.';
      });
    }
  }

  Future<void> _startConsultation() async {
    setState(() => _isActionInProgress = true);
    try {
      await _consultationService.startConsultation(widget.appointmentId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Consultation started.'),
          backgroundColor: AppTheme.success,
        ),
      );
      await _loadDetails();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Could not start consultation: ${e.toString().replaceAll("Exception:", "").trim()}'),
          backgroundColor: AppTheme.error,
        ),
      );
    } finally {
      if (mounted) setState(() => _isActionInProgress = false);
    }
  }

  Future<void> _completeConsultation() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Complete this consultation?', style: TextStyle(fontWeight: FontWeight.bold)),
        content: const Text('Are you sure you want to complete this consultation? This will record the completion timestamp and mark the appointment as finished.'),
        actions: [
          TextButton(
            key: const Key('details_complete_cancel_button'),
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            key: const Key('details_complete_confirm_button'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primary,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Complete Consultation'),
          ),
        ],
      ),
    );

    if (confirm != true || !mounted) return;

    setState(() => _isActionInProgress = true);
    try {
      await _consultationService.completeConsultation(widget.appointmentId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Consultation marked as completed.'),
          backgroundColor: AppTheme.success,
        ),
      );
      await _loadDetails();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Could not complete consultation: ${e.toString().replaceAll("Exception:", "").trim()}'),
          backgroundColor: AppTheme.error,
        ),
      );
    } finally {
      if (mounted) setState(() => _isActionInProgress = false);
    }
  }

  void _navigateToCreateFollowUpPlan() async {
    if (_detail == null) return;
    final item = _detail!.appointment;
    final appt = Appointment(
      id: item.appointmentId,
      patientUserId: item.patientUserId,
      doctorUserId: '',
      doctorProfileId: '',
      availabilityId: '',
      appointmentDate: item.appointmentDate,
      startTime: item.startTime,
      endTime: item.endTime,
      status: item.bookingStatus,
      patientName: item.patientName,
      patientEmail: item.patientEmail,
    );

    final res = await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => CreateCarePlanScreen(
          appointment: appt,
        ),
      ),
    );
    if (res == true) {
      _loadDetails();
    }
  }

  @override
  Widget build(BuildContext context) {
    const navy = Color(0xFF0D1B2A);

    return Scaffold(
      backgroundColor: const Color(0xFFF5F8FC),
      appBar: AppBar(
        title: const Text(
          'Consultation Details',
          style: TextStyle(fontWeight: FontWeight.bold, color: navy),
        ),
        backgroundColor: Colors.white,
        elevation: 0.5,
        iconTheme: const IconThemeData(color: navy),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _loadDetails,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline_rounded, color: AppTheme.error, size: 48),
                      const SizedBox(height: 12),
                      Text(_errorMessage!, style: const TextStyle(fontSize: 15)),
                      const SizedBox(height: 16),
                      ElevatedButton(onPressed: _loadDetails, child: const Text('Retry')),
                    ],
                  ),
                )
              : _detail == null
                  ? const Center(child: Text('No details found.'))
                  : SingleChildScrollView(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          // Status Header Card
                          _buildStatusHeaderCard(),
                          const SizedBox(height: 16),

                          // Patient Information Card
                          _buildPatientCard(),
                          const SizedBox(height: 16),

                          // Timing & Clinical Execution Card
                          _buildTimingCard(),
                          const SizedBox(height: 16),

                          // Clinical Linkages (Care Plan, Rx, Medical Record)
                          _buildClinicalLinkagesCard(),
                          const SizedBox(height: 24),

                          // Action Buttons
                          _buildActionButtons(),
                          const SizedBox(height: 20),
                        ],
                      ),
                    ),
    );
  }

  Widget _buildStatusHeaderCard() {
    final item = _detail!.appointment;
    final statusColor = item.isInProgress
        ? Colors.green.shade700
        : item.isCompleted
            ? Colors.deepPurple
            : const Color(0xFF1565C0);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Consultation Status', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
              const SizedBox(height: 4),
              Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(color: statusColor, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    item.consultationStatus.replaceAll('_', ' '),
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: statusColor),
                  ),
                ],
              ),
            ],
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: AppTheme.surfaceVariant.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              'Booking: ${item.bookingStatus}',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF0D1B2A)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPatientCard() {
    final item = _detail!.appointment;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Patient Information', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Color(0xFF0D1B2A))),
          const Divider(height: 20),
          Row(
            children: [
              CircleAvatar(
                radius: 22,
                backgroundColor: const Color(0xFF1565C0).withValues(alpha: 0.1),
                child: const Icon(Icons.person, color: Color(0xFF1565C0), size: 24),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(item.patientName, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                    if (item.patientEmail != null && item.patientEmail!.isNotEmpty)
                      Text(item.patientEmail!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    if (item.patientPhone != null && item.patientPhone!.isNotEmpty)
                      Text(item.patientPhone!, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ],
                ),
              ),
            ],
          ),
          if (item.patientNote != null && item.patientNote!.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F8FC),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.outline.withValues(alpha: 0.15)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Reason for Visit / Patient Note:', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.textSecondary)),
                  const SizedBox(height: 3),
                  Text(item.patientNote!, style: const TextStyle(fontSize: 13, color: Color(0xFF0D1B2A))),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTimingCard() {
    final item = _detail!.appointment;
    final session = _detail!.session;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Consultation Schedule & Execution', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Color(0xFF0D1B2A))),
          const Divider(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Scheduled Time', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
              Text('${item.appointmentDate} (${item.startTime} - ${item.endTime})', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            ],
          ),
          if (session?.startedAt != null) ...[
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Started At', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                Text(session!.startedAt!.toLocal().toString().substring(0, 16), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.green)),
              ],
            ),
          ],
          if (session?.completedAt != null) ...[
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Completed At', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                Text(session!.completedAt!.toLocal().toString().substring(0, 16), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.deepPurple)),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildClinicalLinkagesCard() {
    final cp = _detail!.carePlan;
    final rx = _detail!.prescription;
    final mr = _detail!.medicalRecord;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Clinical Linkages', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Color(0xFF0D1B2A))),
          const Divider(height: 20),
          // Follow-up Care Plan linkage
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(color: Colors.purple.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(8)),
              child: const Icon(Icons.assignment_turned_in_rounded, color: Colors.purple, size: 20),
            ),
            title: const Text('Follow-up Care Plan', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            subtitle: Text(
              cp != null ? 'Status: ${cp['status']} (Due: ${cp['followUpDate']})' : 'No follow-up plan created yet',
              style: const TextStyle(fontSize: 12),
            ),
            trailing: cp == null && _detail!.appointment.isCompleted
                ? TextButton(
                    onPressed: _navigateToCreateFollowUpPlan,
                    child: const Text('Create'),
                  )
                : null,
          ),
          const Divider(height: 12),
          // Digital Prescription linkage
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(color: Colors.teal.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(8)),
              child: const Icon(Icons.medication_rounded, color: Colors.teal, size: 20),
            ),
            title: const Text('Digital Prescription', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            subtitle: Text(
              rx != null ? 'ID: ${rx['prescriptionId']}' : 'No prescription recorded for this visit',
              style: const TextStyle(fontSize: 12),
            ),
          ),
          const Divider(height: 12),
          // Consultation Medical Record linkage
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(color: Colors.indigo.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(8)),
              child: const Icon(Icons.description_rounded, color: Colors.indigo, size: 20),
            ),
            title: const Text('Clinical Consultation Record', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            subtitle: Text(
              mr != null ? 'Record: ${mr['recordId']}' : 'No formal clinical notes documented',
              style: const TextStyle(fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButtons() {
    final item = _detail!.appointment;

    if (item.isCancelled) {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.error.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
        ),
        child: const Center(
          child: Text(
            'This appointment was cancelled. Consultations cannot be initiated.',
            style: TextStyle(color: AppTheme.error, fontWeight: FontWeight.bold, fontSize: 13),
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    if (item.isNotStarted) {
      return SizedBox(
        width: double.infinity,
        child: ElevatedButton.icon(
          key: const Key('details_start_consultation_button'),
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF1565C0),
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
          onPressed: _isActionInProgress ? null : _startConsultation,
          icon: _isActionInProgress
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
              : const Icon(Icons.play_arrow_rounded),
          label: const Text('Start Consultation', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
        ),
      );
    }

    if (item.isInProgress) {
      return SizedBox(
        width: double.infinity,
        child: ElevatedButton.icon(
          key: const Key('details_complete_consultation_button'),
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.green.shade700,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
          onPressed: _isActionInProgress ? null : _completeConsultation,
          icon: _isActionInProgress
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
              : const Icon(Icons.check_circle_rounded),
          label: const Text('Complete Consultation', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
        ),
      );
    }

    // COMPLETED
    return Column(
      children: [
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            key: const Key('details_create_followup_plan_button'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.deepPurple,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            icon: const Icon(Icons.assignment_add),
            label: const Text('Create Follow-up Plan', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
            onPressed: _navigateToCreateFollowUpPlan,
          ),
        ),
        const SizedBox(height: 10),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton(
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFF1565C0),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text("Return to Today's Schedule"),
          ),
        ),
      ],
    );
  }
}
