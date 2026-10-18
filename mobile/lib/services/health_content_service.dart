import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/health_content.dart';

/// Service interfacing with the Health & Wellness Content API (Phase 24).
class HealthContentService {
  final ApiClient _apiClient;

  HealthContentService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  /// Retrieve published articles for the patient health feed with search and category filters.
  Future<HealthContentListResponse> fetchPublishedArticles({
    String? category,
    String? search,
    int page = 1,
    int pageSize = 10,
  }) async {
    final queryParams = <String>[
      'page=$page',
      'pageSize=$pageSize',
    ];
    if (category != null && category.trim().isNotEmpty && category != 'All') {
      queryParams.add('category=${Uri.encodeComponent(category.trim())}');
    }
    if (search != null && search.trim().isNotEmpty) {
      queryParams.add('search=${Uri.encodeComponent(search.trim())}');
    }

    final endpoint = '${ApiConstants.healthContentEndpoint}?${queryParams.join('&')}';
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return HealthContentListResponse.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching published health articles.');
  }

  /// Retrieve full article details by contentId or mongoId.
  Future<HealthArticle> fetchArticleDetail(String identifier) async {
    final endpoint = ApiConstants.healthContentDetailEndpoint(identifier);
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return HealthArticle.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching article details.');
  }

  /// Retrieve health topic categories and published article counts.
  Future<List<HealthCategory>> fetchCategories() async {
    final response = await _apiClient.get(
      ApiConstants.healthContentCategoriesEndpoint,
      includeAuth: false,
    );

    if (response is List<dynamic>) {
      return response
          .map((c) => HealthCategory.fromJson(c as Map<String, dynamic>))
          .toList();
    }
    throw Exception('Unexpected response format when fetching health content categories.');
  }

  /// Retrieve the patient's bookmarked articles.
  Future<HealthContentListResponse> fetchBookmarks({
    int page = 1,
    int pageSize = 10,
  }) async {
    final endpoint = '${ApiConstants.healthContentBookmarksEndpoint}?page=$page&pageSize=$pageSize';
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return HealthContentListResponse.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching bookmarked articles.');
  }

  /// Toggle bookmark for an article (adds if not bookmarked, removes if already bookmarked).
  Future<bool> toggleBookmark(String identifier) async {
    final endpoint = ApiConstants.healthContentBookmarkToggleEndpoint(identifier);
    final response = await _apiClient.post(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return response['isBookmarked'] == true;
    }
    return false;
  }

  // --------------------------------------------------------------------------
  // Admin Operations
  // --------------------------------------------------------------------------

  /// Admin: List articles across all statuses (DRAFT, PUBLISHED, ARCHIVED).
  Future<HealthContentListResponse> fetchAdminArticles({
    String? status,
    String? category,
    String? search,
    int page = 1,
    int pageSize = 10,
  }) async {
    final queryParams = <String>[
      'page=$page',
      'pageSize=$pageSize',
    ];
    if (status != null && status.trim().isNotEmpty && status != 'ALL') {
      queryParams.add('status=${Uri.encodeComponent(status.trim().toUpperCase())}');
    }
    if (category != null && category.trim().isNotEmpty && category != 'All') {
      queryParams.add('category=${Uri.encodeComponent(category.trim())}');
    }
    if (search != null && search.trim().isNotEmpty) {
      queryParams.add('search=${Uri.encodeComponent(search.trim())}');
    }

    final endpoint = '${ApiConstants.adminHealthContentEndpoint}?${queryParams.join('&')}';
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return HealthContentListResponse.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching admin health articles.');
  }

  /// Admin: Fetch draft, published, or archived article details for editor/preview.
  Future<HealthArticle> fetchAdminArticleDetail(String identifier) async {
    final endpoint = ApiConstants.adminHealthContentDetailEndpoint(identifier);
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return HealthArticle.fromJson(response);
    }
    throw Exception('Unexpected response format when previewing admin article.');
  }

  /// Admin: Create a new health article draft or published piece.
  Future<HealthArticle> createArticle({
    required String title,
    required String summary,
    required String body,
    required String category,
    String? coverImage,
    List<String> tags = const [],
    String? sources,
    String status = 'DRAFT',
  }) async {
    final payload = {
      'title': title.trim(),
      'summary': summary.trim(),
      'body': body.trim(),
      'category': category.trim(),
      if (coverImage != null && coverImage.trim().isNotEmpty) 'coverImage': coverImage.trim(),
      'tags': tags,
      if (sources != null && sources.trim().isNotEmpty) 'sources': sources.trim(),
      'status': status.toUpperCase(),
    };

    final response = await _apiClient.post(
      ApiConstants.adminHealthContentEndpoint,
      body: payload,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return HealthArticle.fromJson(response);
    }
    throw Exception('Unexpected response format when creating health article.');
  }

  /// Admin: Update an existing health article.
  Future<HealthArticle> updateArticle(
    String identifier,
    Map<String, dynamic> updateData,
  ) async {
    final endpoint = ApiConstants.adminHealthContentDetailEndpoint(identifier);
    final response = await _apiClient.patch(
      endpoint,
      body: updateData,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return HealthArticle.fromJson(response);
    }
    throw Exception('Unexpected response format when updating health article.');
  }

  /// Admin: Publish article.
  Future<HealthArticle> publishArticle(String identifier) async {
    final endpoint = ApiConstants.adminHealthContentPublishEndpoint(identifier);
    final response = await _apiClient.post(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return HealthArticle.fromJson(response);
    }
    throw Exception('Unexpected response format when publishing health article.');
  }

  /// Admin: Archive article.
  Future<HealthArticle> archiveArticle(String identifier) async {
    final endpoint = ApiConstants.adminHealthContentArchiveEndpoint(identifier);
    final response = await _apiClient.post(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return HealthArticle.fromJson(response);
    }
    throw Exception('Unexpected response format when archiving health article.');
  }
}
