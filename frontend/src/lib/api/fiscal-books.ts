import { apiDownload, apiFetch } from '#lib/api/client.ts';
import type {
  FiscalBookKind,
  FiscalBookMode,
  FiscalMonth,
  PeriodStatus,
  PurchaseFiscal,
  PurchaseFiscalInput,
  RentaPurchase
} from '#lib/types/fiscal-books.ts';

function query(mode: FiscalBookMode | null, extra: Record<string, string> = {}): string {
  const params = new URLSearchParams(extra);
  if (mode) params.set('mode', mode);
  const text = params.toString();
  return text ? `?${text}` : '';
}

/** Libros de IVA y anexos del F-07 (requiere `fiscal_books:read`). */
export const fiscalBooksApi = {
  month(period: string, mode: FiscalBookMode | null = null) {
    return apiFetch<FiscalMonth>(`/fiscal-books/${period}${query(mode)}`);
  },
  workbook(period: string, mode: FiscalBookMode | null = null) {
    return apiDownload(`/fiscal-books/${period}/xlsx${query(mode)}`);
  },
  bookPdf(
    period: string,
    book: FiscalBookKind,
    firstFolio: number,
    mode: FiscalBookMode | null = null
  ) {
    return apiDownload(
      `/fiscal-books/${period}/pdf${query(mode, { book, first_folio: String(firstFolio) })}`
    );
  },
  f07Zip(period: string, mode: FiscalBookMode | null = null) {
    return apiDownload(`/fiscal-books/${period}/f07.zip${query(mode)}`);
  },
  purchase(id: string) {
    return apiFetch<PurchaseFiscal>(`/fiscal-books/purchases/${id}`);
  },
  recordPurchase(id: string, payload: PurchaseFiscalInput) {
    return apiFetch<PurchaseFiscal>(`/fiscal-books/purchases/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },
  periodStatus(period: string) {
    return apiFetch<PeriodStatus>(`/fiscal-books/${period}/close`);
  },
  closePeriod(period: string) {
    return apiFetch<PeriodStatus>(`/fiscal-books/${period}/close`, { method: 'POST' });
  },
  reopenPeriod(period: string, reason: string) {
    return apiFetch<PeriodStatus>(`/fiscal-books/${period}/reopen`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    });
  },
  settings() {
    return apiFetch<RentaPurchase>('/fiscal-books/settings');
  },
  saveSettings(payload: RentaPurchase) {
    return apiFetch<RentaPurchase>('/fiscal-books/settings', {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  }
};
