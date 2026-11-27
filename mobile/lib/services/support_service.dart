import '../core/network/api_client.dart';
import '../models/support_ticket.dart';

/// A05 (Agent 26): the requester's support tickets. Identity comes from the signed-in session on the backend.
class SupportService {
  final ApiClient _client;

  SupportService({ApiClient? client}) : _client = client ?? ApiClient();

  Future<List<SupportTicket>> myTickets() async {
    final response = await _client.get('/admin/workflow/tickets?page=1&pageSize=50', includeAuth: true);
    final items = response is Map ? response['items'] : null;
    if (items is! List) return [];
    return items.whereType<Map>().map((e) => SupportTicket.fromJson(Map<String, dynamic>.from(e))).toList();
  }

  Future<SupportTicket> ticket(String ticketId) async {
    final response = await _client.get('/admin/workflow/tickets/${Uri.encodeComponent(ticketId)}', includeAuth: true);
    return SupportTicket.fromJson(Map<String, dynamic>.from(response as Map));
  }

  Future<SupportTicket> create({required String category, required String subject, required String message}) async {
    final response = await _client.post('/admin/workflow/tickets',
        body: {'category': category, 'subject': subject, 'description': message}, includeAuth: true);
    return SupportTicket.fromJson(Map<String, dynamic>.from(response as Map));
  }

  Future<SupportTicket> reply(String ticketId, String message) async {
    final response = await _client.post('/admin/workflow/tickets/${Uri.encodeComponent(ticketId)}/messages',
        body: {'message': message}, includeAuth: true);
    return SupportTicket.fromJson(Map<String, dynamic>.from(response as Map));
  }
}
