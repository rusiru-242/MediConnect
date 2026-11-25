// Phase 03 doctor UI regression tests (P03-N01, N16, N18 and the truthful "Today" panel).
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/network/api_client.dart';
import 'package:mediconnect/core/theme/app_theme.dart';
import 'package:mediconnect/models/appointment.dart';
import 'package:mediconnect/models/auth_session.dart';
import 'package:mediconnect/models/consultation.dart';
import 'package:mediconnect/models/doctor_application_status.dart';
import 'package:mediconnect/models/user_model.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/providers/locale_provider.dart';
import 'package:mediconnect/providers/notification_provider.dart';
import 'package:mediconnect/providers/theme_provider.dart';
import 'package:mediconnect/screens/doctor/consultation_details_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_home_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_schedule_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_workflow_screen.dart';
import 'package:mediconnect/services/auth_api_service.dart';
import 'package:mediconnect/services/consultation_service.dart';
import 'package:mediconnect/widgets/doctor_today_overview.dart';
import 'package:provider/provider.dart';

class _NoStatusAuth extends AuthApiService {
  @override
  Future<DoctorApplicationStatus> getDoctorApplicationStatus() async => throw Exception('offline');
}

class _Schedule extends ConsultationService {
  _Schedule(this.schedule);
  final DoctorDailySchedule schedule;
  int starts = 0;

  @override
  Future<DoctorDailySchedule> getTodaySchedule() async => schedule;

  @override
  Future<DoctorDailySchedule> getScheduleByDate(String date) async => schedule;

  @override
  Future<DailyScheduleStats> getScheduleSummary([String? date]) async => schedule.stats;

  @override
  Future<ConsultationDetail> getConsultationDetails(String appointmentId) async =>
      ConsultationDetail(appointment: schedule.appointments.firstWhere((a) => a.appointmentId == appointmentId));

  @override
  Future<ConsultationSession> startConsultation(String appointmentId, {String? notes}) async {
    starts++;
    throw Exception('not expected');
  }
}

class _FollowUpClient extends ApiClient {
  @override
  Future<dynamic> get(String endpoint, {Map<String, String>? headers, bool includeAuth = true}) async =>
      {'appointments': []};

  @override
  Future<dynamic> post(String endpoint,
      {Map<String, dynamic>? body, Map<String, String>? headers, bool includeAuth = true}) async {
    return {
      'message': '2 recent follow-up plans.',
      'tool': 'get_my_follow_up_tasks',
      'result': {
        'followUps': [
          {'id': 'CP1', 'appointmentId': 'A1', 'followUpDate': '2026-12-09', 'status': 'ACTIVE',
           'completedTasks': 1, 'totalTasks': 2, 'progressPercentage': 50},
          {'id': 'CP2', 'appointmentId': 'A2', 'followUpDate': '2026-12-10', 'status': 'ACTIVE',
           'completedTasks': 0, 'totalTasks': 0, 'progressPercentage': null},
        ],
      },
    };
  }
}

Appointment _appt(String id, {String status = 'CONFIRMED', String payment = 'PAID', double? paid = 2000}) =>
    Appointment.fromJson({
      'id': id, 'patientUserId': 'P1', 'doctorUserId': 'D1', 'doctorProfileId': 'DP1', 'availabilityId': 'A1',
      'appointmentDate': '2026-12-02', 'startTime': '09:00', 'endTime': '09:30', 'status': status,
      'paymentStatus': payment, 'consultationFee': 2000, 'consultationFeeAtBooking': 2000, 'amountPaid': paid,
      'currency': 'lkr', 'visitType': 'IN_PERSON',
    });

ScheduleAppointmentItem _item(String id, String booking) => ScheduleAppointmentItem(
      appointmentId: id, appointmentDate: '2026-11-25', startTime: '21:00', endTime: '21:30',
      bookingStatus: booking, consultationStatus: 'NOT_STARTED', patientUserId: 'PAT-$id',
      patientName: 'Patient $id', consultationFee: 2000.0,
    );

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  testWidgets('P03-N16 doctor home shows no invented specialty, status, duty toggle or build labels', (tester) async {
    tester.view.physicalSize = const Size(360, 780);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });
    final auth = AuthProvider(authApiService: _NoStatusAuth());
    auth.setSessionForTesting(const AuthSession(
      message: 'ok', accessToken: 't', refreshToken: 'r', expiresIn: 3600,
      user: UserModel(id: 'D1', fullName: 'Dr. P03 Alpha', email: 'doctor@uat.mediconnect.lk', role: 'DOCTOR',
          emailVerified: true, accountStatus: 'ACTIVE', authProviders: ['LOCAL']),
    ));
    await tester.pumpWidget(MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>.value(value: auth),
        ChangeNotifierProvider<ThemeProvider>(create: (_) => ThemeProvider()),
        ChangeNotifierProvider<LocaleProvider>(create: (_) => LocaleProvider()),
        ChangeNotifierProvider<NotificationProvider>(create: (_) => NotificationProvider()),
      ],
      child: MaterialApp(home: DoctorHomeScreen(todayAppointmentsLoader: (_) async => <Appointment>[])),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Dr. P03 Alpha'), findsOneWidget);
    for (final invented in ['Cardiology Specialist', 'On Duty', 'Off Duty', 'Phase 57', 'Phase 21',
      'VERIFIED & ACTIVE', 'TELEMETRY', 'National Hospital Center']) {
      expect(find.textContaining(invented), findsNothing, reason: invented);
    }
    // P03-N23: the prescription renewal queue is reachable from the doctor home.
    await tester.scrollUntilVisible(find.byKey(const Key('doctor_renewals_card')), 300);
    expect(find.byKey(const Key('doctor_renewals_card')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Today panel counts confirmed visits only and labels unpaid requests and gross payments', (tester) async {
    await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme, home: Scaffold(body: DoctorTodayOverview(
      loader: (_) async => [
        _appt('A'), _appt('B', status: 'COMPLETED'),
        _appt('C', status: 'PENDING', payment: 'UNPAID', paid: null), _appt('D', status: 'CANCELLED'),
      ],
    ))));
    await tester.pumpAndSettle();
    expect(tester.widget<Text>(find.byKey(const Key('doctor_today_appointments'))).data, '2');
    expect(find.text('1 awaiting payment'), findsOneWidget);
    expect(find.text("Paid for today's visits"), findsOneWidget);
    expect(tester.widget<Text>(find.byKey(const Key('doctor_today_paid_total'))).data, 'LKR 4,000');
  });

  testWidgets('Empty and failed Today panel states are truthful', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: DoctorTodayOverview(loader: (_) async => <Appointment>[]))));
    await tester.pumpAndSettle();
    expect(tester.widget<Text>(find.byKey(const Key('doctor_today_appointments'))).data, '0');
    expect(tester.widget<Text>(find.byKey(const Key('doctor_today_paid_total'))).data, 'LKR 0');
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: DoctorTodayOverview(
        key: const Key('failing'), loader: (_) async => throw Exception('401 expired')))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('doctor_today_error')), findsOneWidget);
  });

  testWidgets('P03-N01 unconfirmed requests show no Start button; confirmed visits do', (tester) async {
    final pending = _item('P1', 'PENDING');
    final confirmed = _item('C1', 'CONFIRMED');
    final service = _Schedule(DoctorDailySchedule(
      date: '2026-11-25', timezone: 'Asia/Colombo',
      stats: const DailyScheduleStats(date: '2026-11-25', timezone: 'Asia/Colombo', totalScheduled: 2, upcoming: 2,
          waiting: 0, inProgress: 0, completed: 0, cancelled: 0),
      nextPatient: confirmed, appointments: [pending, confirmed],
    ));
    await tester.pumpWidget(MultiProvider(
      providers: [ChangeNotifierProvider<AuthProvider>(create: (_) => AuthProvider())],
      child: MaterialApp(home: DoctorScheduleScreen(consultationService: service)),
    ));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('start_consultation_button_P1')), findsNothing);
    expect(find.byKey(const Key('awaiting_confirmation_label')), findsOneWidget);
    expect(find.byKey(const Key('start_consultation_button_C1')), findsOneWidget);
    expect(service.starts, 0);
  });

  testWidgets('P03-N18 doctor follow-ups show server-side task progress', (tester) async {
    await tester.pumpWidget(MaterialApp(home: DoctorWorkflowScreen(apiClient: _FollowUpClient())));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Follow-ups'));
    await tester.pumpAndSettle();
    expect(find.text('ACTIVE · 1/2 tasks completed'), findsOneWidget);
    expect(find.text('ACTIVE · No care tasks'), findsOneWidget);
    expect(find.textContaining('100%'), findsNothing);
  });

  testWidgets('P03-N23 SOAP notes open from a confirmed visit; an unpaid request cannot start', (tester) async {
    final service = _Schedule(DoctorDailySchedule(
      date: '2026-11-25', timezone: 'Asia/Colombo',
      stats: const DailyScheduleStats(date: '2026-11-25', timezone: 'Asia/Colombo', totalScheduled: 2, upcoming: 2,
          waiting: 0, inProgress: 0, completed: 0, cancelled: 0),
      nextPatient: null, appointments: [_item('C1', 'CONFIRMED'), _item('P1', 'PENDING')],
    ));
    Future<void> open(String id) async {
      await tester.pumpWidget(MultiProvider(
        providers: [ChangeNotifierProvider<AuthProvider>(create: (_) => AuthProvider())],
        child: MaterialApp(home: ConsultationDetailsScreen(key: Key(id), appointmentId: id, consultationService: service)),
      ));
      await tester.pumpAndSettle();
    }
    await open('C1');
    expect(find.byKey(const Key('open_clinical_notes')), findsOneWidget);
    expect(find.byKey(const Key('details_start_consultation_button')), findsOneWidget);
    await open('P1');
    expect(find.byKey(const Key('open_clinical_notes')), findsNothing);
    expect(find.byKey(const Key('details_awaiting_confirmation')), findsOneWidget);
    expect(find.byKey(const Key('details_start_consultation_button')), findsNothing);
  });
}
