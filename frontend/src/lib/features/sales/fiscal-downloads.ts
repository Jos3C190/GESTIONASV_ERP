import { salesInvoicesApi } from '#lib/api/sales-invoices.ts';
import type { FiscalDocument } from '#lib/types/sales-invoices.ts';

/** Descarga el JSON del DTE con el número de control como nombre. */
export async function downloadFiscalJson(document: FiscalDocument): Promise<void> {
  const blob = await salesInvoicesApi.json(document.id);
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement('a');
  link.href = url;
  link.download = `${document.control_number ?? document.id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** Abre el PDF del DTE con el enlace temporal que firma el backend. */
export async function openFiscalPdf(document: FiscalDocument): Promise<void> {
  const { url } = await salesInvoicesApi.pdfUrl(document.id);
  window.open(url, '_blank', 'noopener');
}
