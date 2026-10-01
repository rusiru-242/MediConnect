import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/doctor.dart';
import '../../models/doctor_availability.dart';
import '../../services/doctor_service.dart';
import 'booking_confirmation_screen.dart';

/// Screen displaying public doctor details and patient-facing availability slots.
class DoctorDetailScreen extends StatefulWidget {
  final Doctor? doctor;
  final String? doctorId;
  final DoctorService? doctorService;

  const DoctorDetailScreen({
    super.key,
    this.doctor,
    this.doctorId,
    this.doctorService,
  });

  @override
  State<DoctorDetailScreen> createState() => _DoctorDetailScreenState();
}

class _DoctorDetailScreenState extends State<DoctorDetailScreen> {
  late final DoctorService _doctorService;
  Doctor? _doctor;
  String? _effectiveDoctorId;

  bool _isLoadingDoctor = false;
  String? _doctorError;

  bool _isLoadingAvailability = false;
  String? _availabilityError;
  List<DayAvailabilitySlots> _dayAvailabilities = [];

  String? _selectedDate;
  String? _selectedSlotStartTime;

  @override
  void initState() {
    super.initState();
    _doctorService = widget.doctorService ?? DoctorService();
    _doctor = widget.doctor;
    _effectiveDoctorId = widget.doctor?.doctorId ?? widget.doctorId;
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_doctor == null && _effectiveDoctorId == null) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is Doctor) {
        _doctor = args;
        _effectiveDoctorId = args.doctorId;
      } else if (args is Map<String, dynamic> && args.containsKey('doctorId')) {
        _effectiveDoctorId = args['doctorId'].toString();
      } else if (args is String) {
        _effectiveDoctorId = args;
      }
    }

    if (_doctor == null && _effectiveDoctorId != null && !_isLoadingDoctor) {
      _loadDoctorDetail();
    } else if (_doctor != null && _dayAvailabilities.isEmpty && !_isLoadingAvailability) {
      _loadAvailability();
    }
  }

  Future<void> _loadDoctorDetail() async {
    if (_effectiveDoctorId == null) return;
    setState(() {
      _isLoadingDoctor = true;
      _doctorError = null;
    });

    try {
      final doc = await _doctorService.getDoctorDetail(_effectiveDoctorId!);
      if (!mounted) return;
      setState(() {
        _doctor = doc;
        _isLoadingDoctor = false;
      });
      _loadAvailability();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _doctorError = 'Unable to connect to MediConnect. Please try again.';
        _isLoadingDoctor = false;
      });
    }
  }

  Future<void> _loadAvailability() async {
    final docId = _doctor?.doctorId ?? _effectiveDoctorId;
    if (docId == null) return;

    setState(() {
      _isLoadingAvailability = true;
      _availabilityError = null;
    });

    try {
      final slots = await _doctorService.getDoctorAvailability(docId);
      if (!mounted) return;
      setState(() {
        _dayAvailabilities = slots;
        _isLoadingAvailability = false;
        if (_dayAvailabilities.isNotEmpty) {
          _selectedDate = _dayAvailabilities.first.date;
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _availabilityError = 'Unable to connect to MediConnect. Please try again.';
        _isLoadingAvailability = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Doctor Profile'),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoadingDoctor) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_doctorError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 54, color: AppTheme.error),
              const SizedBox(height: 16),
              Text(
                _doctorError!,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 15, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: _loadDoctorDetail,
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    final doctor = _doctor;
    if (doctor == null) {
      return const Center(child: Text('Doctor not found.'));
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Doctor Header Card
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            elevation: 1,
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 40,
                    backgroundColor: AppTheme.primaryContainer,
                    child: Text(
                      doctor.fullName.isNotEmpty
                          ? doctor.fullName.replaceFirst('Dr. ', '').split(' ').map((n) => n.isNotEmpty ? n[0] : '').take(2).join()
                          : 'DR',
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.onPrimaryContainer,
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    doctor.fullName,
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    doctor.specialty,
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppTheme.primary),
                  ),
                  const SizedBox(height: 10),
                  // Verified Doctor Indicator
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.success.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: AppTheme.success.withValues(alpha: 0.3)),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.verified_rounded, size: 16, color: AppTheme.success),
                        SizedBox(width: 6),
                        Text(
                          'Verified Doctor',
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.success),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 16),

          // Qualifications & Practice Details
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            elevation: 1,
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Professional Details', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 14),
                  if (doctor.qualifications != null && doctor.qualifications!.isNotEmpty) ...[
                    _buildDetailRow(Icons.school_outlined, 'Qualifications', doctor.qualifications!),
                    const Divider(height: 20),
                  ],
                  _buildDetailRow(Icons.local_hospital_outlined, 'Hospital / Clinic', doctor.hospitalOrClinic),
                  const Divider(height: 20),
                  _buildDetailRow(Icons.work_history_outlined, 'Experience', '${doctor.experienceYears} Years'),
                  if (doctor.bio != null && doctor.bio!.isNotEmpty) ...[
                    const Divider(height: 20),
                    _buildDetailRow(Icons.info_outline, 'About', doctor.bio!),
                  ],
                ],
              ),
            ),
          ),

          const SizedBox(height: 20),

          // Availability Section
          const Text(
            'Available Dates & Times',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
          ),
          const SizedBox(height: 12),

          _buildAvailabilitySection(),
        ],
      ),
    );
  }

  Widget _buildDetailRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 20, color: AppTheme.primary),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              const SizedBox(height: 2),
              Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: AppTheme.textPrimary)),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildAvailabilitySection() {
    if (_isLoadingAvailability) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(32.0),
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }

    if (_availabilityError != null) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            children: [
              Text(_availabilityError!, style: const TextStyle(color: AppTheme.textSecondary)),
              const SizedBox(height: 12),
              ElevatedButton.icon(
                onPressed: _loadAvailability,
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_dayAvailabilities.isEmpty) {
      return Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: const Padding(
          padding: EdgeInsets.all(24.0),
          child: Center(
            child: Column(
              children: [
                Icon(Icons.event_busy_rounded, size: 48, color: AppTheme.textSecondary),
                SizedBox(height: 12),
                Text(
                  'No available time slots currently.',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w500, color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final selectedDay = _dayAvailabilities.firstWhere(
      (d) => d.date == _selectedDate,
      orElse: () => _dayAvailabilities.first,
    );

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Select Date',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 10),

            // Available Dates Selector
            SizedBox(
              height: 48,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: _dayAvailabilities.length,
                itemBuilder: (context, index) {
                  final day = _dayAvailabilities[index];
                  final isSelected = day.date == _selectedDate;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8.0),
                    child: ChoiceChip(
                      key: Key('date_chip_${day.date}'),
                      selected: isSelected,
                      label: Text(
                        day.date,
                        style: TextStyle(
                          color: isSelected ? Colors.white : AppTheme.textPrimary,
                          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                        ),
                      ),
                      selectedColor: AppTheme.primary,
                      backgroundColor: Colors.white,
                      onSelected: (selected) {
                        if (selected) {
                          setState(() {
                            _selectedDate = day.date;
                            _selectedSlotStartTime = null;
                          });
                        }
                      },
                    ),
                  );
                },
              ),
            ),

            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 10),

            Text(
              'Available Slots for ${selectedDay.date}',
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 12),

            // Time Slots Wrap
            if (selectedDay.slots.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 16),
                child: Text('No slots remaining on this date.', style: TextStyle(color: AppTheme.textSecondary)),
              )
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: selectedDay.slots.map((slot) {
                  final isSelected = _selectedSlotStartTime == slot.startTime;
                  return ChoiceChip(
                    key: Key('slot_chip_${slot.startTime}'),
                    selected: isSelected,
                    label: Text(
                      '${slot.startTime} - ${slot.endTime}',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                        color: isSelected ? Colors.white : AppTheme.textPrimary,
                      ),
                    ),
                    selectedColor: AppTheme.primary,
                    backgroundColor: AppTheme.surfaceVariant.withValues(alpha: 0.4),
                    side: BorderSide(
                      color: isSelected ? AppTheme.primary : AppTheme.outline.withValues(alpha: 0.3),
                    ),
                    onSelected: (selected) {
                      setState(() {
                        _selectedSlotStartTime = selected ? slot.startTime : null;
                      });
                    },
                  );
                }).toList(),
              ),

            const SizedBox(height: 20),

            // Functional Booking Action Button
            Builder(
              builder: (context) {
                TimeSlot? selectedSlot;
                if (_selectedSlotStartTime != null) {
                  try {
                    selectedSlot = selectedDay.slots.firstWhere(
                      (s) => s.startTime == _selectedSlotStartTime,
                    );
                  } catch (_) {}
                }

                final isEnabled = _selectedSlotStartTime != null &&
                    _doctor != null &&
                    selectedSlot != null;

                return SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    key: const Key('book_appointment_button'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: isEnabled
                          ? AppTheme.primary
                          : AppTheme.outline.withValues(alpha: 0.3),
                      foregroundColor: isEnabled
                          ? Colors.white
                          : AppTheme.textSecondary,
                      elevation: isEnabled ? 2 : 0,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    onPressed: isEnabled
                        ? () async {
                            final shouldRefresh = await Navigator.push<bool>(
                              context,
                              MaterialPageRoute(
                                builder: (_) => BookingConfirmationScreen(
                                  doctor: _doctor!,
                                  date: selectedDay.date,
                                  slot: selectedSlot!,
                                ),
                              ),
                            );
                            if (shouldRefresh == true) {
                              setState(() {
                                _selectedSlotStartTime = null;
                              });
                              _loadAvailability();
                            }
                          }
                        : null,
                    child: Text(
                      _selectedSlotStartTime != null
                          ? 'Continue to Booking ($_selectedSlotStartTime)'
                          : 'Select a Time Slot',
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 15,
                      ),
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
