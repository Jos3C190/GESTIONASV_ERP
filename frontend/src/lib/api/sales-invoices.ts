import { apiDownload, apiFetch } from '#lib/api/client.ts';
import { branch } from '#lib/stores/branch.svelte.ts';
import type {
  FiscalDocument,
  FiscalDocumentFilters,
  FiscalDocumentPage,
  FiscalEmail,
  FiscalEmailHistory,
  FiscalInvalidation,
  Correction,
  CreditLineInput,
  DebitChargeInput,
  InvalidationOverview,
  NotesOverview,
  InvoiceOptions,
  Person,
  FiscalReturn,
  ReturnsOverview,
  TransferRemission
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
  invoice(
    orderId: string,
    pointOfSaleId: string | null,
    renta: { operation: number | null; income: number | null } = { operation: null, income: null }
  ) {
    return apiFetch<FiscalDocument>(`/sales/${orderId}/invoice`, {
      method: 'POST',
      body: JSON.stringify({
        point_of_sale_id: pointOfSaleId,
        renta_operation_type: renta.operation,
        renta_income_type: renta.income
      })
    });
  },
  list(filters: FiscalDocumentFilters = {}) {
    return apiFetch<FiscalDocumentPage>(fiscalDocumentsPath(filters));
  },
  get(id: string) {
    return apiFetch<FiscalDocument>(`/sales/fiscal-documents/${id}`);
  },
  /** Nota de remisión del traslado (V4d). */
  transferRemission(transferId: string) {
    return apiFetch<TransferRemission>(`/inventory/transfers/${transferId}/remission`);
  },
  reissueTransferRemission(transferId: string) {
    return apiFetch<FiscalDocument>(`/inventory/transfers/${transferId}/remission/reissue`, {
      method: 'POST'
    });
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
  invalidation(id: string) {
    return apiFetch<InvalidationOverview>(`/sales/fiscal-documents/${id}/invalidation`);
  },
  invalidate(id: string, payload: { reason: string; requester: Person; cancel_order?: boolean }) {
    return apiFetch<FiscalInvalidation>(`/sales/fiscal-documents/${id}/invalidate`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  /** Eventos de retorno de una factura (V4d2). */
  returns(id: string) {
    return apiFetch<ReturnsOverview>(`/sales/fiscal-documents/${id}/returns`);
  },
  registerReturn(
    id: string,
    payload: { reason: string; lines: { invoice_line_number: number; quantity: string }[] }
  ) {
    return apiFetch<FiscalReturn>(`/sales/fiscal-documents/${id}/returns`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  annulReturn(returnId: string, requester: Person) {
    return apiFetch<FiscalReturn>(`/sales/fiscal-returns/${returnId}/annul`, {
      method: 'POST',
      body: JSON.stringify({ requester })
    });
  },
  returnPdf(returnId: string) {
    return apiDownload(`/sales/fiscal-returns/${returnId}/pdf`);
  },
  returnJson(returnId: string) {
    return apiDownload(`/sales/fiscal-returns/${returnId}/json`);
  },
  correct(id: string, requester: Person) {
    return apiFetch<Correction>(`/sales/fiscal-documents/${id}/correct`, {
      method: 'POST',
      body: JSON.stringify({ requester })
    });
  },
  notes(id: string) {
    return apiFetch<NotesOverview>(`/sales/fiscal-documents/${id}/notes`);
  },
  creditNote(id: string, payload: { reason: string; lines: CreditLineInput[] }) {
    return apiFetch<FiscalDocument>(`/sales/fiscal-documents/${id}/credit-note`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  debitNote(id: string, payload: { reason: string; charges: DebitChargeInput[] }) {
    return apiFetch<FiscalDocument>(`/sales/fiscal-documents/${id}/debit-note`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  sendEmail(id: string, recipients: string[] | null) {
    return apiFetch<FiscalEmail>(`/sales/fiscal-documents/${id}/emails`, {
      method: 'POST',
      body: JSON.stringify({ recipients })
    });
  }
};
