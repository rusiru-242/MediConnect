import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus,
  Edit,
  Eye,
  Archive,
  Send,
  Check,
  AlertCircle,
  Tag,
  Clock,
} from 'lucide-react';
import { contentApi } from '../api/contentApi';
import { HealthArticle, CreateArticleRequest } from '../types/content';
import { StatusBadge } from '../components/common/StatusBadge';
import { Pagination } from '../components/common/Pagination';
import { SearchBar } from '../components/common/SearchBar';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { Modal } from '../components/common/Modal';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { getErrorMessage } from '../api/client';

export const ContentPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Modal states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [previewArticle, setPreviewArticle] = useState<HealthArticle | null>(null);
  const [editArticle, setEditArticle] = useState<HealthArticle | null>(null);

  // Form states for create/edit
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [body, setBody] = useState('');
  const [category, setCategory] = useState('General Wellness');
  const [tagsInput, setTagsInput] = useState('');
  const [coverImageUrl, setCoverImageUrl] = useState('');

  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: contentData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['admin-content', page, searchTerm, statusFilter],
    queryFn: () =>
      contentApi.listArticles({
        page,
        pageSize: 10,
        search: searchTerm,
        status: statusFilter,
      }),
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: CreateArticleRequest) => contentApi.createArticle(data),
    onSuccess: () => {
      setActionSuccess('Article created successfully.');
      setIsCreateOpen(false);
      resetForm();
      queryClient.invalidateQueries({ queryKey: ['admin-content'] });
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err));
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<CreateArticleRequest> }) =>
      contentApi.updateArticle(id, data),
    onSuccess: () => {
      setActionSuccess('Article updated successfully.');
      setEditArticle(null);
      resetForm();
      queryClient.invalidateQueries({ queryKey: ['admin-content'] });
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err));
    },
  });

  // Publish mutation
  const publishMutation = useMutation({
    mutationFn: (id: string) => contentApi.publishArticle(id),
    onSuccess: () => {
      setActionSuccess('Article published to patient wellness feed.');
      queryClient.invalidateQueries({ queryKey: ['admin-content'] });
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err));
    },
  });

  // Archive mutation
  const archiveMutation = useMutation({
    mutationFn: (id: string) => contentApi.archiveArticle(id),
    onSuccess: () => {
      setActionSuccess('Article archived.');
      queryClient.invalidateQueries({ queryKey: ['admin-content'] });
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err));
    },
  });

  const resetForm = () => {
    setTitle('');
    setSummary('');
    setBody('');
    setCategory('General Wellness');
    setTagsInput('');
    setCoverImageUrl('');
  };

  const handleOpenEdit = (art: HealthArticle) => {
    setEditArticle(art);
    setTitle(art.title);
    setSummary(art.summary);
    setBody(art.body);
    setCategory(art.category);
    setTagsInput(art.tags?.join(', ') || '');
    setCoverImageUrl(art.coverImageUrl || '');
    setActionError(null);
    setActionSuccess(null);
  };

  const handleSaveArticle = (isDraft: boolean) => {
    if (!title.trim() || !summary.trim() || !body.trim()) {
      setActionError('Title, summary, and content body are required.');
      return;
    }

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    const payload: CreateArticleRequest = {
      title,
      summary,
      body,
      category,
      tags,
      coverImageUrl: coverImageUrl.trim() || null,
      status: isDraft ? 'DRAFT' : 'PUBLISHED',
    };

    if (editArticle) {
      updateMutation.mutate({ id: editArticle.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const articles = contentData?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Health & Wellness Content CMS
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Create, curate, and publish responsible educational articles for patients.
          </p>
        </div>

        <Button
          variant="primary"
          onClick={() => {
            resetForm();
            setEditArticle(null);
            setIsCreateOpen(true);
            setActionError(null);
            setActionSuccess(null);
          }}
          leftIcon={<Plus className="w-4 h-4" />}
        >
          New Health Article
        </Button>
      </div>

      {actionSuccess && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">
          <Check className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {actionError && (
        <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-800">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs">
        <SearchBar
          placeholder="Search articles by title or keyword..."
          value={searchTerm}
          onChange={(v) => {
            setSearchTerm(v);
            setPage(1);
          }}
        />

        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-teal-500"
          >
            <option value="ALL">All Publishing Statuses</option>
            <option value="PUBLISHED">Published</option>
            <option value="DRAFT">Drafts</option>
            <option value="ARCHIVED">Archived</option>
          </select>
        </div>
      </div>

      {/* Articles List */}
      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
        {isLoading ? (
          <LoadingSkeleton rows={5} />
        ) : error ? (
          <ErrorState
            title="Failed to load articles"
            message={getErrorMessage(error)}
            onRetry={refetch}
          />
        ) : articles.length === 0 ? (
          <EmptyState
            title="No health articles found"
            description="Start publishing medically sound wellness guides for your patient community."
            actionLabel="Create First Article"
            onAction={() => {
              resetForm();
              setIsCreateOpen(true);
            }}
          />
        ) : (
          <div className="divide-y divide-slate-100">
            {articles.map((art) => (
              <div
                key={art.id}
                className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/50 transition-colors"
              >
                <div className="space-y-1.5 max-w-2xl">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                      {art.category}
                    </span>
                    <StatusBadge status={art.status} />
                    <span className="text-[11px] text-slate-400 flex items-center gap-1">
                      <Clock className="w-3 h-3" /> {art.readTimeMinutes} min read
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-900">{art.title}</h3>
                  <p className="text-xs text-slate-500 line-clamp-2">{art.summary}</p>
                  {art.tags && art.tags.length > 0 && (
                    <div className="flex items-center gap-1.5 pt-1">
                      {art.tags.map((t) => (
                        <span
                          key={t}
                          className="inline-flex items-center gap-1 text-[10px] text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full"
                        >
                          <Tag className="w-2.5 h-2.5 text-slate-400" /> {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPreviewArticle(art)}
                    leftIcon={<Eye className="w-3.5 h-3.5" />}
                  >
                    Preview
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleOpenEdit(art)}
                    leftIcon={<Edit className="w-3.5 h-3.5" />}
                  >
                    Edit
                  </Button>
                  {art.status !== 'PUBLISHED' && (
                    <Button
                      variant="primary"
                      size="sm"
                      className="bg-emerald-600 hover:bg-emerald-700"
                      onClick={() => publishMutation.mutate(art.id)}
                      leftIcon={<Send className="w-3.5 h-3.5" />}
                    >
                      Publish
                    </Button>
                  )}
                  {art.status === 'PUBLISHED' && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-slate-500 hover:text-slate-800"
                      onClick={() => archiveMutation.mutate(art.id)}
                      leftIcon={<Archive className="w-3.5 h-3.5" />}
                    >
                      Archive
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {contentData && contentData.totalPages > 1 && (
          <Pagination
            currentPage={page}
            totalPages={contentData.totalPages}
            totalItems={contentData.total}
            pageSize={contentData.pageSize}
            onPageChange={setPage}
          />
        )}
      </div>

      {/* Create / Edit Article Modal */}
      {(isCreateOpen || !!editArticle) && (
        <Modal
          isOpen={true}
          onClose={() => {
            setIsCreateOpen(false);
            setEditArticle(null);
          }}
          title={editArticle ? 'Edit Health Article' : 'Draft New Health Article'}
          description="Educational and medically responsible patient wellness content"
          maxWidth="2xl"
        >
          <div className="space-y-4 text-xs">
            <div>
              <Input
                label="Article Title"
                placeholder="e.g. Managing Hypertension: Daily Diet and Lifestyle Guidance"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white p-2 text-xs text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                >
                  <option value="General Wellness">General Wellness</option>
                  <option value="Cardiology">Cardiology</option>
                  <option value="Nutrition & Diet">Nutrition & Diet</option>
                  <option value="Mental Health">Mental Health</option>
                  <option value="Diabetes & Endocrine">Diabetes & Endocrine</option>
                  <option value="Pediatrics">Pediatrics</option>
                </select>
              </div>

              <div>
                <Input
                  label="Tags (Comma-separated)"
                  placeholder="heart, blood pressure, salt intake"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                />
              </div>
            </div>

            <div>
              <Input
                label="Cover Image URL (Optional)"
                placeholder="https://example.com/images/wellness.jpg"
                value={coverImageUrl}
                onChange={(e) => setCoverImageUrl(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Executive Summary (Displayed in feeds)
              </label>
              <textarea
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                placeholder="Brief summary of key medical guidance..."
                rows={2}
                className="w-full rounded-lg border border-slate-300 p-2.5 text-xs text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Full Article Content (Markdown format supported)
              </label>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Write comprehensive, evidence-based medical information..."
                rows={8}
                className="w-full rounded-lg border border-slate-300 p-2.5 text-xs text-slate-900 font-mono focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 leading-relaxed"
              />
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
              <Button
                variant="outline"
                onClick={() => {
                  setIsCreateOpen(false);
                  setEditArticle(null);
                }}
              >
                Cancel
              </Button>
              <Button
                variant="secondary"
                onClick={() => handleSaveArticle(true)}
                isLoading={createMutation.isPending || updateMutation.isPending}
              >
                Save as Draft
              </Button>
              <Button
                variant="primary"
                onClick={() => handleSaveArticle(false)}
                isLoading={createMutation.isPending || updateMutation.isPending}
              >
                {editArticle ? 'Update & Publish' : 'Publish Article'}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Article Preview Modal */}
      {previewArticle && (
        <Modal
          isOpen={true}
          onClose={() => setPreviewArticle(null)}
          title="Article Preview"
          description={`Category: ${previewArticle.category}`}
          maxWidth="2xl"
        >
          <div className="space-y-4 text-xs">
            {previewArticle.coverImageUrl && (
              <img
                src={previewArticle.coverImageUrl}
                alt={previewArticle.title}
                className="w-full h-48 object-cover rounded-xl"
              />
            )}
            <h2 className="text-base font-extrabold text-slate-900">{previewArticle.title}</h2>
            <div className="flex items-center gap-3 text-[11px] text-slate-500 pb-2 border-b border-slate-100">
              <StatusBadge status={previewArticle.status} />
              <span>{previewArticle.readTimeMinutes} min read</span>
              <span>•</span>
              <span>{new Date(previewArticle.createdAt).toLocaleDateString()}</span>
            </div>
            <div className="text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-100 italic">
              {previewArticle.summary}
            </div>
            <div className="text-slate-800 leading-relaxed whitespace-pre-line py-2">
              {previewArticle.body}
            </div>
            <div className="flex justify-end pt-3 border-t border-slate-100">
              <Button variant="outline" onClick={() => setPreviewArticle(null)}>
                Close Preview
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
