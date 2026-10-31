import type { ExplorerQuery, ExplorerSort, ExplorerStatus, ExplorerView } from './types';

export const defaultExplorerQuery: ExplorerQuery = {
  folder: '',
  search: '',
  category: '',
  status: '',
  sort: 'name',
  view: 'list',
  page: 1
};

function parsePositiveInt(value: string | null): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

function parseSort(value: string | null): ExplorerSort {
  return value === 'updated' || value === 'size' ? value : 'name';
}

function parseView(value: string | null): ExplorerView {
  return value === 'grid' ? 'grid' : 'list';
}

function parseStatus(value: string | null): ExplorerStatus {
  return value === 'active' || value === 'processing' || value === 'deleted' ? value : '';
}

export function parseExplorerQuery(input: URL | URLSearchParams): ExplorerQuery {
  const params = input instanceof URL ? input.searchParams : input;
  return {
    folder: params.get('folder') ?? '',
    search: params.get('search') ?? '',
    category: params.get('category') ?? '',
    status: parseStatus(params.get('status')),
    sort: parseSort(params.get('sort')),
    view: parseView(params.get('view')),
    page: parsePositiveInt(params.get('page'))
  };
}

export function serializeExplorerQuery(query: ExplorerQuery): string {
  const params = new URLSearchParams();
  if (query.folder) params.set('folder', query.folder);
  if (query.search.trim()) params.set('search', query.search.trim());
  if (query.category) params.set('category', query.category);
  if (query.status) params.set('status', query.status);
  if (query.sort !== defaultExplorerQuery.sort) params.set('sort', query.sort);
  if (query.view !== defaultExplorerQuery.view) params.set('view', query.view);
  if (query.page > 1) params.set('page', String(query.page));
  return params.toString();
}

export function withExplorerQuery(url: URL, changes: Partial<ExplorerQuery>): string {
  const next = { ...parseExplorerQuery(url), ...changes };
  const serialized = serializeExplorerQuery(next);
  return `${url.pathname}${serialized ? `?${serialized}` : ''}`;
}
