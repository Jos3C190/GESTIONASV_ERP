import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { salesInvoicesApi } = vi.hoisted(() => ({
  salesInvoicesApi: { transferRemission: vi.fn(), reissueTransferRemission: vi.fn() }
}));
vi.mock('#lib/api/sales-invoices.ts', () => ({ salesInvoicesApi }));

import type { FiscalDocument } from '#lib/types/sales-invoices.ts';
import TransferRemissionCard from './TransferRemissionCard.svelte';

function remission(overrides: Partial<FiscalDocument> = {}): FiscalDocument {
  return {
    id: 'nr-1',
    document_type: '04',
    status: 'simulated',
    control_number: 'DTE-04-M001P001-000000000000001',
    total: '209.05',
    error_message: null,
    sale_id: null,
    transfer_id: 'tr-1',
    transfer_code: 'TR-0001',
    ...overrides
  } as FiscalDocument;
}

beforeEach(() => {
  salesInvoicesApi.transferRemission.mockReset();
  salesInvoicesApi.reissueTransferRemission.mockReset();
});

it('muestra la nota emitida con su número y el valor al costo', async () => {
  salesInvoicesApi.transferRemission.mockResolvedValue({ enabled: true, document: remission() });
  render(TransferRemissionCard, { transferId: 'tr-1', canReissue: true, canOpenDocument: true });

  const link = await screen.findByRole('link', { name: 'DTE-04-M001P001-000000000000001' });
  expect(link).toHaveAttribute('href', '/sales/fiscal-documents/nr-1');
  expect(screen.getByText('$209.05')).toBeInTheDocument();
  expect(screen.getByText('Simulado')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Emitir de nuevo' })).not.toBeInTheDocument();
});

it('una nota rechazada se emite de nuevo', async () => {
  salesInvoicesApi.transferRemission.mockResolvedValue({
    enabled: true,
    document: remission({ status: 'rejected', control_number: null, error_message: 'NIT inválido' })
  });
  salesInvoicesApi.reissueTransferRemission.mockResolvedValue(
    remission({ id: 'nr-2', status: 'pending', control_number: null })
  );
  render(TransferRemissionCard, { transferId: 'tr-1', canReissue: true, canOpenDocument: false });

  expect(
    await screen.findByText(/Hacienda rechazó la nota de remisión\. NIT inválido/)
  ).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Emitir de nuevo' }));
  expect(salesInvoicesApi.reissueTransferRemission).toHaveBeenCalledExactlyOnceWith('tr-1');
  expect(await screen.findByText('Emitiendo')).toBeInTheDocument();
  expect(screen.getByText(/Se está emitiendo ante Hacienda/)).toBeInTheDocument();
});

it('sin la nota habilitada no muestra nada; sin nota avisa que salió sin ella', async () => {
  salesInvoicesApi.transferRemission.mockResolvedValue({ enabled: false, document: null });
  const { unmount } = render(TransferRemissionCard, {
    transferId: 'tr-1',
    canReissue: true,
    canOpenDocument: true
  });
  await vi.waitFor(() => expect(salesInvoicesApi.transferRemission).toHaveBeenCalled());
  expect(screen.queryByText('Nota de remisión')).not.toBeInTheDocument();
  unmount();

  salesInvoicesApi.transferRemission.mockResolvedValue({ enabled: true, document: null });
  render(TransferRemissionCard, { transferId: 'tr-2', canReissue: true, canOpenDocument: true });
  expect(
    await screen.findByText(/salió sin nota de remisión: se despachó antes de habilitarla/)
  ).toBeInTheDocument();
});
