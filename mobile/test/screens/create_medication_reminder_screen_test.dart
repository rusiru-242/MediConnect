import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/medication_reminder.dart';
import 'package:mediconnect/models/prescription.dart';
import 'package:mediconnect/screens/patient/create_medication_reminder_screen.dart';
import 'package:mediconnect/services/medication_reminder_service.dart';

class MockReminderServiceForCreate extends MedicationReminderService {
  bool createReminderCalled = false;
  String? createdPrescriptionId;
  List<String>? createdScheduledTimes;

  @override
  Future<MedicationReminder> createReminder({
    required String prescriptionId,
    required int prescriptionMedicationIndex,
    required List<String> scheduledTimes,
    String patientTimezone = 'Asia/Colombo',
    String? notes,
  }) async {
    createReminderCalled = true;
    createdPrescriptionId = prescriptionId;
    createdScheduledTimes = scheduledTimes;
    return MedicationReminder(
      id: 'REM-DB-1',
      reminderId: 'REM-TEST-001',
      patientUserId: 'USER-1',
      prescriptionId: prescriptionId,
      prescriptionDbId: 'RX-DB-1',
      prescriptionMedicationIndex: prescriptionMedicationIndex,
      medicationName: 'Amoxicillin',
      strength: '500mg',
      dose: '1 capsule',
      route: 'Oral',
      frequency: 'Twice daily',
      duration: '5 days',
      scheduledTimes: scheduledTimes,
      patientTimezone: patientTimezone,
      startDate: DateTime.now(),
      endDate: DateTime.now().add(const Duration(days: 5)),
      enabled: true,
      status: 'ACTIVE',
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );
  }
}

void main() {
  group('CreateMedicationReminderScreen Widget Tests', () {
    testWidgets('renders prescribed medication details and creates reminder matching frequency',
        (tester) async {
      tester.view.physicalSize = const Size(600, 1400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final samplePrescription = Prescription(
        id: '670000000000000000000001',
        prescriptionId: 'RX-20261018-ABC123',
        medicalRecordId: 'REC-1',
        appointmentId: 'APPT-1',
        patientUserId: 'PAT-1',
        doctorUserId: 'DOC-1',
        doctorName: 'Dr. Silva',
        issuedAt: DateTime.now(),
        status: 'ISSUED',
        medicationItems: const [
          MedicationItem(
            medicationName: 'Amoxicillin',
            strength: '500mg',
            dose: '1 capsule',
            route: 'Oral',
            frequency: 'Twice daily',
            duration: '5 days',
            quantity: '10 capsules',
            additionalInstructions: 'Take after meals',
          ),
        ],
        instructions: 'Complete full course',
      );

      final mockService = MockReminderServiceForCreate();

      await tester.pumpWidget(
        MaterialApp(
          home: CreateMedicationReminderScreen(
            initialPrescription: samplePrescription,
            initialMedicationIndex: 0,
            reminderService: mockService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('New Medication Reminder'), findsOneWidget);
      expect(find.text('Amoxicillin'), findsOneWidget);
      expect(find.text('Dose 1'), findsOneWidget);
      expect(find.text('Dose 2'), findsOneWidget);
      expect(find.text('Save & Schedule Reminder'), findsOneWidget);

      // Verify Safety banner
      expect(
        find.textContaining('Medication dosage, route, and frequency are prescribed by your doctor'),
        findsOneWidget,
      );

      // Ensure button is visible in scrollview before tapping
      await tester.ensureVisible(find.text('Save & Schedule Reminder'));
      await tester.pumpAndSettle();

      // Tap Save & Schedule Reminder
      await tester.tap(find.text('Save & Schedule Reminder'));
      await tester.pumpAndSettle();

      expect(mockService.createReminderCalled, isTrue);
      expect(mockService.createdPrescriptionId, 'RX-20261018-ABC123');
      expect(mockService.createdScheduledTimes?.length, 2);
    });
  });
}
