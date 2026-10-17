import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/prescription.dart';
import '../../services/medical_record_service.dart';

/// Screen allowing doctors to document clinical notes, assessment, treatment plan, and structured Rx.
class CreateConsultationRecordScreen extends StatefulWidget {
  final Map<String, dynamic> appointment;
  final MedicalRecordService? service;

  const CreateConsultationRecordScreen({
    super.key,
    required this.appointment,
    this.service,
  });

  @override
  State<CreateConsultationRecordScreen> createState() => _CreateConsultationRecordScreenState();
}

class _MedicationItemEntry {
  final TextEditingController nameController = TextEditingController();
  final TextEditingController strengthController = TextEditingController();
  final TextEditingController doseController = TextEditingController(text: '1 tablet');
  final TextEditingController frequencyController = TextEditingController(text: 'Twice daily (BD)');
  final TextEditingController durationController = TextEditingController(text: '5 days');
  final TextEditingController quantityController = TextEditingController(text: '10 tablets');
  final TextEditingController instructionsController = TextEditingController(text: 'Take after meals');
  String route = 'Oral';

  void dispose() {
    nameController.dispose();
    strengthController.dispose();
    doseController.dispose();
    frequencyController.dispose();
    durationController.dispose();
    quantityController.dispose();
    instructionsController.dispose();
  }
}

class _CreateConsultationRecordScreenState extends State<CreateConsultationRecordScreen> {
  late final MedicalRecordService _service;
  final _formKey = GlobalKey<FormState>();

  final _clinicalNotesController = TextEditingController();
  final _assessmentController = TextEditingController();
  final _treatmentPlanController = TextEditingController();
  final _followUpController = TextEditingController();
  final _prescInstructionsController = TextEditingController();

  bool _includePrescription = true;
  final List<_MedicationItemEntry> _medications = [];
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? MedicalRecordService();
    // Default starter medication item
    _addMedication();
  }

  @override
  void dispose() {
    _clinicalNotesController.dispose();
    _assessmentController.dispose();
    _treatmentPlanController.dispose();
    _followUpController.dispose();
    _prescInstructionsController.dispose();
    for (final med in _medications) {
      med.dispose();
    }
    super.dispose();
  }

  void _addMedication() {
    setState(() {
      _medications.add(_MedicationItemEntry());
    });
  }

  void _removeMedication(int index) {
    if (_medications.length <= 1) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('At least one medication is required when issuing a prescription.')),
      );
      return;
    }
    setState(() {
      final removed = _medications.removeAt(index);
      removed.dispose();
    });
  }

  Future<void> _handleSubmit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    if (_includePrescription) {
      for (int i = 0; i < _medications.length; i++) {
        final med = _medications[i];
        if (med.nameController.text.trim().isEmpty || med.strengthController.text.trim().isEmpty) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Please fill in medication name and strength for item #${i + 1}.')),
          );
          return;
        }
      }
    }

    // Confirmation dialog before final issuance
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirm Record & Prescription'),
        content: Text(
          'Are you sure you want to officially issue this clinical consultation record'
          '${_includePrescription ? " and digital prescription (${_medications.length} items)" : ""}?'
          '\n\nThis will be permanently attached to the patient\'s health record and is tamper-evident.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primary),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Confirm & Issue'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() => _isSubmitting = true);

    try {
      final apptId = widget.appointment['id']?.toString() ?? widget.appointment['_id']?.toString() ?? '';

      // 1. Create Consultation Medical Record
      final record = await _service.createMedicalRecord(
        appointmentId: apptId,
        clinicalNotes: _clinicalNotesController.text,
        assessment: _assessmentController.text,
        treatmentPlan: _treatmentPlanController.text,
        followUpInstructions: _followUpController.text,
      );

      // 2. Issue Digital Prescription if checked
      if (_includePrescription) {
        final medItems = _medications.map((m) {
          return MedicationItem(
            medicationName: m.nameController.text.trim(),
            strength: m.strengthController.text.trim(),
            dose: m.doseController.text.trim(),
            route: m.route,
            frequency: m.frequencyController.text.trim(),
            duration: m.durationController.text.trim(),
            quantity: m.quantityController.text.trim(),
            additionalInstructions: m.instructionsController.text.trim(),
          );
        }).toList();

        await _service.createPrescription(
          medicalRecordId: record.id,
          appointmentId: apptId,
          medicationItems: medItems,
          instructions: _prescInstructionsController.text,
        );
      }

      if (!mounted) return;

      setState(() => _isSubmitting = false);

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Consultation documented and prescription issued successfully.'),
          backgroundColor: AppTheme.success,
        ),
      );

      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSubmitting = false);

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to save record: $e'),
          backgroundColor: AppTheme.error,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final patientName = widget.appointment['patientName'] ?? widget.appointment['patient']?['fullName'] ?? 'Patient';
    final apptDate = widget.appointment['appointmentDate'] ?? 'Today';
    final timeSlot = '${widget.appointment['startTime'] ?? ""} - ${widget.appointment['endTime'] ?? ""}';

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Document Consultation'),
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.all(16.0),
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              offset: const Offset(0, -2),
              blurRadius: 10,
            ),
          ],
        ),
        child: ElevatedButton(
          key: const Key('create_consultation_submit_button'),
          onPressed: _isSubmitting ? null : _handleSubmit,
          style: ElevatedButton.styleFrom(
            backgroundColor: AppTheme.primary,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
          child: _isSubmitting
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                )
              : const Text(
                  'Issue Consultation & Prescription',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
        ),
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16.0),
          children: [
            // Patient Header Card
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              color: const Color(0xFFF0FDFA),
              child: Padding(
                padding: const EdgeInsets.all(14.0),
                child: Row(
                  children: [
                    const CircleAvatar(
                      backgroundColor: AppTheme.primary,
                      child: Icon(Icons.person_rounded, color: Colors.white),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '$patientName',
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          Text(
                            'Date: $apptDate • Slot: $timeSlot',
                            style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),

            // Clinical Notes
            _buildTextFormField(
              key: const Key('consultation_clinical_notes_field'),
              controller: _clinicalNotesController,
              label: 'Clinical Observations & Symptoms *',
              hint: 'Describe presenting symptoms, physical findings, vital signs...',
              maxLines: 4,
              validator: (v) => v == null || v.trim().isEmpty ? 'Clinical notes are required.' : null,
            ),

            const SizedBox(height: 14),

            // Assessment
            _buildTextFormField(
              key: const Key('consultation_assessment_field'),
              controller: _assessmentController,
              label: 'Clinical Assessment & Impression *',
              hint: 'Provisional diagnosis, clinical impression...',
              maxLines: 2,
              validator: (v) => v == null || v.trim().isEmpty ? 'Assessment is required.' : null,
            ),

            const SizedBox(height: 14),

            // Treatment Plan
            _buildTextFormField(
              key: const Key('consultation_treatment_plan_field'),
              controller: _treatmentPlanController,
              label: 'Treatment & Care Plan *',
              hint: 'Management strategy, non-pharmacological care, lifestyle advice...',
              maxLines: 3,
              validator: (v) => v == null || v.trim().isEmpty ? 'Treatment plan is required.' : null,
            ),

            const SizedBox(height: 14),

            // Follow-up
            _buildTextFormField(
              key: const Key('consultation_follow_up_field'),
              controller: _followUpController,
              label: 'Follow-Up Instructions (Optional)',
              hint: 'Review in 2 weeks, return if symptoms worsen...',
              maxLines: 2,
            ),

            const SizedBox(height: 20),

            // Digital Prescription Toggle
            Card(
              elevation: 1,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              child: SwitchListTile(
                title: const Text(
                  'Issue Structured Digital Prescription (Rx)',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
                subtitle: const Text('Add verified medications to accompany this consultation record.'),
                value: _includePrescription,
                activeThumbColor: AppTheme.primary,
                onChanged: (val) {
                  setState(() => _includePrescription = val);
                },
              ),
            ),

            if (_includePrescription) ...[
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Prescribed Medications',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                  ),
                  TextButton.icon(
                    key: const Key('consultation_add_medication_button'),
                    onPressed: _addMedication,
                    icon: const Icon(Icons.add_circle_outline, size: 18),
                    label: const Text('Add Medicine'),
                  ),
                ],
              ),
              const SizedBox(height: 8),

              ..._medications.asMap().entries.map((entry) {
                final idx = entry.key;
                final med = entry.value;
                return _buildMedicationEntryCard(idx, med);
              }),

              const SizedBox(height: 12),
              _buildTextFormField(
                controller: _prescInstructionsController,
                label: 'General Prescription Advice (Optional)',
                hint: 'General precautions, dietary considerations during medication...',
                maxLines: 2,
              ),
            ],

            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _buildTextFormField({
    Key? key,
    required TextEditingController controller,
    required String label,
    required String hint,
    int maxLines = 1,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      key: key,
      controller: controller,
      maxLines: maxLines,
      validator: validator,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        alignLabelWithHint: maxLines > 1,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        filled: true,
        fillColor: Colors.white,
      ),
    );
  }

  Widget _buildMedicationEntryCard(int index, _MedicationItemEntry med) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(14.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Medication #${index + 1}',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: AppTheme.primary),
                ),
                if (_medications.length > 1)
                  IconButton(
                    icon: const Icon(Icons.delete_outline_rounded, color: AppTheme.error, size: 20),
                    onPressed: () => _removeMedication(index),
                    tooltip: 'Remove',
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  flex: 3,
                  child: TextFormField(
                    key: Key('med_name_$index'),
                    controller: med.nameController,
                    decoration: InputDecoration(
                      labelText: 'Drug Name *',
                      hintText: 'e.g. Paracetamol',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      isDense: true,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  flex: 2,
                  child: TextFormField(
                    key: Key('med_strength_$index'),
                    controller: med.strengthController,
                    decoration: InputDecoration(
                      labelText: 'Strength *',
                      hintText: 'e.g. 500mg',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      isDense: true,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: med.doseController,
                    decoration: InputDecoration(
                      labelText: 'Dose',
                      hintText: '1 tablet',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      isDense: true,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: DropdownButtonFormField<String>(
                    initialValue: med.route,
                    items: const [
                      DropdownMenuItem(value: 'Oral', child: Text('Oral')),
                      DropdownMenuItem(value: 'Topical', child: Text('Topical')),
                      DropdownMenuItem(value: 'Inhalation', child: Text('Inhalation')),
                      DropdownMenuItem(value: 'Intravenous', child: Text('Intravenous')),
                    ],
                    onChanged: (val) {
                      if (val != null) setState(() => med.route = val);
                    },
                    decoration: InputDecoration(
                      labelText: 'Route',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      isDense: true,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: med.frequencyController,
                    decoration: InputDecoration(
                      labelText: 'Frequency',
                      hintText: 'Twice daily',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      isDense: true,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextFormField(
                    controller: med.durationController,
                    decoration: InputDecoration(
                      labelText: 'Duration',
                      hintText: '5 days',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      isDense: true,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            TextFormField(
              controller: med.instructionsController,
              decoration: InputDecoration(
                labelText: 'Instructions',
                hintText: 'Take after meals with water',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                isDense: true,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
