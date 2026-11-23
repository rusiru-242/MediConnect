import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/analytics_data.dart';
import 'package:mediconnect/models/health_content.dart';

void main() {
  group('HealthArticle model tests', () {
    test('parses full article json correctly', () {
      final json = {
        'id': 'mongo_art_1',
        'contentId': 'CNT-20261018-001',
        'title': 'The Power of a Balanced Plate',
        'summary': 'Educational guide about macronutrients and daily vitality.',
        'body': 'Eating well requires variety, balance, and moderation.',
        'category': 'Healthy Food',
        'coverImage': 'https://example.com/food.jpg',
        'tags': ['nutrition', 'healthy eating'],
        'sources': 'WHO Dietary Guidelines',
        'authorAdminId': 'admin_1',
        'authorName': 'MediConnect Editorial Team',
        'status': 'PUBLISHED',
        'readingTimeMinutes': 3,
        'createdAt': '2026-10-18T10:00:00.000Z',
        'publishedAt': '2026-10-18T10:05:00.000Z',
        'isBookmarked': true,
      };

      final article = HealthArticle.fromJson(json);

      expect(article.id, 'mongo_art_1');
      expect(article.contentId, 'CNT-20261018-001');
      expect(article.title, 'The Power of a Balanced Plate');
      expect(article.summary, 'Educational guide about macronutrients and daily vitality.');
      expect(article.category, 'Healthy Food');
      expect(article.coverImage, 'https://example.com/food.jpg');
      expect(article.tags, contains('nutrition'));
      expect(article.sources, 'WHO Dietary Guidelines');
      expect(article.authorName, 'MediConnect Editorial Team');
      expect(article.status, 'PUBLISHED');
      expect(article.readingTimeMinutes, 3);
      expect(article.isBookmarked, isTrue);
    });

    test('supports copyWith for toggling bookmarks and status', () {
      final article = HealthArticle(
        id: '1',
        contentId: 'CNT-001',
        title: 'Safe Physical Movement',
        summary: 'Daily exercise habits.',
        category: 'Exercise',
        createdAt: DateTime.now(),
        isBookmarked: false,
      );

      final bookmarked = article.copyWith(isBookmarked: true);
      expect(bookmarked.isBookmarked, isTrue);
      expect(bookmarked.title, 'Safe Physical Movement');

      final archived = article.copyWith(status: 'ARCHIVED');
      expect(archived.status, 'ARCHIVED');
    });

    test('serializes to JSON format', () {
      final article = HealthArticle(
        id: '1',
        contentId: 'CNT-001',
        title: 'Title',
        summary: 'Summary',
        category: 'Nutrition',
        createdAt: DateTime(2026, 10, 18),
        isBookmarked: false,
      );

      final json = article.toJson();
      expect(json['contentId'], 'CNT-001');
      expect(json['category'], 'Nutrition');
      expect(json['isBookmarked'], isFalse);
    });
  });

  group('HealthCategory model tests', () {
    test('parses category count item correctly', () {
      final json = {
        'category': 'Mental Wellness',
        'count': 12,
      };

      final cat = HealthCategory.fromJson(json);
      expect(cat.category, 'Mental Wellness');
      expect(cat.count, 12);
    });
  });

  group('Analytics models tests', () {
    test('parses CurrencyRevenueData correctly with net revenue', () {
      final json = {
        'currency': 'lkr',
        'grossAmount': 10000.0,
        'refundedAmount': 2500.0,
        'netAmount': 7500.0,
        'paymentCount': 4,
      };

      final rev = CurrencyRevenueData.fromJson(json);
      expect(rev.currency, 'LKR');
      expect(rev.grossAmount, 10000.0);
      expect(rev.refundedAmount, 2500.0);
      expect(rev.netAmount, 7500.0);
      expect(rev.paymentCount, 4);
    });

    test('parses AnalyticsOverviewData correctly', () {
      final json = {
        'totalPatients': 45,
        'totalVerifiedDoctors': 12,
        'pendingDoctorApprovals': 3,
        'rejectedDoctorApplications': 1,
        'totalAppointments': 60,
        'confirmedAppointments': 20,
        'completedAppointments': 35,
        'cancelledAppointments': 5,
        'pendingAppointments': 0,
        'totalRevenueByCurrency': [
          {
            'currency': 'lkr',
            'grossAmount': 50000.0,
            'refundedAmount': 5000.0,
            'netAmount': 45000.0,
            'paymentCount': 15,
          }
        ],
        'successfulPaymentsCount': 15,
        'testPaymentsCount': 15,
        'livePaymentsCount': 0,
        'totalArticles': 8,
        'publishedArticles': 6,
        'draftArticles': 2,
        'totalBookmarks': 22,
        'startDate': '2026-01-01',
        'endDate': '2026-12-31',
      };

      final data = AnalyticsOverviewData.fromJson(json);
      expect(data.totalPatients, 45);
      expect(data.totalVerifiedDoctors, 12);
      expect(data.completedAppointments, 35);
      expect(data.totalRevenueByCurrency.first.netAmount, 45000.0);
      expect(data.testPaymentsCount, 15);
      expect(data.publishedArticles, 6);
      expect(data.totalBookmarks, 22);
    });

    test('parses AppointmentAnalyticsData correctly', () {
      final json = {
        'totalAppointments': 50,
        'statusBreakdown': {
          'COMPLETED': 35,
          'CANCELLED': 10,
          'CONFIRMED': 5,
        },
        'trends': [
          {
            'date': '2026-10-18',
            'total': 5,
            'completed': 4,
            'confirmed': 1,
            'cancelled': 0,
          }
        ],
        'completionRate': 87.5,
        'cancellationRate': 20.0,
      };

      final data = AppointmentAnalyticsData.fromJson(json);
      expect(data.totalAppointments, 50);
      expect(data.statusBreakdown['COMPLETED'], 35);
      expect(data.trends.first.date, '2026-10-18');
      expect(data.completionRate, 87.5);
    });
  });
}
