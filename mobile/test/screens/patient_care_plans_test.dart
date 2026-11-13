import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/appointment.dart';
import 'package:mediconnect/models/care_plan.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/doctor/create_care_plan_screen.dart';
import 'package:mediconnect/screens/patient/patient_care_plans_screen.dart';
import 'package:mediconnect/services/care_plan_service.dart';
import 'package:provider/provider.dart';

class MockCarePlanService extends CarePlanService {
  List<CarePlan> patientPlans = [
    CarePlan(
      id: 'PLAN-1',
      patientUserId: 'PAT-1',
      patientName: 'Kasun Wickrama',
      doctorUserId: 'DOC-1',
      doctorProfileId: 'PROF-1',
      doctorName: 'Dr. Saman Perera',
      doctorSpecialty: 'Cardiology',
      doctorHospital: 'Colombo General Hospital',
      appointmentId: 'APPT-1',
      consultationDate: '2026-11-10',
      followUpDate: '2026-11-25',
      followUpDateEnd: '2026-11-28',
      reason: 'Post-hypertension therapy review',
      instructions: 'Check blood pressure twice daily. Maintain low salt diet.',
      recommendedConsultationType: 'IN_PERSON',
      status: 'ACTIVE',
      version: 1,
      createdBy: 'DOC-1',
      updatedBy: 'DOC-1',
      tasks: [
        CareTask(
          taskId: 'TASK-1',
          title: 'Daily BP Measurement',
          description: 'Measure before breakfast and dinner',
          isCompleted: false,
        ),
        CareTask(
          taskId: 'TASK-2',
          title: 'Lipid Profile Test',
          description: 'Complete blood draw 2 days prior to consultation',
          isCompleted: true,
          completedAt: DateTime.parse('2026-11-12T08:00:00Z'),
        ),
      ],
      auditLog: [
        CarePlanAuditEntry(
          action: 'CREATED',
          performedBy: 'DOC-1',
          performedByRole: 'DOCTOR',
          timestamp: DateTime.parse('2026-11-10T11:00:00Z'),
          note: 'Initial care plan',
        ),
      ],
      createdAt: DateTime.parse('2026-11-10T11:00:00Z'),
      updatedAt: DateTime.parse('2026-11-10T11:00:00Z'),
    ),
    CarePlan(
      id: 'PLAN-2',
      patientUserId: 'PAT-1',
      patientName: 'Kasun Wickrama',
      doctorUserId: 'DOC-2',
      doctorProfileId: 'PROF-2',
      doctorName: 'Dr. Nirmal Senanayake',
      doctorSpecialty: 'Neurology',
      doctorHospital: 'Kandy National Hospital',
      appointmentId: 'APPT-2',
      consultationDate: '2026-10-01',
      followUpDate: '2026-10-15',
      reason: 'Post-migraine review',
      instructions: 'Review sleep journal',
      recommendedConsultationType: 'VIDEO',
      status: 'COMPLETED',
      version: 1,
      createdBy: 'DOC-2',
      updatedBy: 'DOC-2',
      tasks: [],
      auditLog: [],
      createdAt: DateTime.parse('2026-10-01T10:00:00Z'),
      updatedAt: DateTime.parse('2026-10-15T10:00:00Z'),
    ),
  ];

  bool taskToggled = false;
  bool planCreated = false;

  @override
  Future<List<CarePlan>> getPatientCarePlans({String? status}) async {
    if (status != null) {
      return patientPlans.where((p) => p.status == status).toList();
    }
    return patientPlans;
  }

  @override
  Future<CarePlan> updateTaskStatus(
    String planId,
    String taskId, {
    required bool isCompleted,
  }) async {
    taskToggled = true;
    final planIdx = patientPlans.indexWhere((p) => p.id == planId);
    if (planIdx >= 0) {
      final oldPlan = patientPlans[planIdx];
      final updatedTasks = oldPlan.tasks.map((t) {
        if (t.taskId == taskId) {
          return t.copyWith(
            isCompleted: isCompleted,
            completedAt: isCompleted ? DateTime.now() : null,
          );
        }
        return t;
      }).toList();

      final updatedPlan = oldPlan.copyWith(tasks: updatedTasks);
      patientPlans[planIdx] = updatedPlan;
      return updatedPlan;
    }
    throw Exception('Care plan not found');
  }

  @override
  Future<CarePlan> createCarePlan({
    required String appointmentId,
    required String followUpDate,
    String? followUpDateEnd,
    required String reason,
    required String instructions,
    String recommendedConsultationType = 'IN_PERSON',
    List<Map<String, dynamic>> tasks = const [],
    List<String> linkedPrescriptionIds = const [],
    List<String> linkedMedicalRecordIds = const [],
  }) async {
    planCreated = true;
    final newPlan = CarePlan(
      id: 'PLAN-NEW',
      patientUserId: 'PAT-1',
      patientName: 'Test Patient',
      doctorUserId: 'DOC-1',
      doctorProfileId: 'PROF-1',
      doctorName: 'Dr. Saman Perera',
      doctorSpecialty: 'Cardiology',
      doctorHospital: 'Colombo General',
      appointmentId: appointmentId,
      followUpDate: followUpDate,
      followUpDateEnd: followUpDateEnd,
      reason: reason,
      instructions: instructions,
      recommendedConsultationType: recommendedConsultationType,
      status: 'ACTIVE',
      createdBy: 'DOC-1',
      updatedBy: 'DOC-1',
      tasks: tasks
          .map((t) => CareTask(
                taskId: 'T-${DateTime.now().millisecondsSinceEpoch}',
                title: t['title']?.toString() ?? '',
                description: t['description']?.toString(),
              ))
          .toList(),
      auditLog: [],
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );
    patientPlans.add(newPlan);
    return newPlan;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  Widget createTestApp({required Widget child}) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>(create: (_) => AuthProvider()),
      ],
      child: MaterialApp(
        home: child,
      ),
    );
  }

  group('Patient Care Plans Screen Tests (Phase 56)', () {
    testWidgets('1. Displays active plans, doctor specialty, reason, and tabs', (tester) async {
      final mock = MockCarePlanService();
      await tester.pumpWidget(createTestApp(
        child: PatientCarePlansScreen(carePlanService: mock),
      ));
      await tester.pumpAndSettle();

      expect(find.text('My Care Plans'), findsOneWidget);
      expect(find.text('Active (1)'), findsOneWidget);
      expect(find.text('History (1)'), findsOneWidget);

      // Verify active plan details
      expect(find.text('Dr. Saman Perera'), findsOneWidget);
      expect(find.text('Cardiology'), findsOneWidget);
      expect(find.text('Post-hypertension therapy review'), findsOneWidget);
      expect(find.text('Check blood pressure twice daily. Maintain low salt diet.'), findsOneWidget);

      // Verify tasks rendered
      expect(find.text('Daily BP Measurement'), findsOneWidget);
      expect(find.text('Lipid Profile Test'), findsOneWidget);

      // Verify "Book Follow-up" button
      expect(find.text('Book Follow-up Appointment'), findsOneWidget);
    });

    testWidgets('2. Patient toggles care task checkbox', (tester) async {
      final mock = MockCarePlanService();
      await tester.pumpWidget(createTestApp(
        child: PatientCarePlansScreen(carePlanService: mock),
      ));
      await tester.pumpAndSettle();

      // Find first task checkbox key
      final taskKey = find.byKey(const Key('task_checkbox_TASK-1'));
      expect(taskKey, findsOneWidget);

      await tester.tap(taskKey);
      await tester.pumpAndSettle();

      expect(mock.taskToggled, isTrue);
    });

    testWidgets('3. Switch to History tab displays completed care plans', (tester) async {
      final mock = MockCarePlanService();
      await tester.pumpWidget(createTestApp(
        child: PatientCarePlansScreen(carePlanService: mock),
      ));
      await tester.pumpAndSettle();

      // Tap on History tab
      await tester.tap(find.text('History (1)'));
      await tester.pumpAndSettle();

      expect(find.text('Dr. Nirmal Senanayake'), findsOneWidget);
      expect(find.text('Post-migraine review'), findsOneWidget);
      expect(find.text('COMPLETED'), findsOneWidget);
    });
  });

  group('Doctor Create Care Plan Screen Tests (Phase 56)', () {
    testWidgets('4. Doctor creates care plan with tasks and validates fields', (tester) async {
      final mock = MockCarePlanService();
      final testAppt = Appointment(
        id: 'APPT-TEST-123',
        patientUserId: 'PAT-1',
        doctorUserId: 'DOC-1',
        doctorProfileId: 'PROF-1',
        availabilityId: 'AVAIL-1',
        appointmentDate: '2026-11-12',
        startTime: '09:00',
        endTime: '09:30',
        status: 'COMPLETED',
        patientName: 'Anura Kumara',
        doctorName: 'Dr. Saman Perera',
        specialty: 'Cardiology',
        hospitalOrClinic: 'Colombo General',
      );

      await tester.pumpWidget(createTestApp(
        child: CreateCarePlanScreen(
          appointment: testAppt,
          carePlanService: mock,
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Create Follow-up Plan'), findsNWidgets(2));
      expect(find.text('Anura Kumara'), findsOneWidget);

      // Enter Reason
      await tester.enterText(
        find.byKey(const Key('care_plan_reason_field')),
        'Cardiac follow-up and ECG check',
      );

      // Enter Instructions
      await tester.enterText(
        find.byKey(const Key('care_plan_instructions_field')),
        'Avoid strenuous exercise and track morning pulse.',
      );

      // Add a task
      final taskInput = find.byKey(const Key('care_plan_task_input_0'));
      expect(taskInput, findsOneWidget);
      await tester.enterText(taskInput, 'Daily Morning Pulse Log');

      // Submit plan
      final submitButton = find.byKey(const Key('submit_care_plan_button'));
      await tester.ensureVisible(submitButton);
      await tester.tap(submitButton);
      await tester.pumpAndSettle();

      expect(mock.planCreated, isTrue);
    });
  });
}
