import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/doctor_availability.dart';
import '../../services/doctor_service.dart';

/// Screen allowing doctors to create or update an availability window.
class AddAvailabilityScreen extends StatefulWidget {
  final DoctorAvailability? existingAvailability;
  final DoctorService? doctorService;

  const AddAvailabilityScreen({
    super.key,
    this.existingAvailability,
    this.doctorService,
  });

  @override
  State<AddAvailabilityScreen> createState() => _AddAvailabilityScreenState();
}

class _AddAvailabilityScreenState extends State<AddAvailabilityScreen> {
  late final DoctorService _doctorService;
  DoctorAvailability? _existing;

  DateTime? _selectedDate;
  TimeOfDay? _startTime;
  TimeOfDay? _endTime;
  int _selectedSlotDuration = 30;

  bool _isSaving = false;
  String? _formError;

  final List<int> _allowedDurations = [15, 20, 30, 45, 60];

  @override
  void initState() {
    super.initState();
    _doctorService = widget.doctorService ?? DoctorService();
    _existing = widget.existingAvailability;

    if (_existing != null) {
      _initFromExisting(_existing!);
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_existing == null) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is DoctorAvailability) {
        _existing = args;
        _initFromExisting(args);
      }
    }
  }

  void _initFromExisting(DoctorAvailability item) {
    _selectedDate = DateTime.tryParse(item.date);
    final startParts = item.startTime.split(':');
    if (startParts.length == 2) {
      _startTime = TimeOfDay(hour: int.parse(startParts[0]), minute: int.parse(startParts[1]));
    }
    final endParts = item.endTime.split(':');
    if (endParts.length == 2) {
      _endTime = TimeOfDay(hour: int.parse(endParts[0]), minute: int.parse(endParts[1]));
    }
    _selectedSlotDuration = item.slotDurationMinutes;
  }

  String _formatDate(DateTime date) {
    final year = date.year.toString().padLeft(4, '0');
    final month = date.month.toString().padLeft(2, '0');
    final day = date.day.toString().padLeft(2, '0');
    return '$year-$month-$day';
  }

  String _formatTime(TimeOfDay time) {
    final hour = time.hour.toString().padLeft(2, '0');
    final minute = time.minute.toString().padLeft(2, '0');
    return '$hour:$minute';
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final initial = _selectedDate != null && !_selectedDate!.isBefore(DateTime(now.year, now.month, now.day))
        ? _selectedDate!
        : now;

    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(now.year, now.month, now.day),
      lastDate: now.add(const Duration(days: 180)),
    );

    if (picked != null) {
      setState(() {
        _selectedDate = picked;
        _formError = null;
      });
    }
  }

  Future<void> _pickStartTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _startTime ?? const TimeOfDay(hour: 9, minute: 0),
    );
    if (picked != null) {
      setState(() {
        _startTime = picked;
        _formError = null;
      });
    }
  }

  Future<void> _pickEndTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _endTime ?? const TimeOfDay(hour: 12, minute: 0),
    );
    if (picked != null) {
      setState(() {
        _endTime = picked;
        _formError = null;
      });
    }
  }

  String? _validate() {
    if (_selectedDate == null) {
      return 'Please select a date.';
    }

    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final targetDay = DateTime(_selectedDate!.year, _selectedDate!.month, _selectedDate!.day);
    if (targetDay.isBefore(today)) {
      return 'Cannot schedule availability for a past date.';
    }

    if (_startTime == null) {
      return 'Please choose a start time.';
    }
    if (_endTime == null) {
      return 'Please choose an end time.';
    }

    final startMinutes = _startTime!.hour * 60 + _startTime!.minute;
    final endMinutes = _endTime!.hour * 60 + _endTime!.minute;

    if (startMinutes >= endMinutes) {
      return 'Start time must be earlier than end time.';
    }

    final windowMinutes = endMinutes - startMinutes;
    if (windowMinutes < _selectedSlotDuration) {
      return 'Availability window ($windowMinutes min) must be at least one slot duration ($_selectedSlotDuration min).';
    }

    return null;
  }

  Future<void> _saveAvailability() async {
    final validationError = _validate();
    if (validationError != null) {
      setState(() {
        _formError = validationError;
      });
      return;
    }

    setState(() {
      _isSaving = true;
      _formError = null;
    });

    final dateStr = _formatDate(_selectedDate!);
    final startStr = _formatTime(_startTime!);
    final endStr = _formatTime(_endTime!);

    try {
      if (_existing != null) {
        await _doctorService.updateAvailability(
          _existing!.id,
          date: dateStr,
          startTime: startStr,
          endTime: endStr,
          slotDurationMinutes: _selectedSlotDuration,
        );
      } else {
        await _doctorService.createAvailability(
          date: dateStr,
          startTime: startStr,
          endTime: endStr,
          slotDurationMinutes: _selectedSlotDuration,
        );
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(_existing != null ? 'Availability updated successfully.' : 'Availability saved successfully.'),
          backgroundColor: AppTheme.success,
        ),
      );
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _formError = e.toString().replaceFirst('ApiException: ', '').replaceFirst('Exception: ', '');
        _isSaving = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isEditing = _existing != null;
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Text(isEditing ? 'Edit Availability' : 'Add Availability'),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_formError != null) ...[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.error.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline, color: AppTheme.error, size: 20),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          _formError!,
                          style: const TextStyle(color: AppTheme.error, fontSize: 13),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],

              // Date Picker Card
              Card(
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                child: ListTile(
                  key: const Key('add_availability_date_picker_tile'),
                  leading: const Icon(Icons.calendar_today_rounded, color: AppTheme.primary),
                  title: const Text('Date', style: TextStyle(fontSize: 14, color: AppTheme.textSecondary)),
                  subtitle: Text(
                    _selectedDate != null ? _formatDate(_selectedDate!) : 'Select Date',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: _selectedDate != null ? AppTheme.textPrimary : AppTheme.textSecondary,
                    ),
                  ),
                  trailing: const Icon(Icons.edit_calendar_rounded, size: 20),
                  onTap: _pickDate,
                ),
              ),

              const SizedBox(height: 16),

              // Time Pickers Row
              Row(
                children: [
                  Expanded(
                    child: Card(
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      child: ListTile(
                        key: const Key('add_availability_start_time_tile'),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                        leading: const Icon(Icons.access_time_rounded, color: AppTheme.primary, size: 22),
                        title: const Text('Start Time', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                        subtitle: Text(
                          _startTime != null ? _formatTime(_startTime!) : 'Select',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            color: _startTime != null ? AppTheme.textPrimary : AppTheme.textSecondary,
                          ),
                        ),
                        onTap: _pickStartTime,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Card(
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      child: ListTile(
                        key: const Key('add_availability_end_time_tile'),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                        leading: const Icon(Icons.update_rounded, color: AppTheme.primary, size: 22),
                        title: const Text('End Time', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                        subtitle: Text(
                          _endTime != null ? _formatTime(_endTime!) : 'Select',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            color: _endTime != null ? AppTheme.textPrimary : AppTheme.textSecondary,
                          ),
                        ),
                        onTap: _pickEndTime,
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 20),

              // Slot Duration Selector
              Card(
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Slot Duration',
                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'Duration of each patient appointment slot within this window',
                        style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        children: _allowedDurations.map((duration) {
                          final isSelected = _selectedSlotDuration == duration;
                          return ChoiceChip(
                            key: Key('duration_chip_${duration}min'),
                            selected: isSelected,
                            label: Text('$duration min'),
                            selectedColor: AppTheme.primary,
                            labelStyle: TextStyle(
                              color: isSelected ? Colors.white : AppTheme.textPrimary,
                              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                            ),
                            onSelected: (selected) {
                              if (selected) {
                                setState(() {
                                  _selectedSlotDuration = duration;
                                  _formError = null;
                                });
                              }
                            },
                          );
                        }).toList(),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 32),

              // Save Button
              ElevatedButton(
                key: const Key('save_availability_button'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: _isSaving ? null : _saveAvailability,
                child: _isSaving
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : Text(
                        isEditing ? 'Update Availability' : 'Save Availability',
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
