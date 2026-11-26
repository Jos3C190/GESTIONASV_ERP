import { apiDownload, apiFetch } from '#lib/api/client.ts';
import type {
  AccountDocument,
  CreditStatus,
  CustomerAccount,
  CustomerSummary,
  Receipt,
  ReceiptInput,
  WithholdingCertificate
} from '#lib/types/sales-receivables.ts';

/** Cuentas por cobrar y recibos de cobro (`sales_receivables:read` / `:collect`). */
export const salesReceivablesApi = {
  portfolio() {
    return apiFetch<CustomerSummary[]>('/sales/receivables');
  },
  account(customerId: string) {
    return apiFetch<CustomerAccount>(`/sales/receivables/customers/${customerId}`);
  },
  document(documentId: string) {
    return apiFetch<AccountDocument>(`/sales/receivables/documents/${documentId}`);
  },
  recordCertificate(documentId: string, payload: WithholdingCertificate) {
    return apiFetch<AccountDocument>(
      `/sales/receivables/documents/${documentId}/withholding-certificate`,
      { method: 'PUT', body: JSON.stringify(payload) }
    );
  },
  register(payload: ReceiptInput) {
    return apiFetch<Receipt>('/sales/receipts', { method: 'POST', body: JSON.stringify(payload) });
  },
  apply(receiptId: string, applications: { document_id: string; amount: string }[]) {
    return apiFetch<Receipt>(`/sales/receipts/${receiptId}/apply`, {
      method: 'POST',
      body: JSON.stringify({ applications })
    });
  },
  annul(receiptId: string, reason: string) {
    return apiFetch<Receipt>(`/sales/receipts/${receiptId}/annul`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    });
  },
  receiptPdf(receiptId: string) {
    return apiDownload(`/sales/receipts/${receiptId}/pdf`);
  },
  credit(customerId: string) {
    return apiFetch<CreditStatus>(`/sales/receivables/customers/${customerId}/credit`);
  },
  addNote(customerId: string, note: string, nextActionOn: string | null) {
    return apiFetch<CreditStatus>(`/sales/receivables/customers/${customerId}/notes`, {
      method: 'POST',
      body: JSON.stringify({ note, next_action_on: nextActionOn })
    });
  },
  block(customerId: string, reason: string) {
    return apiFetch<CreditStatus>(`/sales/receivables/customers/${customerId}/block`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    });
  },
  unblock(customerId: string) {
    return apiFetch<CreditStatus>(`/sales/receivables/customers/${customerId}/unblock`, {
      method: 'POST'
    });
  },
  statementPdf(customerId: string) {
    return apiDownload(`/sales/receivables/customers/${customerId}/statement.pdf`);
  },
  sendStatement(customerId: string, to: string | null) {
    return apiFetch<{ sent_to: string }>(
      `/sales/receivables/customers/${customerId}/send-statement`,
      { method: 'POST', body: JSON.stringify(to ? { to } : {}) }
    );
  }
};
