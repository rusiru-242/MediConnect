export type ContentStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';

export interface HealthArticle {
  id: string;
  title: string;
  slug: string;
  summary: string;
  body: string;
  category: string;
  tags: string[];
  coverImageUrl?: string | null;
  status: ContentStatus;
  readTimeMinutes: number;
  viewCount: number;
  bookmarkCount: number;
  authorId: string;
  authorName?: string | null;
  publishedAt?: string | null;
  createdAt: string;
  updatedAt?: string | null;
}

export interface ContentListResponse {
  items: HealthArticle[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface CreateArticleRequest {
  title: string;
  summary: string;
  body: string;
  category: string;
  tags: string[];
  coverImageUrl?: string | null;
  status?: ContentStatus;
}

export interface UpdateArticleRequest {
  title?: string;
  summary?: string;
  body?: string;
  category?: string;
  tags?: string[];
  coverImageUrl?: string | null;
  status?: ContentStatus;
}
