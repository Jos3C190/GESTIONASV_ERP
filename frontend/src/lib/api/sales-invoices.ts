import { apiDownload, apiFetch } from '#lib/api/client.ts';
import { branch } from '#lib/stores/branch.svelte.ts';
import type {
  FiscalDocument,
  FiscalDocumentFilters,
  FiscalDocumentPage,
  FiscalEmail,
  FiscalEmailHistory,
  InvoiceOptions
} from '#lib/types/sales-invoices.ts';

export function fiscalDocumentsPath(filters: FiscalDocumentFilters = {}): string {
  const query = new URLSearchParams();
  const branchId = filters.branch_id === undefined ? branch.id : filters.branch_id;
  if (branchId) query.set('branch_id', branchId);
  if (filters.sale_id) query.set('sale_id', filters.sale_id);
  if (filters.status) query.set('status', filters.status);
  if (filters.document_type) query.set('document_type', filters.document_type);
  if (filters.q?.trim()) query.set('q', filters.q.trim());
  query.set('page', String(filters.page ?? 1));
  query.set('size', String(filters.size ?? 20));
  return `/sales/fiscal-documents?${query.toString()}`;
}

export const salesInvoicesApi = {
  options(orderId: string) {
    return apiFetch<InvoiceOptions>(`/sales/${orderId}/invoice-options`);
  },
  invoice(orderId: string, pointOfSaleId: string | null) {
    return apiFetch<FiscalDocument>(`/sales/${orderId}/invoice`, {
      method: 'POST',
      body: JSON.stringify({ point_of_sale_id: pointOfSaleId })
    });
  },
  list(filters: FiscalDocumentFilters = {}) {
    return apiFetch<FiscalDocumentPage>(fiscalDocumentsPath(filters));
  },
  get(id: string) {
    return apiFetch<FiscalDocument>(`/sales/fiscal-documents/${id}`);
  },
  retry(id: string) {
    return apiFetch<FiscalDocument>(`/sales/fiscal-documents/${id}/retry`, { method: 'POST' });
  },
  json(id: string) {
    return apiDownload(`/sales/fiscal-documents/${id}/json`);
  },
  pdfUrl(id: string) {
    return apiFetch<{ url: string }>(`/sales/fiscal-documents/${id}/pdf`);
  },
  emails(id: string) {
    return apiFetch<FiscalEmailHistory>(`/sales/fiscal-documents/${id}/emails`);
  },
  sendEmail(id: string, recipients: string[] | null) {
    return apiFetch<FiscalEmail>(`/sales/fiscal-documents/${id}/emails`, {
      method: 'POST',
      body: JSON.stringify({ recipients })
    });
  }
};
