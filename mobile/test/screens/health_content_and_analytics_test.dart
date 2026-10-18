import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/health_content.dart';
import 'package:mediconnect/screens/patient/article_detail_screen.dart';
import 'package:mediconnect/screens/patient/health_wellness_screen.dart';

void main() {
  final sampleArticle = HealthArticle(
    id: 'mongo_1',
    contentId: 'CNT-20261018-001',
    title: 'Everyday Hydration & Cognitive Focus',
    summary: 'How consistent hydration supports mental alertness and health.',
    body: '''## The Importance of Daily Water Intake

Staying hydrated is essential for every physiological function.

### Key Guidelines
- Drink 6 to 8 glasses daily
- Monitor your urine color
- Pair hydration with water-rich fruits

*Disclaimer: Consult your doctor for specific fluid restrictions.*''',
    category: 'Nutrition',
    tags: const ['hydration', 'brain', 'focus'],
    sources: 'WHO Healthy Diet Factsheet',
    authorName: 'MediConnect Editorial Team',
    status: 'PUBLISHED',
    readingTimeMinutes: 2,
    createdAt: DateTime.now(),
    publishedAt: DateTime.now(),
    isBookmarked: false,
  );

  group('ArticleDetailScreen widget tests', () {
    testWidgets('renders article title, reading time, body, tags and medical disclaimer', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: ArticleDetailScreen(
            articleIdentifier: sampleArticle.contentId,
            initialArticle: sampleArticle,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Check title and category
      expect(find.text('Everyday Hydration & Cognitive Focus'), findsOneWidget);
      expect(find.text('Nutrition'), findsOneWidget);
      expect(find.text('2 min read'), findsOneWidget);

      // Check summary
      expect(find.text(sampleArticle.summary), findsOneWidget);

      // Check headings and body
      expect(find.text('The Importance of Daily Water Intake'), findsOneWidget);
      expect(find.text('Key Guidelines'), findsOneWidget);

      // Check tags
      expect(find.text('hydration'), findsOneWidget);
      expect(find.text('brain'), findsOneWidget);

      // Check sources
      expect(find.text('WHO Healthy Diet Factsheet'), findsOneWidget);

      // Check medical disclaimer box
      expect(find.text('Medical Disclaimer'), findsOneWidget);
      expect(find.byIcon(Icons.shield_outlined), findsOneWidget);

      // Check bookmark button
      expect(find.byKey(const Key('article_detail_bookmark_icon_button')), findsOneWidget);
    });
  });

  group('HealthWellnessScreen widget tests', () {
    testWidgets('renders app bar, category chips, search bar, and empty or feed state', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: HealthWellnessScreen(),
        ),
      );
      await tester.pump(); // Start loading

      // App bar title
      expect(find.text('Health & Wellness'), findsOneWidget);

      // Search bar
      expect(find.byKey(const Key('health_feed_search_input')), findsOneWidget);

      // Category chips
      expect(find.text('All'), findsOneWidget);
      expect(find.text('Healthy Food'), findsOneWidget);
      expect(find.text('Exercise'), findsOneWidget);
      expect(find.text('Nutrition'), findsOneWidget);
      expect(find.text('Mental Wellness'), findsOneWidget);
      expect(find.text('Preventive Healthcare'), findsOneWidget);

      // Bookmarks button in AppBar
      expect(find.byKey(const Key('health_feed_bookmarks_icon_button')), findsOneWidget);
    });
  });
}
