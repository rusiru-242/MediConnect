import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/medical_record.dart';
import '../../services/medical_record_service.dart';
import 'prescription_detail_screen.dart';

/// Screen displaying complete consultation clinical notes, assessment, treatment plan, and attached Rx.
class MedicalRecordDetailScreen extends StatefulWidget {
  final String recordId;
  final MedicalRecord? initialRecord;
  final MedicalRecordService? service;

  const MedicalRecordDetailScreen({
    super.key,
    required this.recordId,
    this.initialRecord,
    this.service,
  });

  @override
  State<MedicalRecordDetailScreen> createState() => _MedicalRecordDetailScreenState();
}

class _MedicalRecordDetailScreenState extends State<MedicalRecordDetailScreen> {
  late final MedicalRecordService _service;
  MedicalRecord? _record;
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? MedicalRecordService();
    _record = widget.initialRecord;
    if (_record == null) {
      _loadRecord();
    }
  }

  Future<void> _loadRecord() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final rec = await _service.getMedicalRecordDetail(widget.recordId);
      if (mounted) {
        setState(() {
          _record = rec;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Could not load medical consultation record. Please try again.';
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Consultation Record'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: _loadRecord,
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 56, color: AppTheme.error),
              const SizedBox(height: 16),
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 15, color: AppTheme.textPrimary),
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: _loadRecord,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_record == null) {
      return const Center(child: Text('Record not found.'));
    }

    final rec = _record!;

    return ListView(
      padding: const EdgeInsets.all(16.0),
      children: [
        // 1. Doctor & Consultation Header Card
        Card(
          elevation: 2,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    CircleAvatar(
                      radius: 28,
                      backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
                      child: const Icon(Icons.medical_services_rounded, color: AppTheme.primary, size: 28),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            rec.doctorName ?? 'Verified Doctor',
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            rec.doctorSpecialty ?? 'General Physician',
                            style: const TextStyle(
                              fontSize: 14,
                              color: AppTheme.primary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          if (rec.slmcRegistrationNumber != null) ...[
                            const SizedBox(height: 2),
                            Text(
                              'SLMC: ${rec.slmcRegistrationNumber}',
                              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                            ),
                          ],
                          if (rec.hospitalOrClinic != null) ...[
                            const SizedBox(height: 2),
                            Text(
                              rec.hospitalOrClinic!,
                              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                            ),
                          ],
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: rec.status == 'AMENDED'
                            ? Colors.orange.withValues(alpha: 0.15)
                            : AppTheme.success.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        rec.status,
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: rec.status == 'AMENDED' ? Colors.orange[800] : AppTheme.success,
                        ),
                      ),
                    ),
                  ],
                ),
                const Divider(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildMetaItem('CONSULTATION DATE', rec.consultationDate),
                    _buildMetaItem('RECORD REF', rec.recordId),
                  ],
                ),
              ],
            ),
          ),
        ),

        const SizedBox(height: 16),

        // 2. Clinical Notes Section
        _buildSectionCard(
          icon: Icons.notes_rounded,
          iconColor: Colors.blueAccent,
          title: 'Clinical Observations & Symptoms',
          content: rec.clinicalNotes,
        ),

        const SizedBox(height: 12),

        // 3. Assessment Section
        _buildSectionCard(
          icon: Icons.assignment_turned_in_rounded,
          iconColor: AppTheme.primary,
          title: 'Clinical Assessment & Impression',
          content: rec.assessment,
        ),

        const SizedBox(height: 12),

        // 4. Treatment Plan Section
        _buildSectionCard(
          icon: Icons.healing_rounded,
          iconColor: Colors.teal,
          title: 'Treatment & Management Plan',
          content: rec.treatmentPlan,
        ),

        if (rec.followUpInstructions != null && rec.followUpInstructions!.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildSectionCard(
            icon: Icons.event_repeat_rounded,
            iconColor: Colors.deepPurple,
            title: 'Follow-Up Instructions',
            content: rec.followUpInstructions!,
          ),
        ],

        // 5. Attached Digital Prescription Card (if present)
        if (rec.prescription != null) ...[
          const SizedBox(height: 16),
          Card(
            elevation: 2,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            color: const Color(0xFFF0FDFA),
            child: InkWell(
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (ctx) => PrescriptionDetailScreen(
                      prescriptionId: rec.prescription!.id,
                      initialPrescription: rec.prescription,
                    ),
                  ),
                );
              },
              borderRadius: BorderRadius.circular(16),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppTheme.primary.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(Icons.receipt_long_rounded, color: AppTheme.primary, size: 28),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Digital Prescription Attached',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.primary,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'Ref: ${rec.prescription!.prescriptionId} • ${rec.prescription!.medicationItems.length} Medications',
                            style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                          ),
                        ],
                      ),
                    ),
                    const Icon(Icons.chevron_right_rounded, color: AppTheme.primary),
                  ],
                ),
              ),
            ),
          ),
        ],

        const SizedBox(height: 24),

        // Disclaimer
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.amber.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.amber.withValues(alpha: 0.4)),
          ),
          child: const Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.lock_outline_rounded, color: Colors.amber, size: 20),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'CONFIDENTIAL MEDICAL RECORD: This record was documented by a verified physician and is stored with end-to-end access controls.',
                  style: TextStyle(fontSize: 12, color: Colors.black87),
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 24),
      ],
    );
  }

  Widget _buildMetaItem(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.textSecondary),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
        ),
      ],
    );
  }

  Widget _buildSectionCard({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String content,
  }) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 20, color: iconColor),
                const SizedBox(width: 8),
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              content,
              style: const TextStyle(
                fontSize: 14,
                color: AppTheme.textPrimary,
                height: 1.45,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
