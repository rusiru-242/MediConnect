/// A05 (Agent 26): a customer support ticket as the requester sees it.
///
/// The backend never sends the internal triage draft to a requester, so this model has no draft field.
class SupportMessage {
  final String messageId;
  final String senderRole;
  final String senderName;
  final String message;
  final DateTime? sentAt;

  const SupportMessage({
    required this.messageId,
    required this.senderRole,
    required this.senderName,
    required this.message,
    this.sentAt,
  });

  bool get fromSupport => senderRole == 'ADMIN' || senderRole == 'SYSTEM';

  factory SupportMessage.fromJson(Map<String, dynamic> json) => SupportMessage(
        messageId: (json['messageId'] ?? '').toString(),
        senderRole: (json['senderRole'] ?? '').toString(),
        senderName: (json['senderName'] ?? '').toString(),
        message: (json['message'] ?? '').toString(),
        sentAt: DateTime.tryParse((json['sentAt'] ?? '').toString())?.toLocal(),
      );
}

class SupportTicket {
  final String ticketId;
  final String subject;
  final String category;
  final String status;
  final String? safetyNotice;
  final String? awaitingReplyFrom;
  final List<SupportMessage> messages;
  final DateTime? updatedAt;

  const SupportTicket({
    required this.ticketId,
    required this.subject,
    required this.category,
    required this.status,
    this.safetyNotice,
    this.awaitingReplyFrom,
    this.messages = const [],
    this.updatedAt,
  });

  bool get isClosed => status == 'closed';
  bool get supportReplied => awaitingReplyFrom == 'requester';

  factory SupportTicket.fromJson(Map<String, dynamic> json) => SupportTicket(
        ticketId: (json['ticketId'] ?? '').toString(),
        subject: (json['subject'] ?? '').toString(),
        category: (json['category'] ?? 'general_support').toString(),
        status: (json['status'] ?? 'open').toString(),
        safetyNotice: json['safetyNotice'] as String?,
        awaitingReplyFrom: json['awaitingReplyFrom'] as String?,
        messages: (json['messages'] as List? ?? const [])
            .whereType<Map>()
            .map((m) => SupportMessage.fromJson(Map<String, dynamic>.from(m)))
            .toList(),
        updatedAt: DateTime.tryParse((json['updatedAt'] ?? '').toString())?.toLocal(),
      );
}

/// Categories defined by the backend (`TicketCategory`); doctor verification is for doctors and is not offered here.
const supportCategories = <String, String>{
  'appointment_issue': 'Appointment help',
  'payment_issue': 'Payment help',
  'refund_request': 'Refund question',
  'account_access': 'Account and sign-in',
  'notification_issue': 'Notifications and reminders',
  'general_support': 'General or technical issue',
};

String supportCategoryLabel(String value) => supportCategories[value] ?? value.replaceAll('_', ' ');

String supportStatusLabel(String value) => const {
      'open': 'Open',
      'in_progress': 'In progress',
      'waiting_for_user': 'Support replied',
      'resolved': 'Resolved',
      'closed': 'Closed',
    }[value] ??
    value;
