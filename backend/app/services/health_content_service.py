"""Service implementing business logic for Health & Wellness Content Management (Phase 24)."""

from datetime import datetime, timezone
import logging
import math
import re
from typing import Any, Dict, List, Optional
import uuid
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.health_content import (
    ContentBookmarkDocument,
    ContentStatus,
    HealthContentDocument,
    SUPPORTED_CATEGORIES,
    calculate_reading_time,
    get_content_bookmark_collection,
    get_health_content_collection,
    utc_now,
)
from app.schemas.health_content import (
    BookmarkActionResponse,
    CategoryCountItem,
    ContentListResponse,
    ContentResponse,
    ContentSummaryItem,
    CreateContentRequest,
    UpdateContentRequest,
)
from app.schemas.user import UserResponseSchema

logger = logging.getLogger(__name__)


def generate_content_id() -> str:
    """Generate human-readable content identifier, e.g. CNT-20261018-9F3B1A."""
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return f"CNT-{date_part}-{unique_suffix}"


def generate_bookmark_id() -> str:
    """Generate unique bookmark identifier, e.g. BMK-9F3B1A2C."""
    return f"BMK-{uuid.uuid4().hex[:8].upper()}"


DEFAULT_SEED_ARTICLES = [
    {
        "title": "The Power of a Balanced Plate: Everyday Macronutrients & Energy",
        "category": "Healthy Food",
        "summary": "Learn how building meals with a balance of lean proteins, whole grains, and colorful vegetables sustains all-day vitality and metabolic wellness.",
        "body": """## Building a Balanced Plate for Everyday Vitality

Eating well does not require restrictive or extreme dietary regimens. Instead, nutritional science consistently points toward variety, balance, and moderation as the cornerstones of long-term wellness.

### The Three Pillar Macronutrients

1. **Complex Carbohydrates**: Whole grains such as brown rice, oats, barley, and quinoa supply sustained glucose, preventing rapid spikes and crashes in blood sugar levels while providing essential dietary fiber.
2. **Lean Proteins**: Essential for cellular repair, immune response, and muscle maintenance. Incorporate plant-based legumes, pulses, tofu, nuts, as well as poultry, eggs, and fish according to your dietary preferences.
3. **Heart-Healthy Fats**: Monounsaturated and polyunsaturated fats from avocados, extra virgin olive oil, nuts, and seeds support brain function, hormone synthesis, and nutrient absorption (notably vitamins A, D, E, and K).

### Practical Tips for Everyday Meals

- **Color Your Plate**: Aim for at least two different colors of fruits or vegetables in every main meal. The diverse pigments reflect varied phytonutrients and antioxidants.
- **Hydrate Consistently**: Thirst can often be mistaken for hunger. Drink water regularly throughout the day.
- **Listen to Satiety Cues**: Eat mindfully, chewing thoroughly, and pause when you feel comfortably satisfied rather than overly full.

*Disclaimer: This article provides general educational information and is not intended to replace individualized dietary guidance from a registered dietitian or physician.*""",
        "tags": ["healthy eating", "nutrition", "balanced diet", "wellness", "macronutrients"],
        "sources": "World Health Organization Healthy Diet Factsheet; Harvard T.H. Chan School of Public Health The Nutrition Source.",
        "coverImage": "https://images.unsplash.com/photo-1490645935967-10de6ba17061?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Safe Physical Activity: Sustainable Exercise Habits for Life",
        "category": "Exercise",
        "summary": "Discover practical, injury-free movement routines that fit seamlessly into busy lifestyles without extreme workouts or burnout.",
        "body": """## Movement as Medicine: Sustainable Physical Activity

Regular movement is one of the most effective ways to preserve cardiovascular function, support cognitive longevity, and elevate daily mood. You do not need punishing gym sessions to experience profound health benefits.

### Core Guidelines for Lifelong Movement

- **Consistency Trumps Intensity**: Moderate activity for 20 to 30 minutes 5 days a week produces far greater cardiovascular adaptations than sporadic, exhaustive weekend workouts.
- **Incorporate Functional Movement**: Everyday activities like brisk walking, taking the stairs, gardening, and stretching count significantly toward total weekly activity.
- **Warm-Up and Cool-Down**: Allocate 5 minutes before exercise for dynamic mobility (leg swings, arm circles) and 5 minutes after for gentle stretching to preserve joint range of motion and prevent muscular strains.

### Listening to Your Body

Always distinguish between standard muscular effort and acute, sharp pain. Sharp, radiating, or joint-centric pain is a signal to stop immediately and seek evaluation from a qualified healthcare practitioner.

*Disclaimer: Consult your doctor before embarking on any new exercise program, especially if you have chronic medical conditions or haven't exercised recently.*""",
        "tags": ["exercise", "fitness", "cardiovascular health", "active lifestyle", "mobility"],
        "sources": "American College of Sports Medicine Guidelines; CDC Physical Activity Basics.",
        "coverImage": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Everyday Hydration: Why Fluid Balance Matters More Than You Think",
        "category": "Nutrition",
        "summary": "How consistent hydration impacts cognitive focus, digestion, joint cushioning, and kidney efficiency throughout the day.",
        "body": """## Understanding Daily Hydration

Water makes up roughly 60% of adult body weight and participates in nearly every biochemical reaction, from cellular energy production to waste elimination.

### Signs of Optimal vs. Inadequate Hydration

- **Urine Color**: Light pale yellow or straw color generally indicates adequate hydration. Dark amber tones usually suggest the body needs fluids.
- **Mental Clarity**: Mild dehydration (as little as 1-2% fluid loss) can trigger subtle headaches, difficulty concentrating, and lethargy.
- **Digestive Ease**: Dietary fiber requires adequate fluid intake to smoothly pass through the gastrointestinal tract and prevent constipation.

### Healthy Hydration Habits

- Keep a reusable water bottle at your workstation or in your bag.
- Infuse plain water with lemon slices, cucumber, or mint leaves if you prefer natural flavor.
- Consume water-rich fruits and vegetables like watermelons, cucumbers, oranges, and spinach.

*Disclaimer: Individuals with certain renal, cardiovascular, or endocrine conditions should consult their supervising physician regarding specific daily fluid allowances.*""",
        "tags": ["hydration", "nutrition", "water", "digestion", "wellness"],
        "sources": "National Academies of Sciences, Engineering, and Medicine Dietary Reference Intakes for Water.",
        "coverImage": "https://images.unsplash.com/photo-1548839140-29a749e1bc4e?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Mindful Stress Reduction: Evidence-Based Techniques for Calm",
        "category": "Mental Wellness",
        "summary": "Explore gentle breathing patterns, boundaries, and sleep routines that naturally lower sympathetic nervous system overdrive.",
        "body": """## Cultivating Mental Calm in a Demanding World

Modern life frequently triggers our sympathetic nervous system—the classic 'fight or flight' response—even when there is no physical danger. Chronic activation of this pathway can elevate cortisol levels and disturb restorative sleep.

### Practical De-Stress Rituals

1. **Box Breathing**: Inhale slowly for 4 seconds, hold for 4 seconds, exhale smoothly for 4 seconds, and hold empty for 4 seconds. Repeat for 2 to 3 minutes to activate the vagus nerve and parasympathetic relaxation response.
2. **Digital Sunsets**: Power down smartphones, laptops, and bright screens at least 45 minutes before sleep to facilitate natural melatonin secretion.
3. **Gratitude Micro-Journaling**: Jot down 2 or 3 specific positive occurrences each evening to gently reframe cognitive attention away from anticipatory anxiety.

*Disclaimer: If you are experiencing persistent anxiety, low mood, or feelings of despair, please seek compassionate support from a certified psychologist, psychiatrist, or mental health hotline.*""",
        "tags": ["mental health", "stress management", "mindfulness", "breathing", "sleep"],
        "sources": "American Psychological Association Stress in America; National Institute of Mental Health.",
        "coverImage": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "The Value of Preventive Health Screenings by Age Group",
        "category": "Preventive Healthcare",
        "summary": "Why catching asymptomatic shifts in blood pressure, glucose, and lipid profiles early safeguards long-term health.",
        "body": """## Proactive Care: The Power of Preventive Screenings

Preventive healthcare focuses on maintaining wellness rather than solely treating established sickness. Many chronic cardiovascular and metabolic conditions develop silently over several years without initial symptoms.

### Key Universal Screenings

- **Blood Pressure**: Regular monitoring detects hypertension before it stresses arterial walls or the heart muscle.
- **Lipid Panels (Cholesterol)**: Periodic assessment of LDL, HDL, and triglycerides guides proactive dietary or lifestyle adjustments.
- **Fasting Blood Glucose or HbA1c**: Identifies pre-diabetic shifts early when lifestyle modifications have the highest rate of reversal.
- **Dental and Vision Checks**: Essential for oral hygiene, gum health, and screening for retinal or ocular changes.

Schedule regular discussions with your primary care doctor to tailor your screening schedule based on family medical history and individual risk factors.

*Disclaimer: This content is for educational awareness and does not replace personalized medical advice or clinical diagnostic screenings.*""",
        "tags": ["preventive care", "screenings", "blood pressure", "health checks", "wellness"],
        "sources": "US Preventive Services Task Force; Ministry of Health Non-Communicable Diseases Directorate.",
        "coverImage": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Rest & Recovery: The Undervalued Foundation of Physical Performance",
        "category": "General Health Tips",
        "summary": "Why deep sleep and planned rest days are when true physiological repair, memory consolidation, and cellular renewal occur.",
        "body": """## Why Rest Is an Active Biological Process

In a culture that often glorifies constant hustle, rest is frequently viewed as lost time. In reality, physiological recovery is when biological adaptation and repair truly occur.

### What Happens During Deep Sleep

- **Tissue Regeneration**: Human growth hormone is secreted during slow-wave non-REM sleep, stimulating muscle protein synthesis and cellular repair.
- **Neurochemical Cleansing**: The brain's glymphatic system actively flushes out metabolic waste products that accumulate during waking hours.
- **Immune Priming**: Cytokines and immune defense cells are synthesized and distributed throughout lymphatic channels.

### Restorative Habits

- Maintain consistent sleep and wake times, even on weekends.
- Keep the sleeping environment cool, quiet, and dark.
- Incorporate active rest days with light walking or gentle mobility work rather than high-impact training.

*Disclaimer: If you suffer from chronic insomnia, severe snoring, or daytime fatigue, consult a physician or sleep specialist for thorough medical evaluation.*""",
        "tags": ["sleep", "recovery", "rest", "immunity", "longevity"],
        "sources": "National Sleep Foundation Sleep Duration Recommendations; Division of Sleep Medicine at Harvard Medical School.",
        "coverImage": "https://images.unsplash.com/photo-1511295742362-92c96b124e52?auto=format&fit=crop&w=1200&q=80",
    },
]


class HealthContentService:
    """Core service for managing health articles, bookmarks, and educational feeds."""

    @classmethod
    def _find_article_doc(cls, db: Database, identifier: str) -> Optional[Dict[str, Any]]:
        """Look up article by MongoDB ObjectId or human-readable contentId."""
        coll = get_health_content_collection(db)
        if ObjectId.is_valid(identifier):
            doc = coll.find_one({"$or": [{"_id": ObjectId(identifier)}, {"contentId": identifier}]})
            if doc:
                return doc
        return coll.find_one({"contentId": identifier})

    @classmethod
    def seed_default_articles_if_empty(cls, db: Database, admin_user_id: Optional[str] = "ADMIN-SYSTEM") -> int:
        """Seed initial educational articles if the collection is currently empty."""
        coll = get_health_content_collection(db)
        if coll.count_documents({}) > 0:
            return 0

        inserted_count = 0
        now = utc_now()
        for idx, item in enumerate(DEFAULT_SEED_ARTICLES):
            reading_time = calculate_reading_time(item["body"])
            content_id = f"CNT-{now.strftime('%Y%m%d')}-00{idx + 1}"
            doc = {
                "contentId": content_id,
                "title": item["title"],
                "summary": item["summary"],
                "body": item["body"],
                "category": item["category"],
                "coverImage": item.get("coverImage"),
                "tags": item.get("tags", []),
                "sources": item.get("sources"),
                "authorAdminId": admin_user_id,
                "authorName": "MediConnect Editorial Team",
                "status": ContentStatus.PUBLISHED.value,
                "readingTimeMinutes": reading_time,
                "createdAt": now,
                "updatedAt": now,
                "publishedAt": now,
            }
            try:
                coll.insert_one(doc)
                inserted_count += 1
            except Exception as e:
                logger.warning("Failed to insert seed article: %s", e)

        logger.info("Successfully seeded %d default health articles.", inserted_count)
        return inserted_count

    @classmethod
    def _user_bookmarked_ids(cls, db: Database, user_id: Optional[str]) -> set[str]:
        """Return set of contentIds and string _ids bookmarked by the user."""
        if not user_id:
            return set()
        bm_coll = get_content_bookmark_collection(db)
        cursor = bm_coll.find({"userId": user_id}, {"contentId": 1})
        return {b["contentId"] for b in cursor}

    @classmethod
    def _doc_to_response(
        cls, doc: Dict[str, Any], is_bookmarked: bool = False
    ) -> ContentResponse:
        """Map MongoDB document to ContentResponse schema."""
        return ContentResponse(
            id=str(doc["_id"]),
            contentId=doc["contentId"],
            title=doc["title"],
            summary=doc["summary"],
            body=doc["body"],
            category=doc["category"],
            coverImage=doc.get("coverImage"),
            tags=doc.get("tags", []),
            sources=doc.get("sources"),
            authorAdminId=str(doc.get("authorAdminId", "")),
            authorName=doc.get("authorName", "MediConnect Editorial Team"),
            status=doc.get("status", ContentStatus.DRAFT.value),
            readingTimeMinutes=doc.get("readingTimeMinutes", 1),
            createdAt=doc.get("createdAt", utc_now()),
            updatedAt=doc.get("updatedAt", utc_now()),
            publishedAt=doc.get("publishedAt"),
            isBookmarked=is_bookmarked,
        )

    @classmethod
    def _doc_to_summary(
        cls, doc: Dict[str, Any], is_bookmarked: bool = False
    ) -> ContentSummaryItem:
        """Map MongoDB document to ContentSummaryItem schema."""
        return ContentSummaryItem(
            id=str(doc["_id"]),
            contentId=doc["contentId"],
            title=doc["title"],
            summary=doc["summary"],
            category=doc["category"],
            coverImage=doc.get("coverImage"),
            tags=doc.get("tags", []),
            authorName=doc.get("authorName", "MediConnect Editorial Team"),
            readingTimeMinutes=doc.get("readingTimeMinutes", 1),
            status=doc.get("status", ContentStatus.DRAFT.value),
            createdAt=doc.get("createdAt", utc_now()),
            publishedAt=doc.get("publishedAt"),
            isBookmarked=is_bookmarked,
        )

    # -------------------------------------------------------------------------
    # Admin Operations
    # -------------------------------------------------------------------------

    @classmethod
    def create_article(
        cls, db: Database, admin: UserResponseSchema, payload: CreateContentRequest
    ) -> ContentResponse:
        """Create a new health article draft or published piece."""
        coll = get_health_content_collection(db)
        content_id = generate_content_id()
        now = utc_now()
        reading_time = calculate_reading_time(payload.body)

        published_at = now if payload.status == ContentStatus.PUBLISHED else None

        doc = HealthContentDocument(
            contentId=content_id,
            title=payload.title,
            summary=payload.summary,
            body=payload.body,
            category=payload.category,
            coverImage=payload.coverImage,
            tags=payload.tags,
            sources=payload.sources,
            authorAdminId=admin.id,
            authorName=admin.fullName or "MediConnect Admin",
            status=payload.status,
            readingTimeMinutes=reading_time,
            createdAt=now,
            updatedAt=now,
            publishedAt=published_at,
        )

        to_insert = doc.to_mongo_dict()
        result = coll.insert_one(to_insert)
        to_insert["_id"] = result.inserted_id
        return cls._doc_to_response(to_insert, is_bookmarked=False)

    @classmethod
    def update_article(
        cls, db: Database, identifier: str, payload: UpdateContentRequest
    ) -> ContentResponse:
        """Update an existing health article."""
        coll = get_health_content_collection(db)
        doc = cls._find_article_doc(db, identifier)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Health article '{identifier}' not found.",
            )

        update_fields: Dict[str, Any] = {"updatedAt": utc_now()}
        if payload.title is not None:
            update_fields["title"] = payload.title.strip()
        if payload.summary is not None:
            update_fields["summary"] = payload.summary.strip()
        if payload.body is not None:
            body_text = payload.body.strip()
            update_fields["body"] = body_text
            update_fields["readingTimeMinutes"] = calculate_reading_time(body_text)
        if payload.category is not None:
            update_fields["category"] = payload.category
        if payload.coverImage is not None:
            update_fields["coverImage"] = payload.coverImage
        if payload.tags is not None:
            update_fields["tags"] = payload.tags
        if payload.sources is not None:
            update_fields["sources"] = payload.sources
        if payload.status is not None:
            update_fields["status"] = payload.status.value
            if payload.status == ContentStatus.PUBLISHED and not doc.get("publishedAt"):
                update_fields["publishedAt"] = utc_now()

        coll.update_one({"_id": doc["_id"]}, {"$set": update_fields})
        updated_doc = coll.find_one({"_id": doc["_id"]})
        return cls._doc_to_response(updated_doc, is_bookmarked=False)

    @classmethod
    def publish_article(cls, db: Database, identifier: str) -> ContentResponse:
        """Transition an article status to PUBLISHED."""
        coll = get_health_content_collection(db)
        doc = cls._find_article_doc(db, identifier)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Health article '{identifier}' not found.",
            )

        now = utc_now()
        coll.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "status": ContentStatus.PUBLISHED.value,
                    "publishedAt": doc.get("publishedAt") or now,
                    "updatedAt": now,
                }
            },
        )
        updated_doc = coll.find_one({"_id": doc["_id"]})
        return cls._doc_to_response(updated_doc, is_bookmarked=False)

    @classmethod
    def archive_article(cls, db: Database, identifier: str) -> ContentResponse:
        """Transition an article status to ARCHIVED."""
        coll = get_health_content_collection(db)
        doc = cls._find_article_doc(db, identifier)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Health article '{identifier}' not found.",
            )

        now = utc_now()
        coll.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": ContentStatus.ARCHIVED.value, "updatedAt": now}},
        )
        updated_doc = coll.find_one({"_id": doc["_id"]})
        return cls._doc_to_response(updated_doc, is_bookmarked=False)

    @classmethod
    def list_admin_articles(
        cls,
        db: Database,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> ContentListResponse:
        """List articles for administrative management with filters and pagination."""
        cls.seed_default_articles_if_empty(db)
        coll = get_health_content_collection(db)

        query: Dict[str, Any] = {}
        if status_filter and status_filter.upper() != "ALL":
            query["status"] = status_filter.upper()
        if category and category.strip():
            query["category"] = category.strip()
        if search and search.strip():
            s = search.strip()
            query["$or"] = [
                {"contentId": {"$regex": re.escape(s), "$options": "i"}},
                {"title": {"$regex": re.escape(s), "$options": "i"}},
                {"summary": {"$regex": re.escape(s), "$options": "i"}},
                {"tags": {"$regex": re.escape(s), "$options": "i"}},
            ]

        total = coll.count_documents(query)
        page = max(1, page)
        page_size = max(1, min(page_size, 50))
        skip = (page - 1) * page_size
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

        cursor = (
            coll.find(query)
            .sort([("updatedAt", DESCENDING)])
            .skip(skip)
            .limit(page_size)
        )
        items = [cls._doc_to_summary(doc, is_bookmarked=False) for doc in cursor]

        categories = cls.get_categories(db)
        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
            categories=categories,
        )

    # -------------------------------------------------------------------------
    # Public & Patient Operations
    # -------------------------------------------------------------------------

    @classmethod
    def list_published_articles(
        cls,
        db: Database,
        category: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        user_id: Optional[str] = None,
    ) -> ContentListResponse:
        """List published health articles for patient feed with pagination and bookmarks."""
        cls.seed_default_articles_if_empty(db)
        coll = get_health_content_collection(db)

        query: Dict[str, Any] = {"status": ContentStatus.PUBLISHED.value}
        if category and category.strip():
            query["category"] = category.strip()
        if search and search.strip():
            s = search.strip()
            query["$or"] = [
                {"contentId": {"$regex": re.escape(s), "$options": "i"}},
                {"title": {"$regex": re.escape(s), "$options": "i"}},
                {"summary": {"$regex": re.escape(s), "$options": "i"}},
                {"tags": {"$regex": re.escape(s), "$options": "i"}},
            ]

        total = coll.count_documents(query)
        page = max(1, page)
        page_size = max(1, min(page_size, 50))
        skip = (page - 1) * page_size
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

        cursor = (
            coll.find(query)
            .sort([("publishedAt", DESCENDING), ("createdAt", DESCENDING)])
            .skip(skip)
            .limit(page_size)
        )

        bookmarked_set = cls._user_bookmarked_ids(db, user_id)
        items = []
        for doc in cursor:
            is_bm = doc["contentId"] in bookmarked_set or str(doc["_id"]) in bookmarked_set
            items.append(cls._doc_to_summary(doc, is_bookmarked=is_bm))

        categories = cls.get_categories(db)
        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
            categories=categories,
        )

    @classmethod
    def get_article_by_id(
        cls,
        db: Database,
        identifier: str,
        user_id: Optional[str] = None,
        require_published: bool = True,
    ) -> ContentResponse:
        """Fetch article detail by id or contentId."""
        cls.seed_default_articles_if_empty(db)
        doc = cls._find_article_doc(db, identifier)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Health article '{identifier}' not found.",
            )

        if require_published and doc.get("status") != ContentStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article is not published or has been archived.",
            )

        bookmarked_set = cls._user_bookmarked_ids(db, user_id)
        is_bm = doc["contentId"] in bookmarked_set or str(doc["_id"]) in bookmarked_set
        return cls._doc_to_response(doc, is_bookmarked=is_bm)

    @classmethod
    def get_categories(cls, db: Database) -> List[CategoryCountItem]:
        """Return available health categories and published article counts."""
        coll = get_health_content_collection(db)
        pipeline = [
            {"$match": {"status": ContentStatus.PUBLISHED.value}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        ]
        results = {r["_id"]: r["count"] for r in coll.aggregate(pipeline)}
        items = []
        for cat in SUPPORTED_CATEGORIES:
            items.append(CategoryCountItem(category=cat, count=results.get(cat, 0)))
        return items

    # -------------------------------------------------------------------------
    # Bookmark Operations
    # -------------------------------------------------------------------------

    @classmethod
    def toggle_bookmark(
        cls, db: Database, user_id: str, identifier: str
    ) -> BookmarkActionResponse:
        """Add or remove bookmark for an article."""
        doc = cls._find_article_doc(db, identifier)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Health article '{identifier}' not found.",
            )

        bm_coll = get_content_bookmark_collection(db)
        content_id = doc["contentId"]
        existing = bm_coll.find_one({
            "userId": user_id,
            "$or": [{"contentId": content_id}, {"contentId": str(doc["_id"])}],
        })

        if existing:
            bm_coll.delete_one({"_id": existing["_id"]})
            return BookmarkActionResponse(
                success=True,
                isBookmarked=False,
                message="Article removed from your bookmarks.",
            )

        bm_doc = ContentBookmarkDocument(
            bookmarkId=generate_bookmark_id(),
            userId=user_id,
            contentId=content_id,
            createdAt=utc_now(),
        )
        try:
            bm_coll.insert_one(bm_doc.model_dump(by_alias=True, exclude_none=True))
        except DuplicateKeyError:
            pass  # Already bookmarked concurrently

        return BookmarkActionResponse(
            success=True,
            isBookmarked=True,
            message="Article saved to your bookmarks.",
        )

    @classmethod
    def remove_bookmark(
        cls, db: Database, user_id: str, identifier: str
    ) -> BookmarkActionResponse:
        """Explicitly remove article from bookmarks."""
        doc = cls._find_article_doc(db, identifier)
        bm_coll = get_content_bookmark_collection(db)

        query: Dict[str, Any] = {"userId": user_id}
        if doc:
            query["$or"] = [{"contentId": doc["contentId"]}, {"contentId": str(doc["_id"])}]
        else:
            query["contentId"] = identifier

        result = bm_coll.delete_many(query)
        if result.deleted_count == 0:
            return BookmarkActionResponse(
                success=True,
                isBookmarked=False,
                message="Article was not in bookmarks.",
            )

        return BookmarkActionResponse(
            success=True,
            isBookmarked=False,
            message="Article removed from bookmarks.",
        )

    @classmethod
    def list_user_bookmarks(
        cls, db: Database, user_id: str, page: int = 1, page_size: int = 10
    ) -> ContentListResponse:
        """Retrieve paginated list of articles bookmarked by the user."""
        bm_coll = get_content_bookmark_collection(db)
        coll = get_health_content_collection(db)

        total_bms = bm_coll.count_documents({"userId": user_id})
        page = max(1, page)
        page_size = max(1, min(page_size, 50))
        skip = (page - 1) * page_size
        total_pages = max(1, math.ceil(total_bms / page_size)) if total_bms > 0 else 1

        bm_cursor = (
            bm_coll.find({"userId": user_id})
            .sort([("createdAt", DESCENDING)])
            .skip(skip)
            .limit(page_size)
        )
        content_ids = [b["contentId"] for b in bm_cursor]

        articles_cursor = coll.find({
            "$or": [
                {"contentId": {"$in": content_ids}},
                {"_id": {"$in": [ObjectId(c) for c in content_ids if ObjectId.is_valid(c)]}},
            ],
            "status": ContentStatus.PUBLISHED.value,
        })
        article_map = {}
        for a in articles_cursor:
            article_map[a["contentId"]] = a
            article_map[str(a["_id"])] = a

        items = []
        for cid in content_ids:
            if cid in article_map:
                doc = article_map[cid]
                # Avoid duplicate addition if mapped by both contentId and _id
                if not any(it.contentId == doc["contentId"] for it in items):
                    items.append(cls._doc_to_summary(doc, is_bookmarked=True))

        categories = cls.get_categories(db)
        return ContentListResponse(
            items=items,
            total=len(items),
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
            categories=categories,
        )
