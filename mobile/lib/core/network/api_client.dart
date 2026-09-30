import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../constants/api_constants.dart';
import '../storage/secure_storage_service.dart';
import 'api_exceptions.dart';

/// Centralized HTTP client for MediConnect.
/// Handles headers, automatic token attachment, transparent 401 refresh token rotation,
/// and converts network/HTTP errors into user-friendly exceptions.
class ApiClient {
  final http.Client _httpClient;
  final SecureStorageService _storageService;

  // Guard against concurrent refresh requests and refresh loops
  bool _isRefreshing = false;
  Completer<bool>? _refreshCompleter;

  ApiClient({
    http.Client? httpClient,
    SecureStorageService? storageService,
  })  : _httpClient = httpClient ?? http.Client(),
        _storageService = storageService ?? SecureStorageService();

  /// GET request
  Future<dynamic> get(
    String endpoint, {
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    return _sendWithRetry(
      () => _rawGet(endpoint, headers: headers, includeAuth: includeAuth),
      endpoint: endpoint,
      includeAuth: includeAuth,
    );
  }

  /// GET request returning raw response bytes (useful for secure binary document retrieval)
  Future<List<int>> getBytes(
    String endpoint, {
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    final response = await _sendWithRetryRaw(
      () => _rawGet(endpoint, headers: headers, includeAuth: includeAuth),
      endpoint: endpoint,
      includeAuth: includeAuth,
    );
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response.bodyBytes;
    }
    _processResponse(response);
    return response.bodyBytes;
  }

  /// POST request
  Future<dynamic> post(
    String endpoint, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    return _sendWithRetry(
      () => _rawPost(endpoint, body: body, headers: headers, includeAuth: includeAuth),
      endpoint: endpoint,
      includeAuth: includeAuth,
    );
  }

  /// PUT request
  Future<dynamic> put(
    String endpoint, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    return _sendWithRetry(
      () => _rawPut(endpoint, body: body, headers: headers, includeAuth: includeAuth),
      endpoint: endpoint,
      includeAuth: includeAuth,
    );
  }

  /// DELETE request
  Future<dynamic> delete(
    String endpoint, {
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    return _sendWithRetry(
      () => _rawDelete(endpoint, headers: headers, includeAuth: includeAuth),
      endpoint: endpoint,
      includeAuth: includeAuth,
    );
  }

  /// POST multipart request for file uploads
  Future<dynamic> postMultipart(
    String endpoint, {
    required Map<String, String> fields,
    required List<http.MultipartFile> files,
    Map<String, String>? headers,
    bool includeAuth = false,
  }) async {
    try {
      final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
      final request = http.MultipartRequest('POST', uri);

      final combinedHeaders = await _buildHeaders(headers, includeAuth: includeAuth);
      combinedHeaders.remove('Content-Type');
      combinedHeaders.remove('content-type');
      request.headers.addAll(combinedHeaders);

      request.fields.addAll(fields);
      request.files.addAll(files);

      final streamedResponse = await _httpClient.send(request).timeout(
        ApiConstants.timeoutDuration,
        onTimeout: () => throw const NetworkException(),
      );

      final response = await http.Response.fromStream(streamedResponse);
      return _processResponse(response);
    } on SocketException {
      throw const NetworkException();
    } on http.ClientException {
      throw const NetworkException();
    }
  }

  Future<http.Response> _rawGet(
    String endpoint, {
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    final combinedHeaders = await _buildHeaders(headers, includeAuth: includeAuth);

    return _httpClient.get(uri, headers: combinedHeaders).timeout(
      ApiConstants.timeoutDuration,
      onTimeout: () => throw const NetworkException(),
    );
  }

  Future<http.Response> _rawPost(
    String endpoint, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    final combinedHeaders = await _buildHeaders(headers, includeAuth: includeAuth);

    return _httpClient
        .post(
          uri,
          headers: combinedHeaders,
          body: body != null ? jsonEncode(body) : null,
        )
        .timeout(
          ApiConstants.timeoutDuration,
          onTimeout: () => throw const NetworkException(),
        );
  }

  Future<http.Response> _rawPut(
    String endpoint, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    final combinedHeaders = await _buildHeaders(headers, includeAuth: includeAuth);

    return _httpClient
        .put(
          uri,
          headers: combinedHeaders,
          body: body != null ? jsonEncode(body) : null,
        )
        .timeout(
          ApiConstants.timeoutDuration,
          onTimeout: () => throw const NetworkException(),
        );
  }

  Future<http.Response> _rawDelete(
    String endpoint, {
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    final combinedHeaders = await _buildHeaders(headers, includeAuth: includeAuth);

    return _httpClient
        .delete(
          uri,
          headers: combinedHeaders,
        )
        .timeout(
          ApiConstants.timeoutDuration,
          onTimeout: () => throw const NetworkException(),
        );
  }

  /// Execute an HTTP request with automatic token refresh on 401
  Future<dynamic> _sendWithRetry(
    Future<http.Response> Function() requestFn, {
    required String endpoint,
    required bool includeAuth,
  }) async {
    try {
      final response = await requestFn();

      // Check if 401 Unauthorized and auth was requested
      if (response.statusCode == 401 &&
          includeAuth &&
          endpoint != ApiConstants.loginEndpoint &&
          endpoint != ApiConstants.refreshEndpoint) {
        final refreshSucceeded = await _attemptTokenRefresh();
        if (refreshSucceeded) {
          // Retry the original request once with newly rotated access token
          final retryResponse = await requestFn();
          return _processResponse(retryResponse);
        } else {
          await _storageService.clearTokens();
          throw const AuthException(
            message: 'Your session has expired. Please sign in again.',
            statusCode: 401,
          );
        }
      }

      return _processResponse(response);
    } on SocketException {
      throw const NetworkException();
    } on http.ClientException {
      throw const NetworkException();
    } on TimeoutException {
      throw const NetworkException();
    }
  }

  /// Execute an HTTP request with automatic token refresh on 401 returning raw http.Response
  Future<http.Response> _sendWithRetryRaw(
    Future<http.Response> Function() requestFn, {
    required String endpoint,
    required bool includeAuth,
  }) async {
    try {
      final response = await requestFn();

      if (response.statusCode == 401 &&
          includeAuth &&
          endpoint != ApiConstants.loginEndpoint &&
          endpoint != ApiConstants.refreshEndpoint) {
        final refreshSucceeded = await _attemptTokenRefresh();
        if (refreshSucceeded) {
          return await requestFn();
        } else {
          await _storageService.clearTokens();
          throw const AuthException(
            message: 'Your session has expired. Please sign in again.',
            statusCode: 401,
          );
        }
      }

      return response;
    } on SocketException {
      throw const NetworkException();
    } on http.ClientException {
      throw const NetworkException();
    } on TimeoutException {
      throw const NetworkException();
    }
  }

  /// Refreshes access token using stored refresh token with mutex lock
  Future<bool> _attemptTokenRefresh() async {
    if (_isRefreshing) {
      // If refresh is already in flight, wait for its completion
      return await _refreshCompleter?.future ?? false;
    }

    _isRefreshing = true;
    _refreshCompleter = Completer<bool>();

    try {
      final storedRefreshToken = await _storageService.getRefreshToken();
      if (storedRefreshToken == null || storedRefreshToken.isEmpty) {
        _refreshCompleter?.complete(false);
        return false;
      }

      final uri = Uri.parse('${ApiConstants.baseUrl}${ApiConstants.refreshEndpoint}');
      final response = await _httpClient
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'refreshToken': storedRefreshToken}),
          )
          .timeout(ApiConstants.timeoutDuration);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final newAccessToken = data['accessToken'] as String?;
        final newRefreshToken = data['refreshToken'] as String?;

        if (newAccessToken != null && newRefreshToken != null) {
          await _storageService.saveTokens(
            accessToken: newAccessToken,
            refreshToken: newRefreshToken,
          );
          _refreshCompleter?.complete(true);
          return true;
        }
      }

      _refreshCompleter?.complete(false);
      return false;
    } catch (_) {
      _refreshCompleter?.complete(false);
      return false;
    } finally {
      _isRefreshing = false;
    }
  }

  /// Merges standard headers, JSON content type, and Bearer token if present
  Future<Map<String, String>> _buildHeaders(
    Map<String, String>? customHeaders, {
    required bool includeAuth,
  }) async {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };

    if (customHeaders != null) {
      headers.addAll(customHeaders);
    }

    if (includeAuth) {
      final token = await _storageService.getAccessToken();
      if (token != null && token.isNotEmpty) {
        headers['Authorization'] = 'Bearer $token';
      }
    }

    return headers;
  }

  /// Parses HTTP response, extracts JSON payload, or throws structured ApiException
  dynamic _processResponse(http.Response response) {
    dynamic decodedBody;
    if (response.body.isNotEmpty) {
      try {
        decodedBody = jsonDecode(response.body);
      } catch (_) {
        decodedBody = null;
      }
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return decodedBody;
    }

    final message = _extractErrorMessage(decodedBody, response.statusCode);

    if (response.statusCode == 401) {
      throw AuthException(message: message, statusCode: 401);
    }

    if (response.statusCode == 422) {
      throw ValidationException(
        message: message,
        statusCode: 422,
        details: decodedBody,
      );
    }

    if (response.statusCode >= 500) {
      throw const ApiException(
        message: 'A server error occurred. Please try again later.',
        statusCode: 500,
      );
    }

    throw ApiException(
      message: message,
      statusCode: response.statusCode,
      details: decodedBody,
    );
  }

  /// Extracts clean user-facing error message without raw database or Python traces
  String _extractErrorMessage(dynamic body, int statusCode) {
    if (body is Map<String, dynamic>) {
      if (body['detail'] != null) {
        final detail = body['detail'];
        if (detail is String) {
          return detail;
        }
        if (detail is List && detail.isNotEmpty) {
          final first = detail.first;
          if (first is Map && first['msg'] != null) {
            return first['msg'].toString();
          }
        }
      }
      if (body['message'] != null && body['message'] is String) {
        return body['message'] as String;
      }
    }

    switch (statusCode) {
      case 400:
        return 'Invalid request. Please check your information.';
      case 401:
        return 'Invalid email or password.';
      case 403:
        return 'Access denied. You do not have permission to perform this action.';
      case 404:
        return 'The requested resource was not found.';
      case 409:
        return 'An account with this email already exists.';
      case 429:
        return 'Too many requests. Please wait a moment before trying again.';
      default:
        return 'An unexpected error occurred. Please try again.';
    }
  }
}
