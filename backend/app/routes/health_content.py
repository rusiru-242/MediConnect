"""FastAPI routes for Health & Wellness Content Management and Patient Feed (Phase 24)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user, get_optional_current_user, require_admin
from app.schemas.health_content import (
    BookmarkActionResponse,
    CategoryCountItem,
    ContentListResponse,
    ContentResponse,
    CreateContentRequest,
    UpdateContentRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.health_content_service import HealthContentService

# -----------------------------------------------------------------------------
# 1. Public & Patient Content Router (/api/content)
# -----------------------------------------------------------------------------
content_router = APIRouter(
    prefix="/content",
    tags=["Health & Wellness Content"],
)


@content_router.get(
    "/categories",
    response_model=List[CategoryCountItem],
    status_code=status.HTTP_200_OK,
    summary="List health content categories and article counts",
)
def get_categories(
    db: Database = Depends(get_database),
) -> List[CategoryCountItem]:
    """Retrieve available health topic categories and published article counts."""
    return HealthContentService.get_categories(db)


@content_router.get(
    "/bookmarks",
    response_model=ContentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List patient's bookmarked health articles",
)
def list_user_bookmarks(
    page: int = Query(1, ge=1, description="Page number"),
    pageSize: int = Query(10, ge=1, le=50, description="Items per page"),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> ContentListResponse:
    """Retrieve articles bookmarked by the authenticated patient."""
    return HealthContentService.list_user_bookmarks(
        db=db, user_id=current_user.id, page=page, page_size=pageSize
    )


@content_router.post(
    "/bookmarks/{identifier}",
    response_model=BookmarkActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle bookmark for an article",
)
def toggle_bookmark(
    identifier: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> BookmarkActionResponse:
    """Add or remove an article from user bookmarks."""
    return HealthContentService.toggle_bookmark(
        db=db, user_id=current_user.id, identifier=identifier
    )


@content_router.delete(
    "/bookmarks/{identifier}",
    response_model=BookmarkActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove an article from bookmarks",
)
def remove_bookmark(
    identifier: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> BookmarkActionResponse:
    """Remove an article from user bookmarks."""
    return HealthContentService.remove_bookmark(
        db=db, user_id=current_user.id, identifier=identifier
    )


@content_router.get(
    "",
    response_model=ContentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List published health articles with category filter and search",
)
def list_published_articles(
    category: Optional[str] = Query(None, description="Category filter"),
    search: Optional[str] = Query(None, description="Search term across title, summary, tags"),
    page: int = Query(1, ge=1, description="Page number"),
    pageSize: int = Query(10, ge=1, le=50, description="Items per page"),
    optional_user: Optional[UserResponseSchema] = Depends(get_optional_current_user),
    db: Database = Depends(get_database),
) -> ContentListResponse:
    """List published health and wellness articles for patient feed."""
    user_id = optional_user.id if optional_user else None
    return HealthContentService.list_published_articles(
        db=db,
        category=category,
        search=search,
        page=page,
        page_size=pageSize,
        user_id=user_id,
    )


@content_router.get(
    "/{identifier}",
    response_model=ContentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get published health article details",
)
def get_article_detail(
    identifier: str,
    optional_user: Optional[UserResponseSchema] = Depends(get_optional_current_user),
    db: Database = Depends(get_database),
) -> ContentResponse:
    """Fetch published health article details by contentId or ObjectId."""
    user_id = optional_user.id if optional_user else None
    return HealthContentService.get_article_by_id(
        db=db, identifier=identifier, user_id=user_id, require_published=True
    )


# -----------------------------------------------------------------------------
# 2. Admin Content Management Router (/api/admin/content)
# -----------------------------------------------------------------------------
admin_content_router = APIRouter(
    prefix="/admin/content",
    tags=["Admin Health Content Management"],
)


@admin_content_router.post(
    "",
    response_model=ContentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a health article (Admin only)",
)
def create_article(
    payload: CreateContentRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> ContentResponse:
    """Create a new health article draft or published article."""
    return HealthContentService.create_article(db=db, admin=current_admin, payload=payload)


@admin_content_router.patch(
    "/{identifier}",
    response_model=ContentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a health article (Admin only)",
)
def update_article(
    identifier: str,
    payload: UpdateContentRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> ContentResponse:
    """Update fields of an existing health article."""
    return HealthContentService.update_article(db=db, identifier=identifier, payload=payload)


@admin_content_router.post(
    "/{identifier}/publish",
    response_model=ContentResponse,
    status_code=status.HTTP_200_OK,
    summary="Publish a health article (Admin only)",
)
def publish_article(
    identifier: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> ContentResponse:
    """Set health article status to PUBLISHED."""
    return HealthContentService.publish_article(db=db, identifier=identifier)


@admin_content_router.post(
    "/{identifier}/archive",
    response_model=ContentResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive a health article (Admin only)",
)
def archive_article(
    identifier: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> ContentResponse:
    """Set health article status to ARCHIVED."""
    return HealthContentService.archive_article(db=db, identifier=identifier)


@admin_content_router.get(
    "",
    response_model=ContentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all articles for admin management (Admin only)",
)
def list_admin_articles(
    status: Optional[str] = Query(None, description="Filter by status (DRAFT, PUBLISHED, ARCHIVED, ALL)"),
    category: Optional[str] = Query(None, description="Category filter"),
    search: Optional[str] = Query(None, description="Search term"),
    page: int = Query(1, ge=1, description="Page number"),
    pageSize: int = Query(10, ge=1, le=50, description="Items per page"),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> ContentListResponse:
    """List articles with draft/archive/published statuses for admin review and management."""
    return HealthContentService.list_admin_articles(
        db=db,
        status_filter=status,
        category=category,
        search=search,
        page=page,
        page_size=pageSize,
    )


@admin_content_router.get(
    "/{identifier}",
    response_model=ContentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get any article by id for admin preview (Admin only)",
)
def get_admin_article_preview(
    identifier: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> ContentResponse:
    """Preview draft, published, or archived article details."""
    return HealthContentService.get_article_by_id(
        db=db, identifier=identifier, user_id=current_admin.id, require_published=False
    )
