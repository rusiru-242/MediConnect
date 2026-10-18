// Models for Health & Wellness Content Management and Patient Feed (Phase 24).

class HealthArticle {
  final String id;
  final String contentId;
  final String title;
  final String summary;
  final String body;
  final String category;
  final String? coverImage;
  final List<String> tags;
  final String? sources;
  final String? authorAdminId;
  final String authorName;
  final String status;
  final int readingTimeMinutes;
  final DateTime createdAt;
  final DateTime? updatedAt;
  final DateTime? publishedAt;
  final bool isBookmarked;

  const HealthArticle({
    required this.id,
    required this.contentId,
    required this.title,
    required this.summary,
    this.body = '',
    required this.category,
    this.coverImage,
    this.tags = const [],
    this.sources,
    this.authorAdminId,
    this.authorName = 'MediConnect Team',
    this.status = 'PUBLISHED',
    this.readingTimeMinutes = 1,
    required this.createdAt,
    this.updatedAt,
    this.publishedAt,
    this.isBookmarked = false,
  });

  factory HealthArticle.fromJson(Map<String, dynamic> json) {
    return HealthArticle(
      id: (json['id'] ?? json['_id'] ?? '').toString(),
      contentId: (json['contentId'] ?? '').toString(),
      title: (json['title'] ?? '').toString(),
      summary: (json['summary'] ?? '').toString(),
      body: (json['body'] ?? '').toString(),
      category: (json['category'] ?? 'General Health Tips').toString(),
      coverImage: json['coverImage']?.toString(),
      tags: (json['tags'] as List<dynamic>?)?.map((t) => t.toString()).toList() ?? const [],
      sources: json['sources']?.toString(),
      authorAdminId: json['authorAdminId']?.toString(),
      authorName: (json['authorName'] ?? 'MediConnect Team').toString(),
      status: (json['status'] ?? 'DRAFT').toString().toUpperCase(),
      readingTimeMinutes: (json['readingTimeMinutes'] as num?)?.toInt() ?? 1,
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now()
          : DateTime.now(),
      updatedAt: json['updatedAt'] != null
          ? DateTime.tryParse(json['updatedAt'].toString())
          : null,
      publishedAt: json['publishedAt'] != null
          ? DateTime.tryParse(json['publishedAt'].toString())
          : null,
      isBookmarked: json['isBookmarked'] == true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'contentId': contentId,
      'title': title,
      'summary': summary,
      'body': body,
      'category': category,
      if (coverImage != null) 'coverImage': coverImage,
      'tags': tags,
      if (sources != null) 'sources': sources,
      if (authorAdminId != null) 'authorAdminId': authorAdminId,
      'authorName': authorName,
      'status': status,
      'readingTimeMinutes': readingTimeMinutes,
      'createdAt': createdAt.toIso8601String(),
      if (updatedAt != null) 'updatedAt': updatedAt!.toIso8601String(),
      if (publishedAt != null) 'publishedAt': publishedAt!.toIso8601String(),
      'isBookmarked': isBookmarked,
    };
  }

  HealthArticle copyWith({
    String? id,
    String? contentId,
    String? title,
    String? summary,
    String? body,
    String? category,
    String? coverImage,
    List<String>? tags,
    String? sources,
    String? authorAdminId,
    String? authorName,
    String? status,
    int? readingTimeMinutes,
    DateTime? createdAt,
    DateTime? updatedAt,
    DateTime? publishedAt,
    bool? isBookmarked,
  }) {
    return HealthArticle(
      id: id ?? this.id,
      contentId: contentId ?? this.contentId,
      title: title ?? this.title,
      summary: summary ?? this.summary,
      body: body ?? this.body,
      category: category ?? this.category,
      coverImage: coverImage ?? this.coverImage,
      tags: tags ?? this.tags,
      sources: sources ?? this.sources,
      authorAdminId: authorAdminId ?? this.authorAdminId,
      authorName: authorName ?? this.authorName,
      status: status ?? this.status,
      readingTimeMinutes: readingTimeMinutes ?? this.readingTimeMinutes,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      publishedAt: publishedAt ?? this.publishedAt,
      isBookmarked: isBookmarked ?? this.isBookmarked,
    );
  }
}

class HealthCategory {
  final String category;
  final int count;

  const HealthCategory({
    required this.category,
    required this.count,
  });

  factory HealthCategory.fromJson(Map<String, dynamic> json) {
    return HealthCategory(
      category: (json['category'] ?? '').toString(),
      count: (json['count'] as num?)?.toInt() ?? 0,
    );
  }
}

class HealthContentListResponse {
  final List<HealthArticle> items;
  final int total;
  final int page;
  final int pageSize;
  final int totalPages;
  final List<HealthCategory> categories;

  const HealthContentListResponse({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.totalPages,
    this.categories = const [],
  });

  factory HealthContentListResponse.fromJson(Map<String, dynamic> json) {
    return HealthContentListResponse(
      items: (json['items'] as List<dynamic>?)
              ?.map((item) => HealthArticle.fromJson(item as Map<String, dynamic>))
              .toList() ??
          const [],
      total: (json['total'] as num?)?.toInt() ?? 0,
      page: (json['page'] as num?)?.toInt() ?? 1,
      pageSize: (json['pageSize'] as num?)?.toInt() ?? 10,
      totalPages: (json['totalPages'] as num?)?.toInt() ?? 1,
      categories: (json['categories'] as List<dynamic>?)
              ?.map((c) => HealthCategory.fromJson(c as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}
