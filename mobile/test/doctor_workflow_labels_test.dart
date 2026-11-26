import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/screens/doctor/doctor_workflow_screen.dart';

void main() {
  test('P3-B7: analytics fields are shown with readable labels, never raw keys', () {
    expect(fieldLabel('bookedFees'), 'Booked consultation fees');
    expect(fieldLabel('netCollected'), 'Net collected');
    expect(fieldLabel('someNewMetricCount'), 'Some new metric count');
    expect(fieldLabel('snake_case_key'), 'Snake case key');
  });

  test('P3-B7: internal account identifiers are hidden', () {
    expect(isInternalField('patientUserId'), isTrue);
    expect(isInternalField('doctorProfileId'), isTrue);
    expect(isInternalField('id'), isTrue);
    expect(isInternalField('status'), isFalse);
  });

  test('P3-B8: shared preparation sections have labels', () {
    expect(sourceSectionLabel('recordedAllergies'), 'Recorded allergies');
    expect(sourceSectionLabel('activePrescriptions'), 'Active prescriptions (all clinicians)');
    expect(sourceSectionLabel('recentMeasurements'), 'Recent measurements');
  });
}
