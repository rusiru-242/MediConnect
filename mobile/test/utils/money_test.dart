// BUG-008 / BUG-028: fees are parsed from numbers or numeric strings and never defaulted.
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/doctor.dart';
import 'package:mediconnect/models/health_chat.dart';
import 'package:mediconnect/utils/money.dart';

void main() {
  test('parseAmount accepts numbers and numeric strings only', () {
    expect(parseAmount(2500), 2500.0);
    expect(parseAmount('3,500'), 3500.0);
    expect(parseAmount('LKR 2800'), 2800.0);
    expect(parseAmount(null), isNull);
    expect(parseAmount('call clinic'), isNull);
    expect(parseAmount(-1), isNull);
    expect(formatFee(null), 'Fee not listed');
  });

  test('Doctor without a listed fee is flagged instead of defaulting to LKR 2500', () {
    final missing = Doctor.fromJson({'doctorId': 'D1', 'fullName': 'Dr A', 'specialty': 'Cardiology'});
    expect(missing.hasConsultationFee, isFalse);
    final stringFee = Doctor.fromJson({'doctorId': 'D2', 'fullName': 'Dr B', 'consultationFee': '3,000'});
    expect(stringFee.hasConsultationFee, isTrue);
    expect(stringFee.consultationFee, 3000.0);
  });

  test('Referral card never invents a fee or a rating', () {
    final card = DoctorReferralCard.fromJson({'doctorId': 'D1', 'fullName': 'Dr A'});
    expect(card.consultationFee, isNull);
    expect(card.rating, isNull);
  });
}
