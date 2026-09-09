import type {
  DocumentBreadcrumbOut,
  DocumentCategoryOut,
  GeneralEntryOut,
  GeneralExplorerPage
} from '$lib/api/client';

export type ExplorerView = 'list' | 'grid';
export type ExplorerSort = 'name' | 'updated' | 'size';
export type ExplorerStatus = '' | 'active' | 'processing' | 'deleted';

export interface ExplorerQuery {
  folder: string;
  search: string;
  category: string;
  status: ExplorerStatus;
  sort: ExplorerSort;
  view: ExplorerView;
  page: number;
}

export interface ExplorerDocument {
  id: string;
  title: string;
  original_filename: string;
  extension: string;
  technical_status: string;
  business_status: string;
  size_bytes: number;
  category_name: string | null;
}

export type ExplorerItem =
  | { kind: 'folder'; id: string; name: string; entry: GeneralEntryOut; updatedAt: string | null }
  | {
      kind: 'file';
      id: string;
      name: string;
      entry: GeneralEntryOut;
      document: ExplorerDocument;
      updatedAt: string | null;
    };

export interface ExplorerData {
  items: ExplorerItem[];
  breadcrumbs: DocumentBreadcrumbOut[];
  categories: DocumentCategoryOut[];
  total: number;
  pages: number;
}

export function normalizeExplorerPage(
  page: GeneralExplorerPage,
  categories: DocumentCategoryOut[]
): ExplorerData {
  const items: ExplorerItem[] = [];
  for (const entry of page.items) {
    if (entry.kind === 'folder') {
      items.push({
        kind: 'folder',
        id: entry.id,
        name: entry.name,
        entry,
        updatedAt: entry.updated_at
      });
      continue;
    }
    if (entry.document_id) {
      items.push({
        kind: 'file',
        id: entry.id,
        name: entry.name,
        entry,
        document: {
          id: entry.document_id,
          title: entry.title ?? entry.name,
          original_filename: entry.original_filename ?? entry.name,
          extension: entry.extension ?? '',
          technical_status: entry.technical_status ?? '',
          business_status: entry.business_status ?? '',
          size_bytes: entry.size_bytes ?? 0,
          category_name: entry.category_name ?? null
        },
        updatedAt: entry.updated_at
      });
    }
  }
  return {
    items,
    breadcrumbs: page.breadcrumbs,
    categories,
    total: page.meta.total,
    pages: page.meta.pages
  };
}
