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

/// A04-BUG-009: every field starts empty. The dose, frequency, duration, quantity and instructions used to be
/// pre-filled ("1 tablet", "Twice daily (BD)", "5 days", "10 tablets", "Take after meals"), and quantity had no field
/// at all, so a prescription could be issued with dosing the doctor never entered. Examples are hints only.
class _MedicationItemEntry {
  final TextEditingController nameController = TextEditingController();
  final TextEditingController strengthController = TextEditingController();
  final TextEditingController doseController = TextEditingController();
  final TextEditingController frequencyController = TextEditingController();
  final TextEditingController durationController = TextEditingController();
  final TextEditingController quantityController = TextEditingController();
  final TextEditingController instructionsController = TextEditingController();
  String route = 'Oral';

  /// Required fields left empty, in the order shown on the form.
  List<String> missing() => [
        if (nameController.text.trim().isEmpty) 'drug name',
        if (strengthController.text.trim().isEmpty) 'strength',
        if (doseController.text.trim().isEmpty) 'dose',
        if (frequencyController.text.trim().isEmpty) 'frequency',
        if (durationController.text.trim().isEmpty) 'duration',
        if (quantityController.text.trim().isEmpty) 'quantity',
      ];

  MedicationItem toItem() => MedicationItem(
        medicationName: nameController.text.trim(),
        strength: strengthController.text.trim(),
        dose: doseController.text.trim(),
        route: route,
        frequency: frequencyController.text.trim(),
        duration: durationController.text.trim(),
        quantity: quantityController.text.trim(),
        additionalInstructions:
            instructionsController.text.trim().isEmpty ? null : instructionsController.text.trim(),
      );

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

  /// A04-BUG-010: the consultation record saved by an earlier attempt. If the prescription then failed, a retry used
  /// to create the record again ("already exists") and the visit could never receive its prescription here.
  String? _savedRecordId;

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
        final missing = _medications[i].missing();
        if (missing.isNotEmpty) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              key: const Key('rx_missing_fields_message'),
              content: Text('Medication #${i + 1}: enter the ${missing.join(', ')}. Nothing is filled in for you.'),
            ),
          );
          return;
        }
      }
    }

    final items = _includePrescription ? _medications.map((m) => m.toItem()).toList() : <MedicationItem>[];
    // Structural check of exactly what was typed (missing fields, repeats, allergies, active prescriptions).
    // It never changes the items and never signs; if it cannot run, the dialog says so.
    Map<String, dynamic>? review;
    String? reviewError;
    final patientId = (widget.appointment['patientUserId'] ?? widget.appointment['patientId'])?.toString();
    if (_includePrescription && patientId != null && patientId.isNotEmpty) {
      try {
        review = await _service.reviewPrescriptionDraft(patientUserId: patientId, medicationItems: items);
      } catch (_) {
        reviewError = 'The allergy and active-medication check could not run. Review the patient record yourself.';
      }
    } else if (_includePrescription) {
      reviewError = 'The allergy and active-medication check could not run for this visit.';
    }
    if (!mounted) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        key: const Key('rx_review_dialog'),
        title: Text(_savedRecordId == null ? 'Confirm Record & Prescription' : 'Confirm Prescription'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _savedRecordId == null
                    ? 'Issue this clinical consultation record'
                        '${_includePrescription ? " and digital prescription (${items.length} items)" : ""}?'
                    : 'The consultation record is already saved. Issue the prescription (${items.length} items)?',
              ),
              if (_includePrescription) ...[
                const SizedBox(height: 10),
                const Text('Review what you entered:', style: TextStyle(fontWeight: FontWeight.bold)),
                for (var i = 0; i < items.length; i++)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      '${i + 1}. ${items[i].medicationName} ${items[i].strength} — ${items[i].dose}, ${items[i].route}, '
                      '${items[i].frequency}, ${items[i].duration}, quantity ${items[i].quantity}'
                      '${items[i].additionalInstructions != null ? '. ${items[i].additionalInstructions}' : ''}',
                      key: Key('rx_review_item_$i'),
                    ),
                  ),
                ..._reviewFindings(review, reviewError),
              ],
              const SizedBox(height: 10),
              const Text('This will be permanently attached to the patient\'s health record and is tamper-evident.'),
            ],
          ),
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
    final apptId = widget.appointment['id']?.toString() ?? widget.appointment['_id']?.toString() ?? '';

    try {
      // 1. Create the consultation record once; a retry after a failed prescription reuses it.
      if (_savedRecordId == null) {
        final record = await _service.createMedicalRecord(
          appointmentId: apptId,
          clinicalNotes: _clinicalNotesController.text,
          assessment: _assessmentController.text,
          treatmentPlan: _treatmentPlanController.text,
          followUpInstructions: _followUpController.text,
        );
        _savedRecordId = record.id;
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSubmitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to save record: $e'), backgroundColor: AppTheme.error),
      );
      return;
    }

    try {
      // 2. Issue the digital prescription exactly as reviewed.
      if (_includePrescription) {
        await _service.createPrescription(
          medicalRecordId: _savedRecordId!,
          appointmentId: apptId,
          medicationItems: items,
          instructions: _prescInstructionsController.text,
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSubmitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          key: const Key('rx_issue_failed_message'),
          content: Text('The consultation record was saved, but the prescription was not issued: $e. '
              'Correct it and tap the button again; the record will not be created twice.'),
          backgroundColor: AppTheme.error,
          duration: const Duration(seconds: 8),
        ),
      );
      return;
    }

    if (!mounted) return;
    setState(() => _isSubmitting = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(_includePrescription
            ? 'Consultation documented and prescription issued successfully.'
            : 'Consultation documented successfully.'),
        backgroundColor: AppTheme.success,
      ),
    );
    Navigator.of(context).pop(true);
  }

  List<Widget> _reviewFindings(Map<String, dynamic>? review, String? reviewError) {
    if (reviewError != null) {
      return [
        const SizedBox(height: 8),
        Text(reviewError, key: const Key('rx_review_unavailable'), style: const TextStyle(color: AppTheme.error)),
      ];
    }
    if (review == null) return const [];
    List<String> strings(String key) => (review[key] as List? ?? const []).map((e) => e.toString()).toList();
    final notes = (review['items'] as List? ?? const [])
        .expand((e) => ((e as Map)['notes'] as List? ?? const []).map((n) => n.toString()))
        .toList();
    final allergies = strings('allergyWarnings');
    final duplicates = strings('potentialDuplicates');
    final repeated = strings('repeatedMedicines');
    final missing = strings('missingFieldsWarnings');
    return [
      const SizedBox(height: 8),
      for (final text in allergies)
        Text(text,
            key: const Key('rx_review_allergy_warning'),
            style: const TextStyle(color: AppTheme.error, fontWeight: FontWeight.bold)),
      for (final text in duplicates) Text(text, style: const TextStyle(color: Colors.orange)),
      for (final text in repeated) Text('Entered more than once: $text', style: const TextStyle(color: Colors.orange)),
      for (final text in missing) Text(text, style: const TextStyle(color: Colors.orange)),
      for (final text in notes) Text(text, style: const TextStyle(fontSize: 12)),
      if (allergies.isEmpty && duplicates.isEmpty)
        const Text('No match with documented allergies or active MediConnect prescriptions.',
            key: Key('rx_review_no_match'), style: TextStyle(fontSize: 12)),
      const SizedBox(height: 4),
      Text(
        review['interactionCheckNotice']?.toString() ?? 'Drug-interaction checking is not available.',
        key: const Key('rx_review_interaction_notice'),
        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
      ),
    ];
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
                    key: Key('med_dose_$index'),
                    controller: med.doseController,
                    decoration: InputDecoration(
                      labelText: 'Dose *',
                      hintText: 'e.g. 1 tablet',
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
                    key: Key('med_frequency_$index'),
                    controller: med.frequencyController,
                    decoration: InputDecoration(
                      labelText: 'Frequency *',
                      hintText: 'e.g. Twice daily',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      isDense: true,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextFormField(
                    key: Key('med_duration_$index'),
                    controller: med.durationController,
                    decoration: InputDecoration(
                      labelText: 'Duration *',
                      hintText: 'e.g. 5 days',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      isDense: true,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            TextFormField(
              key: Key('med_quantity_$index'),
              controller: med.quantityController,
              decoration: InputDecoration(
                labelText: 'Quantity *',
                hintText: 'e.g. 10 tablets',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                isDense: true,
              ),
            ),
            const SizedBox(height: 10),
            TextFormField(
              key: Key('med_instructions_$index'),
              controller: med.instructionsController,
              decoration: InputDecoration(
                labelText: 'Instructions (optional)',
                hintText: 'e.g. Take after meals with water',
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
