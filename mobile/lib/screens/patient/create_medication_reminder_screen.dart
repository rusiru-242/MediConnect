import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/prescription.dart';
import '../../services/medical_record_service.dart';
import '../../services/medication_reminder_service.dart';

/// Screen enabling patient to create a new medication reminder schedule from an issued prescription.
class CreateMedicationReminderScreen extends StatefulWidget {
  final Prescription? initialPrescription;
  final int? initialMedicationIndex;
  final MedicationReminderService? reminderService;
  final MedicalRecordService? recordService;

  const CreateMedicationReminderScreen({
    super.key,
    this.initialPrescription,
    this.initialMedicationIndex,
    this.reminderService,
    this.recordService,
  });

  @override
  State<CreateMedicationReminderScreen> createState() => _CreateMedicationReminderScreenState();
}

class _CreateMedicationReminderScreenState extends State<CreateMedicationReminderScreen> {
  late final MedicationReminderService _reminderService;
  late final MedicalRecordService _recordService;

  List<Prescription> _prescriptions = [];
  Prescription? _selectedPrescription;
  int _selectedMedicationIndex = 0;

  List<TimeOfDay> _selectedTimes = [const TimeOfDay(hour: 8, minute: 0)];
  final TextEditingController _notesController = TextEditingController();

  bool _isLoadingPrescriptions = false;
  bool _isSubmitting = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _reminderService = widget.reminderService ?? MedicationReminderService();
    _recordService = widget.recordService ?? MedicalRecordService();

    if (widget.initialPrescription != null) {
      _selectedPrescription = widget.initialPrescription;
      _selectedMedicationIndex = widget.initialMedicationIndex ?? 0;
      _setupTimesForSelectedMedication();
    } else {
      _loadPrescriptions();
    }
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _loadPrescriptions() async {
    setState(() {
      _isLoadingPrescriptions = true;
      _errorMessage = null;
    });

    try {
      final res = await _recordService.getPatientPrescriptions();
      if (mounted) {
        // Filter only valid issued/amended prescriptions
        final valid = res.where((p) => p.status != 'CANCELLED' && p.medicationItems.isNotEmpty).toList();
        setState(() {
          _prescriptions = valid;
          if (valid.isNotEmpty) {
            _selectedPrescription = valid.first;
            _selectedMedicationIndex = 0;
            _setupTimesForSelectedMedication();
          }
          _isLoadingPrescriptions = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Could not load prescriptions: $e';
          _isLoadingPrescriptions = false;
        });
      }
    }
  }

  int _expectedDoses(String frequency) {
    final f = frequency.toLowerCase();
    if (f.contains('twice') || f.contains('bd') || f.contains('bid')) return 2;
    if (f.contains('three') || f.contains('thrice') || f.contains('tds') || f.contains('tid')) return 3;
    if (f.contains('four') || f.contains('qds') || f.contains('qid')) return 4;
    return 1;
  }

  void _setupTimesForSelectedMedication() {
    if (_selectedPrescription == null) return;
    final items = _selectedPrescription!.medicationItems;
    if (_selectedMedicationIndex >= items.length) {
      _selectedMedicationIndex = 0;
    }
    final med = items[_selectedMedicationIndex];
    final count = _expectedDoses(med.frequency);

    if (count == 1) {
      _selectedTimes = [const TimeOfDay(hour: 8, minute: 0)];
    } else if (count == 2) {
      _selectedTimes = [
        const TimeOfDay(hour: 8, minute: 0),
        const TimeOfDay(hour: 20, minute: 0),
      ];
    } else if (count == 3) {
      _selectedTimes = [
        const TimeOfDay(hour: 8, minute: 0),
        const TimeOfDay(hour: 14, minute: 0),
        const TimeOfDay(hour: 20, minute: 0),
      ];
    } else if (count == 4) {
      _selectedTimes = [
        const TimeOfDay(hour: 6, minute: 0),
        const TimeOfDay(hour: 12, minute: 0),
        const TimeOfDay(hour: 18, minute: 0),
        const TimeOfDay(hour: 22, minute: 0),
      ];
    }
  }

  Future<void> _pickTime(int index) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _selectedTimes[index],
    );
    if (picked != null) {
      setState(() {
        _selectedTimes[index] = picked;
      });
    }
  }

  String _formatTimeOfDay(TimeOfDay tod) {
    final h = tod.hour.toString().padLeft(2, '0');
    final m = tod.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }

  Future<void> _submitReminder() async {
    if (_selectedPrescription == null) {
      setState(() {
        _errorMessage = 'Please select a valid doctor-issued prescription.';
      });
      return;
    }

    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      final formattedTimes = _selectedTimes.map(_formatTimeOfDay).toList();
      await _reminderService.createReminder(
        prescriptionId: _selectedPrescription!.prescriptionId,
        prescriptionMedicationIndex: _selectedMedicationIndex,
        scheduledTimes: formattedTimes,
        patientTimezone: 'Asia/Colombo',
        notes: _notesController.text.trim(),
      );

      if (mounted) {
        messenger.showSnackBar(
          const SnackBar(
            content: Text('Medication reminder scheduled successfully!'),
            backgroundColor: AppTheme.success,
          ),
        );
        navigator.pop(true);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceAll('Exception:', '').trim();
          _isSubmitting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('New Medication Reminder'),
        elevation: 0,
      ),
      body: _isLoadingPrescriptions
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Medical Safety Banner (Section 8 Requirement)
                  Container(
                    padding: const EdgeInsets.all(14.0),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryContainer.withValues(alpha: 0.5),
                      borderRadius: BorderRadius.circular(12.0),
                      border: Border.all(color: AppTheme.primaryLight.withValues(alpha: 0.5)),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.verified_user, color: AppTheme.primaryDark, size: 22),
                        const SizedBox(width: 12.0),
                        Expanded(
                          child: Text(
                            'Medication dosage, route, and frequency are prescribed by your doctor and cannot be modified. The reminder system helps you organize your intake schedule.',
                            style: TextStyle(
                              fontSize: 12.5,
                              color: AppTheme.onPrimaryContainer,
                              height: 1.4,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 18.0),

                  // Prescription Selection
                  if (widget.initialPrescription == null) ...[
                    const Text(
                      'Select Prescription',
                      style: TextStyle(
                        fontSize: 15.0,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 8.0),
                    if (_prescriptions.isEmpty)
                      Container(
                        padding: const EdgeInsets.all(16.0),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(12.0),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: const Text(
                          'No valid active prescriptions found. Reminders can only be scheduled for doctor-issued prescriptions.',
                          style: TextStyle(color: AppTheme.textSecondary, fontSize: 13.0),
                        ),
                      )
                    else
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14.0),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(12.0),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<Prescription>(
                            isExpanded: true,
                            value: _selectedPrescription,
                            items: _prescriptions.map((p) {
                              return DropdownMenuItem<Prescription>(
                                value: p,
                                child: Text(
                                  '${p.prescriptionId} (${p.doctorName ?? "Verified Doctor"})',
                                  style: const TextStyle(fontSize: 14.0),
                                ),
                              );
                            }).toList(),
                            onChanged: (p) {
                              if (p != null) {
                                setState(() {
                                  _selectedPrescription = p;
                                  _selectedMedicationIndex = 0;
                                  _setupTimesForSelectedMedication();
                                });
                              }
                            },
                          ),
                        ),
                      ),
                    const SizedBox(height: 18.0),
                  ],

                  // Medication Item Selection
                  if (_selectedPrescription != null &&
                      _selectedPrescription!.medicationItems.isNotEmpty) ...[
                    const Text(
                      'Prescribed Medication Item',
                      style: TextStyle(
                        fontSize: 15.0,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 8.0),
                    for (int i = 0; i < _selectedPrescription!.medicationItems.length; i++) ...[
                      InkWell(
                        onTap: () {
                          setState(() {
                            _selectedMedicationIndex = i;
                            _setupTimesForSelectedMedication();
                          });
                        },
                        borderRadius: BorderRadius.circular(10.0),
                        child: Container(
                          margin: const EdgeInsets.only(bottom: 8.0),
                          padding: const EdgeInsets.symmetric(horizontal: 12.0, vertical: 10.0),
                          decoration: BoxDecoration(
                            color: _selectedMedicationIndex == i
                                ? AppTheme.primaryContainer.withValues(alpha: 0.3)
                                : Colors.white,
                            borderRadius: BorderRadius.circular(10.0),
                            border: Border.all(
                              color: _selectedMedicationIndex == i
                                  ? AppTheme.primary
                                  : AppTheme.border,
                              width: _selectedMedicationIndex == i ? 1.5 : 1.0,
                            ),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                _selectedMedicationIndex == i
                                    ? Icons.radio_button_checked
                                    : Icons.radio_button_off,
                                color: _selectedMedicationIndex == i
                                    ? AppTheme.primary
                                    : AppTheme.textMuted,
                                size: 20,
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      _selectedPrescription!.medicationItems[i].medicationName,
                                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14.5),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      '${_selectedPrescription!.medicationItems[i].strength} • ${_selectedPrescription!.medicationItems[i].dose} • ${_selectedPrescription!.medicationItems[i].frequency} (${_selectedPrescription!.medicationItems[i].duration})',
                                      style: const TextStyle(fontSize: 12.0, color: AppTheme.textSecondary),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 14.0),

                    // Doctor Prescribed Summary Card
                    Builder(builder: (context) {
                      final currentMed =
                          _selectedPrescription!.medicationItems[_selectedMedicationIndex];
                      return Container(
                        padding: const EdgeInsets.all(14.0),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(12.0),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text('Prescribed Dose:', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13.0)),
                                const SizedBox(width: 8.0),
                                Expanded(
                                  child: Text(
                                    currentMed.dose,
                                    style: const TextStyle(fontWeight: FontWeight.bold),
                                    textAlign: TextAlign.end,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6.0),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text('Prescribed Route:', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13.0)),
                                const SizedBox(width: 8.0),
                                Expanded(
                                  child: Text(
                                    currentMed.route,
                                    style: const TextStyle(fontWeight: FontWeight.bold),
                                    textAlign: TextAlign.end,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6.0),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text('Prescribed Frequency:', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13.0)),
                                const SizedBox(width: 8.0),
                                Expanded(
                                  child: Text(
                                    '${currentMed.frequency} (${_selectedTimes.length} time/day)',
                                    style: const TextStyle(fontWeight: FontWeight.bold, color: AppTheme.primaryDark),
                                    textAlign: TextAlign.end,
                                  ),
                                ),
                              ],
                            ),
                            if (currentMed.additionalInstructions != null &&
                                currentMed.additionalInstructions!.isNotEmpty) ...[
                              const Divider(height: 16.0),
                              Text(
                                'Doctor\'s Instructions: ${currentMed.additionalInstructions}',
                                style: const TextStyle(fontSize: 12.0, fontStyle: FontStyle.italic, color: AppTheme.textSecondary),
                              ),
                            ],
                          ],
                        ),
                      );
                    }),
                    const SizedBox(height: 20.0),

                    // Pick Reminder Times
                    Text(
                      'Choose Reminder Times (${_selectedTimes.length} per day)',
                      style: const TextStyle(
                        fontSize: 15.0,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 6.0),
                    const Text(
                      'Select convenient daily times for your alerts:',
                      style: TextStyle(fontSize: 12.0, color: AppTheme.textSecondary),
                    ),
                    const SizedBox(height: 10.0),

                    for (int i = 0; i < _selectedTimes.length; i++)
                      Container(
                        margin: const EdgeInsets.only(bottom: 8.0),
                        padding: const EdgeInsets.symmetric(horizontal: 14.0, vertical: 8.0),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(12.0),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Row(
                              children: [
                                const Icon(Icons.access_time, color: AppTheme.primary, size: 20),
                                const SizedBox(width: 8.0),
                                Text('Dose ${i + 1}', style: const TextStyle(fontWeight: FontWeight.w600)),
                              ],
                            ),
                            TextButton.icon(
                              onPressed: () => _pickTime(i),
                              icon: const Icon(Icons.edit, size: 16),
                              label: Text(
                                _selectedTimes[i].format(context),
                                style: const TextStyle(
                                  fontSize: 16.0,
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.primary,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    const SizedBox(height: 16.0),

                    // Personal Notes
                    const Text(
                      'Personal Notes (Optional)',
                      style: TextStyle(
                        fontSize: 14.0,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 8.0),
                    TextField(
                      controller: _notesController,
                      maxLines: 2,
                      decoration: const InputDecoration(
                        hintText: 'e.g. Keep in desk drawer, take with full glass of water',
                        border: OutlineInputBorder(),
                        filled: true,
                        fillColor: Colors.white,
                      ),
                    ),
                  ],

                  if (_errorMessage != null) ...[
                    const SizedBox(height: 16.0),
                    Container(
                      padding: const EdgeInsets.all(12.0),
                      decoration: BoxDecoration(
                        color: AppTheme.errorContainer,
                        borderRadius: BorderRadius.circular(10.0),
                      ),
                      child: Text(
                        _errorMessage!,
                        style: const TextStyle(color: AppTheme.error, fontSize: 13.0),
                      ),
                    ),
                  ],

                  const SizedBox(height: 24.0),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primary,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14.0),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12.0)),
                    ),
                    onPressed: _isSubmitting || _selectedPrescription == null
                        ? null
                        : _submitReminder,
                    child: _isSubmitting
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                          )
                        : const Text(
                            'Save & Schedule Reminder',
                            style: TextStyle(fontSize: 15.0, fontWeight: FontWeight.bold),
                          ),
                  ),
                ],
              ),
            ),
    );
  }
}
