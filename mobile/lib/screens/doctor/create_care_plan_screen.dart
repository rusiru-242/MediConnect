import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';
import '../../models/appointment.dart';
import '../../services/care_plan_service.dart';

/// Screen allowing an approved doctor to author a follow-up care plan for a consultation.
class CreateCarePlanScreen extends StatefulWidget {
  final Appointment? appointment;
  final String? appointmentId;
  final String? patientUserId;
  final String? patientName;
  final String? consultationDate;
  final CarePlanService? carePlanService;

  const CreateCarePlanScreen({
    super.key,
    this.appointment,
    this.appointmentId,
    this.patientUserId,
    this.patientName,
    this.consultationDate,
    this.carePlanService,
  });

  @override
  State<CreateCarePlanScreen> createState() => _CreateCarePlanScreenState();
}

class _CreateCarePlanScreenState extends State<CreateCarePlanScreen> {
  final _formKey = GlobalKey<FormState>();
  late final CarePlanService _carePlanService;

  String get _effectiveAppointmentId =>
      widget.appointment?.id ?? widget.appointmentId ?? '';
  String get _effectivePatientName =>
      widget.appointment?.patientName ?? widget.patientName ?? 'Patient';
  String? get _effectiveConsultationDate =>
      widget.appointment?.appointmentDate ?? widget.consultationDate;

  final _reasonController = TextEditingController();
  final _instructionsController = TextEditingController();

  DateTime _followUpDate = DateTime.now().add(const Duration(days: 7));
  DateTime? _followUpDateEnd;
  String _consultationType = 'IN_PERSON';

  final List<TextEditingController> _taskControllers = [];
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _carePlanService = widget.carePlanService ?? CarePlanService();
    // Default task
    _taskControllers.add(TextEditingController(text: 'Record blood pressure readings daily'));
  }

  @override
  void dispose() {
    _reasonController.dispose();
    _instructionsController.dispose();
    for (final c in _taskControllers) {
      c.dispose();
    }
    super.dispose();
  }

  void _addTask() {
    setState(() {
      _taskControllers.add(TextEditingController());
    });
  }

  void _removeTask(int index) {
    if (_taskControllers.length > 1) {
      setState(() {
        _taskControllers[index].dispose();
        _taskControllers.removeAt(index);
      });
    }
  }

  String _formatDate(DateTime dt) {
    final y = dt.year.toString().padLeft(4, '0');
    final m = dt.month.toString().padLeft(2, '0');
    final d = dt.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  Future<void> _pickFollowUpDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _followUpDate.isBefore(now) ? now : _followUpDate,
      firstDate: now,
      lastDate: now.add(const Duration(days: 365)),
    );
    if (picked != null) {
      setState(() {
        _followUpDate = picked;
        if (_followUpDateEnd != null && _followUpDateEnd!.isBefore(picked)) {
          _followUpDateEnd = null;
        }
      });
    }
  }

  Future<void> _pickFollowUpDateEnd() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _followUpDateEnd ?? _followUpDate.add(const Duration(days: 3)),
      firstDate: _followUpDate,
      lastDate: _followUpDate.add(const Duration(days: 90)),
    );
    if (picked != null) {
      setState(() {
        _followUpDateEnd = picked;
      });
    }
  }

  Future<void> _submitCarePlan() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final taskPayloads = _taskControllers
        .map((c) => c.text.trim())
        .where((t) => t.isNotEmpty)
        .map((t) => {'title': t})
        .toList();

    try {
      await _carePlanService.createCarePlan(
        appointmentId: _effectiveAppointmentId,
        followUpDate: _formatDate(_followUpDate),
        followUpDateEnd: _followUpDateEnd != null ? _formatDate(_followUpDateEnd!) : null,
        reason: _reasonController.text.trim(),
        instructions: _instructionsController.text.trim(),
        recommendedConsultationType: _consultationType,
        tasks: taskPayloads,
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Follow-up care plan created successfully.'),
          backgroundColor: AppTheme.success,
        ),
      );
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = e.toString().replaceAll('Exception:', '').trim();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Create Follow-up Plan', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.white,
        foregroundColor: AppTheme.textPrimary,
        elevation: 0.5,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Patient Banner
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.primary.withValues(alpha: 0.2)),
                ),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 20,
                      backgroundColor: AppTheme.primary.withValues(alpha: 0.15),
                      child: const Icon(Icons.person, color: AppTheme.primary),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _effectivePatientName,
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                          ),
                          if (_effectiveConsultationDate != null)
                            Text(
                              'Consultation Date: $_effectiveConsultationDate',
                              style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),

              if (_errorMessage != null) ...[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.error.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
                  ),
                  child: Text(_errorMessage!, style: const TextStyle(color: AppTheme.error)),
                ),
                const SizedBox(height: 16),
              ],

              // Date Selectors
              Card(
                elevation: 0.5,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(14.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Follow-up Schedule',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton.icon(
                              key: const Key('pick_follow_up_date_button'),
                              style: OutlinedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 12),
                              ),
                              onPressed: _pickFollowUpDate,
                              icon: const Icon(Icons.calendar_today_rounded, size: 18),
                              label: Text('Date: ${_formatDate(_followUpDate)}'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton.icon(
                              style: OutlinedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 12),
                              ),
                              onPressed: _pickFollowUpDateEnd,
                              icon: const Icon(Icons.date_range_rounded, size: 18),
                              label: Text(
                                _followUpDateEnd == null
                                    ? 'End Date (Opt)'
                                    : 'To: ${_formatDate(_followUpDateEnd!)}',
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      DropdownButtonFormField<String>(
                        initialValue: _consultationType,
                        decoration: const InputDecoration(
                          labelText: 'Recommended Consultation Type',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                        items: const [
                          DropdownMenuItem(value: 'IN_PERSON', child: Text('In-Person Visit')),
                          DropdownMenuItem(value: 'VIDEO', child: Text('Video Consultation')),
                          DropdownMenuItem(value: 'AUDIO', child: Text('Audio / Phone Consultation')),
                        ],
                        onChanged: (v) {
                          if (v != null) setState(() => _consultationType = v);
                        },
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Reason
              TextFormField(
                key: const Key('care_plan_reason_field'),
                controller: _reasonController,
                decoration: const InputDecoration(
                  labelText: 'Follow-up Reason *',
                  hintText: 'e.g. Hypertension review, lab results assessment',
                  border: OutlineInputBorder(),
                ),
                validator: (val) {
                  if (val == null || val.trim().length < 3) {
                    return 'Please enter a clear follow-up reason (min 3 chars).';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              // Care Instructions
              TextFormField(
                key: const Key('care_plan_instructions_field'),
                controller: _instructionsController,
                maxLines: 4,
                decoration: const InputDecoration(
                  labelText: 'Care Instructions *',
                  hintText: 'Dietary guidance, exercise precautions, symptom monitoring...',
                  border: OutlineInputBorder(),
                ),
                validator: (val) {
                  if (val == null || val.trim().length < 5) {
                    return 'Please enter care instructions (min 5 chars).';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 20),

              // Non-medication Tasks
              Card(
                elevation: 0.5,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(14.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Patient Care Tasks (Non-Medication)',
                            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                          ),
                          TextButton.icon(
                            key: const Key('add_care_task_button'),
                            onPressed: _addTask,
                            icon: const Icon(Icons.add_rounded, size: 18),
                            label: const Text('Add Task'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      ..._taskControllers.asMap().entries.map((entry) {
                        final i = entry.key;
                        final ctrl = entry.value;
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 8.0),
                          child: Row(
                            children: [
                              Expanded(
                                child: TextFormField(
                                  key: Key('care_plan_task_input_$i'),
                                  controller: ctrl,
                                  decoration: InputDecoration(
                                    labelText: 'Task ${i + 1}',
                                    hintText: 'e.g. Bring fasting blood sugar report',
                                    border: const OutlineInputBorder(),
                                    isDense: true,
                                  ),
                                ),
                              ),
                              if (_taskControllers.length > 1)
                                IconButton(
                                  icon: const Icon(Icons.remove_circle_outline, color: AppTheme.error),
                                  onPressed: () => _removeTask(i),
                                ),
                            ],
                          ),
                        );
                      }),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Submit Button
              ElevatedButton.icon(
                key: const Key('submit_care_plan_button'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: _isLoading ? null : _submitCarePlan,
                icon: _isLoading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.check_circle_outline_rounded),
                label: Text(
                  _isLoading ? 'Creating Plan...' : 'Create Follow-up Plan',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
