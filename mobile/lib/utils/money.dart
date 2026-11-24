/// Parses an amount sent by the API as a number or numeric string ("3,500", "LKR 2500").
///
/// Returns null when the value is missing or not numeric. Callers must show "Fee not listed"
/// rather than inventing a default amount (BUG-008 / BUG-028).
double? parseAmount(dynamic value) {
  if (value is num) return value >= 0 ? value.toDouble() : null;
  if (value is String) {
    final cleaned = value.toLowerCase().replaceAll(RegExp(r'lkr|rs\.?|,|\s'), '');
    final parsed = double.tryParse(cleaned);
    return parsed != null && parsed >= 0 ? parsed : null;
  }
  return null;
}

/// Formats a fee for display, or a truthful "not listed" label when it is unknown.
String formatFee(double? amount, {String prefix = 'LKR', int decimals = 0}) {
  if (amount == null) return 'Fee not listed';
  return '$prefix ${amount.toStringAsFixed(decimals)}';
}
