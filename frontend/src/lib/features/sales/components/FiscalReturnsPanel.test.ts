import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { salesInvoicesApi } = vi.hoisted(() => ({
  salesInvoicesApi: {
    returns: vi.fn(),
    registerReturn: vi.fn(),
    annulReturn: vi.fn(),
    returnPdf: vi.fn(),
    returnJson: vi.fn()
  }
}));
vi.mock('#lib/api/sales-invoices.ts', () => ({ salesInvoicesApi }));

import type { FiscalDocument, FiscalReturn, ReturnsOverview } from '#lib/types/sales-invoices.ts';
import FiscalReturnsPanel from './FiscalReturnsPanel.svelte';

const INVOICE = { id: 'fe-1', document_type: '01', status: 'simulated' } as FiscalDocument;
const LINE = {
  number: 1,
  code: 'PRD-HAR-001',
  description: 'Harina 50 lb',
  nature: 'taxed' as const,
  quantity: '4',
  unit_price: '22.6',
  net: '81.36',
  returned: '0',
  credited: '0',
  remaining_quantity: '4',
  remaining_amount: '81.36'
};

function item(overrides: Partial<FiscalReturn> = {}): FiscalReturn {
  return {
    id: 'ret-1',
    document_id: 'fe-1',
    reason: 'Cliente devolvió una bolsa',
    status: 'simulated',
    total: '20.34',
    generation_code: 'ABC',
    seal: 'SIMULATED-EVT-1',
    error_code: null,
    error_message: null,
    issued_at: '2026-11-25T16:00:00Z',
    has_json: true,
    lines: [
      {
        line_number: 1,
        invoice_line_number: 1,
        nature: 'taxed',
        description: 'Harina 50 lb',
        quantity: '1',
        amount: '20.34',
        vat: '2.34'
      }
    ],
    annul_status: null,
    annul_requester: null,
    annul_seal: null,
    annul_error_code: null,
    annul_error_message: null,
    annulled_at: null,
    created_at: '2026-11-25T16:00:00Z',
    ...overrides
  };
}

function overview(overrides: Partial<ReturnsOverview> = {}): ReturnsOverview {
  return {
    invoice_id: 'fe-1',
    deadline: '2027-02-25',
    withholding: false,
    blocker: null,
    lines: [LINE],
    returns: [],
    ...overrides
  };
}

beforeEach(() => {
  for (const fn of Object.values(salesInvoicesApi)) fn.mockReset();
});

it('registra un retorno por cantidad con el total estimado e IVA incluido', async () => {
  salesInvoicesApi.returns
    .mockResolvedValueOnce(overview())
    .mockResolvedValue(overview({ returns: [item({ status: 'pending' })] }));
  salesInvoicesApi.registerReturn.mockResolvedValue(item({ status: 'pending' }));
  render(FiscalReturnsPanel, { document: INVOICE, canReturn: true });

  expect(
    await screen.findByText('Se pueden registrar retornos hasta el 25/02/2027.')
  ).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Registrar retorno' }));
  await fireEvent.input(screen.getByLabelText('Cantidad devuelta de la línea 1'), {
    target: { value: '1' }
  });
  await fireEvent.input(screen.getByLabelText('Motivo del retorno'), {
    target: { value: 'Cliente devolvió una bolsa' }
  });
  expect(screen.getAllByText('$20.34').length).toBeGreaterThan(0);
  expect(screen.getByText('$2.34')).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Registrar ante Hacienda' }));
  expect(salesInvoicesApi.registerReturn).toHaveBeenCalledExactlyOnceWith('fe-1', {
    reason: 'Cliente devolvió una bolsa',
    lines: [{ invoice_line_number: 1, quantity: '1' }]
  });
  expect(await screen.findByText(/Se registró el retorno/)).toBeInTheDocument();
  expect(await screen.findByText('Transmitiendo')).toBeInTheDocument();
});

it('anula un retorno vigente con el solicitante', async () => {
  salesInvoicesApi.returns
    .mockResolvedValueOnce(overview({ returns: [item()] }))
    .mockResolvedValue(overview({ returns: [item({ annul_status: 'pending' })] }));
  salesInvoicesApi.annulReturn.mockResolvedValue(item({ annul_status: 'pending' }));
  render(FiscalReturnsPanel, { document: INVOICE, canReturn: true });

  await fireEvent.click(await screen.findByRole('button', { name: 'Anular retorno' }));
  await fireEvent.input(screen.getByLabelText('Nombre del solicitante'), {
    target: { value: 'María Rivas' }
  });
  await fireEvent.input(screen.getByLabelText('Número de documento del solicitante'), {
    target: { value: '04567890-1' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Anular ante Hacienda' }));
  expect(salesInvoicesApi.annulReturn).toHaveBeenCalledExactlyOnceWith('ret-1', {
    name: 'María Rivas',
    document_type: '13',
    document_number: '04567890-1'
  });
  expect(await screen.findByText('Anulación en curso ante Hacienda.')).toBeInTheDocument();
});

it('muestra el bloqueo y no ofrece registrar sin permiso', async () => {
  salesInvoicesApi.returns.mockResolvedValue(
    overview({ blocker: 'El plazo para registrar retornos de esta factura venció.' })
  );
  render(FiscalReturnsPanel, { document: INVOICE, canReturn: true });
  expect(await screen.findByText(/venció/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Registrar retorno' })).toBeDisabled();

  salesInvoicesApi.returns.mockResolvedValue(overview({ returns: [item()] }));
  render(FiscalReturnsPanel, { document: INVOICE, canReturn: false });
  expect((await screen.findAllByText('Simulado')).length).toBeGreaterThan(0);
  expect(screen.queryByRole('button', { name: 'Anular retorno' })).not.toBeInTheDocument();
});
