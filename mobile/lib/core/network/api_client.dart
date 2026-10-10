import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../constants/api_constants.dart';
import '../storage/secure_storage_service.dart';
import 'api_error_mapper.dart';
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

  /// Safe debug logger for outgoing requests (never logs bodies or headers/tokens)
  void _safeLogRequest(String method, Uri uri) {
    if (kDebugMode) {
      debugPrint('[ApiClient] $method $uri');
    }
  }

  /// Safe debug logger for incoming responses (never logs response body)
  void _safeLogResponse(Uri uri, int statusCode) {
    if (kDebugMode) {
      debugPrint('[ApiClient] Response $statusCode from $uri');
    }
  }

  /// Safe debug logger for error categorizations (never logs sensitive payload)
  void _safeLogError(Uri uri, String safeCategory, [int? statusCode]) {
    if (kDebugMode) {
      if (statusCode != null) {
        debugPrint('[ApiClient] Error on $uri: HTTP $statusCode (Category: $safeCategory)');
      } else {
        debugPrint('[ApiClient] Error on $uri (Category: $safeCategory)');
      }
    }
  }

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
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    final response = await _sendWithRetryRaw(
      () => _rawGet(endpoint, headers: headers, includeAuth: includeAuth),
      endpoint: endpoint,
      includeAuth: includeAuth,
    );
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response.bodyBytes;
    }
    _processResponse(response, uri: uri);
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
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    _safeLogRequest('POST (multipart)', uri);
    try {
      final request = http.MultipartRequest('POST', uri);

      final combinedHeaders = await _buildHeaders(headers, includeAuth: includeAuth);
      combinedHeaders.remove('Content-Type');
      combinedHeaders.remove('content-type');
      request.headers.addAll(combinedHeaders);

      request.fields.addAll(fields);
      request.files.addAll(files);

      final streamedResponse = await _httpClient.send(request).timeout(
        ApiConstants.timeoutDuration,
      );

      final response = await http.Response.fromStream(streamedResponse);
      _safeLogResponse(uri, response.statusCode);
      return _processResponse(response, uri: uri);
    } on SocketException catch (e) {
      _safeLogError(uri, 'NetworkException (Socket: ${e.osError?.message ?? e.message})');
      throw const NetworkException();
    } on http.ClientException catch (e) {
      _safeLogError(uri, 'NetworkException (ClientException: ${e.message})');
      throw const NetworkException();
    } on TimeoutException {
      _safeLogError(uri, 'NetworkException (Timeout after ${ApiConstants.timeoutDuration.inSeconds}s)');
      throw const NetworkException();
    } on HttpException catch (e) {
      _safeLogError(uri, 'NetworkException (HttpException: ${e.message})');
      throw const NetworkException();
    } catch (e) {
      if (e is ApiException) {
        rethrow;
      }
      _safeLogError(uri, 'NetworkException ($e)');
      throw const NetworkException();
    }
  }

  Future<http.Response> _rawGet(
    String endpoint, {
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    _safeLogRequest('GET', uri);
    final combinedHeaders = await _buildHeaders(headers, includeAuth: includeAuth);

    return _httpClient.get(uri, headers: combinedHeaders).timeout(
      ApiConstants.timeoutDuration,
    );
  }

  Future<http.Response> _rawPost(
    String endpoint, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    _safeLogRequest('POST', uri);
    final combinedHeaders = await _buildHeaders(headers, includeAuth: includeAuth);

    return _httpClient
        .post(
          uri,
          headers: combinedHeaders,
          body: body != null ? jsonEncode(body) : null,
        )
        .timeout(ApiConstants.timeoutDuration);
  }

  Future<http.Response> _rawPut(
    String endpoint, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    _safeLogRequest('PUT', uri);
    final combinedHeaders = await _buildHeaders(headers, includeAuth: includeAuth);

    return _httpClient
        .put(
          uri,
          headers: combinedHeaders,
          body: body != null ? jsonEncode(body) : null,
        )
        .timeout(ApiConstants.timeoutDuration);
  }

  Future<http.Response> _rawDelete(
    String endpoint, {
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    _safeLogRequest('DELETE', uri);
    final combinedHeaders = await _buildHeaders(headers, includeAuth: includeAuth);

    return _httpClient
        .delete(
          uri,
          headers: combinedHeaders,
        )
        .timeout(ApiConstants.timeoutDuration);
  }

  /// Execute an HTTP request with automatic token refresh on 401
  Future<dynamic> _sendWithRetry(
    Future<http.Response> Function() requestFn, {
    required String endpoint,
    required bool includeAuth,
  }) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    try {
      final response = await requestFn();
      _safeLogResponse(uri, response.statusCode);

      // Check if 401 Unauthorized and auth was requested
      if (response.statusCode == 401 &&
          includeAuth &&
          endpoint != ApiConstants.loginEndpoint &&
          endpoint != ApiConstants.refreshEndpoint) {
        _safeLogError(uri, 'AuthSessionRefresh', 401);
        final refreshSucceeded = await _attemptTokenRefresh();
        if (refreshSucceeded) {
          // Retry the original request once with newly rotated access token
          final retryResponse = await requestFn();
          _safeLogResponse(uri, retryResponse.statusCode);
          return _processResponse(retryResponse, uri: uri);
        } else {
          await _storageService.clearTokens();
          _safeLogError(uri, 'AuthSessionExpired', 401);
          throw const AuthException(
            message: 'Your session has expired. Please sign in again.',
            statusCode: 401,
          );
        }
      }

      return _processResponse(response, uri: uri);
    } on SocketException catch (e) {
      _safeLogError(uri, 'NetworkException (Socket: ${e.osError?.message ?? e.message})');
      throw const NetworkException();
    } on http.ClientException catch (e) {
      _safeLogError(uri, 'NetworkException (ClientException: ${e.message})');
      throw const NetworkException();
    } on TimeoutException {
      _safeLogError(uri, 'NetworkException (Timeout after ${ApiConstants.timeoutDuration.inSeconds}s)');
      throw const NetworkException();
    } on HttpException catch (e) {
      _safeLogError(uri, 'NetworkException (HttpException: ${e.message})');
      throw const NetworkException();
    } catch (e) {
      if (e is ApiException) {
        rethrow;
      }
      final errLower = e.toString().toLowerCase();
      if (errLower.contains('socket') ||
          errLower.contains('connection') ||
          errLower.contains('network') ||
          errLower.contains('failed host lookup') ||
          errLower.contains('timeout') ||
          errLower.contains('xmlhttprequest') ||
          errLower.contains('clientexception') ||
          errLower.contains('failed to fetch') ||
          errLower.contains('load failed') ||
          errLower.contains('handshake') ||
          errLower.contains('tls') ||
          errLower.contains('refused') ||
          errLower.contains('unreachable') ||
          errLower.contains('cors') ||
          errLower.contains('cross-origin')) {
        _safeLogError(uri, 'NetworkException ($e)');
        throw const NetworkException();
      }
      _safeLogError(uri, 'UnexpectedException ($e)');
      rethrow;
    }
  }

  /// Execute an HTTP request with automatic token refresh on 401 returning raw http.Response
  Future<http.Response> _sendWithRetryRaw(
    Future<http.Response> Function() requestFn, {
    required String endpoint,
    required bool includeAuth,
  }) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}$endpoint');
    try {
      final response = await requestFn();
      _safeLogResponse(uri, response.statusCode);

      if (response.statusCode == 401 &&
          includeAuth &&
          endpoint != ApiConstants.loginEndpoint &&
          endpoint != ApiConstants.refreshEndpoint) {
        _safeLogError(uri, 'AuthSessionRefresh', 401);
        final refreshSucceeded = await _attemptTokenRefresh();
        if (refreshSucceeded) {
          final retryResponse = await requestFn();
          _safeLogResponse(uri, retryResponse.statusCode);
          return retryResponse;
        } else {
          await _storageService.clearTokens();
          _safeLogError(uri, 'AuthSessionExpired', 401);
          throw const AuthException(
            message: 'Your session has expired. Please sign in again.',
            statusCode: 401,
          );
        }
      }

      return response;
    } on SocketException catch (e) {
      _safeLogError(uri, 'NetworkException (Socket: ${e.osError?.message ?? e.message})');
      throw const NetworkException();
    } on http.ClientException catch (e) {
      _safeLogError(uri, 'NetworkException (ClientException: ${e.message})');
      throw const NetworkException();
    } on TimeoutException {
      _safeLogError(uri, 'NetworkException (Timeout after ${ApiConstants.timeoutDuration.inSeconds}s)');
      throw const NetworkException();
    } on HttpException catch (e) {
      _safeLogError(uri, 'NetworkException (HttpException: ${e.message})');
      throw const NetworkException();
    } catch (e) {
      if (e is ApiException) {
        rethrow;
      }
      final errLower = e.toString().toLowerCase();
      if (errLower.contains('socket') ||
          errLower.contains('connection') ||
          errLower.contains('network') ||
          errLower.contains('failed host lookup') ||
          errLower.contains('timeout') ||
          errLower.contains('xmlhttprequest') ||
          errLower.contains('clientexception') ||
          errLower.contains('failed to fetch') ||
          errLower.contains('load failed') ||
          errLower.contains('handshake') ||
          errLower.contains('tls') ||
          errLower.contains('refused') ||
          errLower.contains('unreachable') ||
          errLower.contains('cors') ||
          errLower.contains('cross-origin')) {
        _safeLogError(uri, 'NetworkException ($e)');
        throw const NetworkException();
      }
      _safeLogError(uri, 'UnexpectedException ($e)');
      rethrow;
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
  dynamic _processResponse(http.Response response, {Uri? uri}) {
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
      _safeLogError(uri ?? Uri(), 'AuthException (401)', 401);
      throw AuthException(message: message, statusCode: 401);
    }

    if (response.statusCode == 403) {
      _safeLogError(uri ?? Uri(), 'ForbiddenException (403)', 403);
      throw ApiException(
        message: message,
        statusCode: 403,
        details: decodedBody,
      );
    }

    if (response.statusCode == 409) {
      _safeLogError(uri ?? Uri(), 'ConflictException (409)', 409);
      throw ConflictException(
        message: message.isNotEmpty
            ? message
            : 'This time slot is no longer available.',
        statusCode: 409,
        details: decodedBody,
      );
    }

    if (response.statusCode == 422) {
      _safeLogError(uri ?? Uri(), 'ValidationException (422)', 422);
      throw ValidationException(
        message: message,
        statusCode: 422,
        details: decodedBody,
      );
    }

    if (response.statusCode >= 500) {
      _safeLogError(uri ?? Uri(), 'ServerException (${response.statusCode})', response.statusCode);
      throw ApiException(
        message: message,
        statusCode: response.statusCode,
        details: decodedBody,
      );
    }

    _safeLogError(uri ?? Uri(), 'ApiException (${response.statusCode})', response.statusCode);
    throw ApiException(
      message: message,
      statusCode: response.statusCode,
      details: decodedBody,
    );
  }

  /// Extracts clean user-facing error message without raw database or Python traces
  String _extractErrorMessage(dynamic body, int statusCode) {
    return ApiErrorMapper.fromResponseBody(body, statusCode);
  }

  /// Checks connectivity to the backend's existing GET /health endpoint.
  /// Useful to verify network reachability from physical devices before authentication.
  Future<bool> checkHealth() async {
    final healthUri = Uri.parse('${ApiConstants.hostBaseUrl}/health');
    _safeLogRequest('GET', healthUri);
    try {
      final response = await _httpClient.get(healthUri).timeout(
        const Duration(seconds: 5),
      );
      _safeLogResponse(healthUri, response.statusCode);
      return response.statusCode == 200;
    } on SocketException catch (e) {
      _safeLogError(healthUri, 'HealthCheckFailed (Socket: ${e.osError?.message ?? e.message})');
      return false;
    } on http.ClientException catch (e) {
      _safeLogError(healthUri, 'HealthCheckFailed (Client: ${e.message})');
      return false;
    } on TimeoutException {
      _safeLogError(healthUri, 'HealthCheckFailed (Timeout after 5s)');
      return false;
    } catch (e) {
      _safeLogError(healthUri, 'HealthCheckFailed ($e)');
      return false;
    }
  }
}
