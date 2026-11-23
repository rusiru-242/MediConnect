import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/timeline.dart';
import '../../services/patient_timeline_service.dart';
import 'medical_record_detail_screen.dart';
import 'patient_care_plans_screen.dart';
import 'prescription_detail_screen.dart';

/// Consolidated visit overview for a patient consultation/appointment (Phase 58).
class PatientVisitDetailScreen extends StatefulWidget {
  final String appointmentId;
  final PatientTimelineService? timelineService;

  const PatientVisitDetailScreen({
    super.key,
    required this.appointmentId,
    this.timelineService,
  });

  @override
  State<PatientVisitDetailScreen> createState() => _PatientVisitDetailScreenState();
}

class _PatientVisitDetailScreenState extends State<PatientVisitDetailScreen> {
  late final PatientTimelineService _timelineService;

  VisitDetail? _detail;
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _timelineService = widget.timelineService ?? PatientTimelineService();
    _loadVisitDetail();
  }

  Future<void> _loadVisitDetail() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final detail = await _timelineService.getVisitDetail(widget.appointmentId);
      if (!mounted) return;
      setState(() {
        _detail = detail;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = e.toString().replaceAll("Exception:", "").trim();
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    const navy = Color(0xFF0D1B2A);

    return Scaffold(
      backgroundColor: const Color(0xFFF5F8FC),
      appBar: AppBar(
        title: const Text(
          'Visit Details',
          style: TextStyle(fontWeight: FontWeight.bold, color: navy),
        ),
        backgroundColor: Colors.white,
        elevation: 0.5,
        iconTheme: const IconThemeData(color: navy),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: _loadVisitDetail,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24.0),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.error_outline_rounded, color: AppTheme.error, size: 48),
                        const SizedBox(height: 12),
                        Text(
                          _errorMessage!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontSize: 15, color: navy),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton.icon(
                          onPressed: _loadVisitDetail,
                          icon: const Icon(Icons.refresh_rounded),
                          label: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : _detail == null
                  ? const Center(child: Text('Visit information not found.'))
                  : RefreshIndicator(
                      onRefresh: _loadVisitDetail,
                      child: ListView(
                        padding: const EdgeInsets.all(16),
                        children: [
                          _buildDoctorAndStatusCard(),
                          const SizedBox(height: 14),
                          if (_detail!.bookingStatus == 'CANCELLED') ...[
                            _buildCancellationBanner(),
                            const SizedBox(height: 14),
                          ],
                          _buildConsultationSessionCard(),
                          const SizedBox(height: 14),
                          _buildClinicalArtifactsCard(),
                          if (_detail!.timelineEvents.isNotEmpty) ...[
                            const SizedBox(height: 14),
                            _buildVisitTimelineCard(),
                          ],
                          const SizedBox(height: 24),
                        ],
                      ),
                    ),
    );
  }

  Widget _buildDoctorAndStatusCard() {
    const navy = Color(0xFF0D1B2A);
    final isCompleted = _detail!.bookingStatus == 'COMPLETED' || _detail!.consultationStatus == 'COMPLETED';

    Color statusColor;
    if (_detail!.bookingStatus == 'CANCELLED') {
      statusColor = Colors.red.shade700;
    } else if (isCompleted) {
      statusColor = Colors.green.shade700;
    } else {
      statusColor = const Color(0xFF1565C0);
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 26,
                backgroundColor: const Color(0xFF1565C0).withValues(alpha: 0.1),
                child: const Icon(Icons.person, color: Color(0xFF1565C0), size: 28),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _detail!.doctorName,
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 17, color: navy),
                    ),
                    if (_detail!.doctorSpecialty != null && _detail!.doctorSpecialty!.isNotEmpty)
                      Text(
                        _detail!.doctorSpecialty!,
                        style: const TextStyle(color: Color(0xFF1565C0), fontWeight: FontWeight.w600, fontSize: 13),
                      ),
                    if (_detail!.doctorHospital != null && _detail!.doctorHospital!.isNotEmpty)
                      Text(
                        _detail!.doctorHospital!,
                        style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
                      ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: statusColor.withValues(alpha: 0.3)),
                ),
                child: Text(
                  _detail!.bookingStatus,
                  style: TextStyle(color: statusColor, fontWeight: FontWeight.bold, fontSize: 11),
                ),
              ),
            ],
          ),
          const Divider(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildInfoColumn('Appointment Date', _detail!.appointmentDate),
              _buildInfoColumn('Time Slot', '${_detail!.startTime} - ${_detail!.endTime}'),
              _buildInfoColumn('Consultation Fee', 'LKR ${_detail!.consultationFee.toInt()}'),
            ],
          ),
          if (_detail!.patientNote != null && _detail!.patientNote!.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F8FC),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                'Note: ${_detail!.patientNote}',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildInfoColumn(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
        const SizedBox(height: 2),
        Text(value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Color(0xFF0D1B2A))),
      ],
    );
  }

  Widget _buildCancellationBanner() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.red.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.red.shade200),
      ),
      child: Row(
        children: [
          Icon(Icons.cancel_outlined, color: Colors.red.shade700, size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              _detail!.cancellationReason != null && _detail!.cancellationReason!.isNotEmpty
                  ? 'Cancelled (${_detail!.cancelledBy ?? "Patient"}): ${_detail!.cancellationReason}'
                  : 'This appointment was cancelled.',
              style: TextStyle(color: Colors.red.shade900, fontSize: 13, fontWeight: FontWeight.w500),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConsultationSessionCard() {
    const navy = Color(0xFF0D1B2A);
    final sess = _detail!.consultationSession;
    final isCompleted = _detail!.consultationStatus == 'COMPLETED';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: const [
                  Icon(Icons.medical_services_rounded, color: Color(0xFF1565C0), size: 18),
                  SizedBox(width: 8),
                  Text('Consultation Status', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: navy)),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: (isCompleted ? Colors.green : const Color(0xFF1565C0)).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  _detail!.consultationStatus,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: isCompleted ? Colors.green.shade800 : const Color(0xFF1565C0),
                  ),
                ),
              ),
            ],
          ),
          if (sess != null && (sess['startedAt'] != null || sess['completedAt'] != null)) ...[
            const SizedBox(height: 12),
            if (sess['startedAt'] != null)
              _buildTimestampRow('Consultation Commenced', sess['startedAt'].toString().substring(0, 16).replaceFirst('T', ' ')),
            if (sess['completedAt'] != null) ...[
              const SizedBox(height: 6),
              _buildTimestampRow('Consultation Concluded', sess['completedAt'].toString().substring(0, 16).replaceFirst('T', ' ')),
            ],
          ],
        ],
      ),
    );
  }

  Widget _buildTimestampRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF0D1B2A))),
      ],
    );
  }

  Widget _buildClinicalArtifactsCard() {
    const navy = Color(0xFF0D1B2A);
    final rx = _detail!.prescription;
    final mr = _detail!.medicalRecord;
    final cp = _detail!.carePlan;

    final hasAny = rx != null || mr != null || cp != null;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Clinical Documents & Follow-ups', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: navy)),
          const Divider(height: 20),
          if (!hasAny)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8.0),
              child: Text(
                'No prescriptions, medical consultation records, or care plans linked to this visit yet.',
                style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
              ),
            ),
          if (rx != null) ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(color: Colors.teal.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(8)),
                child: const Icon(Icons.receipt_long_rounded, color: Colors.teal, size: 22),
              ),
              title: Text('Digital Prescription (${rx['prescriptionId'] ?? "Prescription"})', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
              subtitle: Text('${rx['medicationsCount'] ?? 0} medication(s) prescribed', style: const TextStyle(fontSize: 12)),
              trailing: ElevatedButton(
                key: const Key('visit_detail_view_prescription_button'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.teal,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => PrescriptionDetailScreen(prescriptionId: rx['id'] ?? ''),
                    ),
                  );
                },
                child: const Text('View', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
              ),
            ),
            if (mr != null || cp != null) const Divider(height: 16),
          ],
          if (mr != null) ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(color: Colors.indigo.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(8)),
                child: const Icon(Icons.description_outlined, color: Colors.indigo, size: 22),
              ),
              title: Text('Medical Record (${mr['recordId'] ?? "Record"})', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
              subtitle: Text(mr['assessment'] != null ? 'Assessment: ${mr['assessment']}' : 'Consultation documentation', style: const TextStyle(fontSize: 12), maxLines: 2, overflow: TextOverflow.ellipsis),
              trailing: ElevatedButton(
                key: const Key('visit_detail_view_record_button'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.indigo,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => MedicalRecordDetailScreen(recordId: mr['id'] ?? ''),
                    ),
                  );
                },
                child: const Text('View', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
              ),
            ),
            if (cp != null) const Divider(height: 16),
          ],
          if (cp != null) ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(color: Colors.purple.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(8)),
                child: const Icon(Icons.assignment_turned_in_rounded, color: Colors.purple, size: 22),
              ),
              title: const Text('Follow-up Care Plan', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
              subtitle: Text('Due: ${cp['followUpDate']} (${cp['status']})', style: const TextStyle(fontSize: 12)),
              trailing: ElevatedButton(
                key: const Key('visit_detail_view_care_plan_button'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.purple,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => const PatientCarePlansScreen(),
                    ),
                  );
                },
                child: const Text('View', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildVisitTimelineCard() {
    const navy = Color(0xFF0D1B2A);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Icon(Icons.timeline_rounded, color: Color(0xFF1565C0), size: 18),
              SizedBox(width: 8),
              Text('Visit Milestones', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: navy)),
            ],
          ),
          const SizedBox(height: 12),
          ..._detail!.timelineEvents.map((e) => Padding(
                padding: const EdgeInsets.only(bottom: 8.0),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      margin: const EdgeInsets.only(top: 4),
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        color: Color(0xFF1565C0),
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(e.title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: navy)),
                          Text(e.description, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                          Text(e.displayDate + (e.displayTime != null ? ' ${e.displayTime}' : ''),
                              style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
                        ],
                      ),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }
}

