import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { salesInvoicesApi } = vi.hoisted(() => ({
  salesInvoicesApi: { notes: vi.fn(), creditNote: vi.fn(), debitNote: vi.fn() }
}));

vi.mock('#lib/api/sales-invoices.ts', () => ({ salesInvoicesApi }));
vi.mock('#lib/api/client.ts', () => ({
  HttpError: class HttpError extends Error {
    constructor(
      readonly code: string,
      message: string,
      readonly status: number
    ) {
      super(message);
    }
  }
}));

import { HttpError } from '#lib/api/client.ts';
import type { FiscalDocument, NotesOverview } from '#lib/types/sales-invoices.ts';
import FiscalNotesPanel from './FiscalNotesPanel.svelte';

const CCF = { id: 'ccf-1', status: 'simulated', document_type: '03' } as unknown as FiscalDocument;

function overview(overrides: Partial<NotesOverview> = {}): NotesOverview {
  return {
    ccf_id: 'ccf-1',
    credit_deadline: '2027-02-18',
    withholding: true,
    perception: false,
    credit_blocker: null,
    debit_blocker: null,
    lines: [
      {
        number: 1,
        code: 'CAM-1',
        description: 'Camiseta',
        nature: 'taxed',
        quantity: '4',
        unit_price: '10',
        net: '40.00',
        returned: '0',
        credited: '0',
        remaining_quantity: '4',
        remaining_amount: '40.00'
      }
    ],
    notes: [],
    ...overrides
  };
}

beforeEach(() => {
  for (const fn of Object.values(salesInvoicesApi)) fn.mockReset();
});

it('emite una nota de crédito por devolución con el total estimado y la retención', async () => {
  salesInvoicesApi.notes.mockResolvedValue(overview());
  salesInvoicesApi.creditNote.mockResolvedValue({ id: 'nc-1' });
  render(FiscalNotesPanel, { document: CCF, canIssue: true });

  expect(await screen.findByText(/hasta el 18\/02\/2027/)).toBeInTheDocument();
  expect(screen.getByText('Este crédito fiscal no tiene notas.')).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Emitir nota de crédito' }));
  const submit = screen.getByRole('button', { name: 'Emitir nota de crédito' });
  expect(submit).toBeDisabled();

  await fireEvent.change(screen.getByLabelText('Ajuste de la línea 1'), {
    target: { value: 'return' }
  });
  await fireEvent.input(screen.getByLabelText('Cantidad devuelta de la línea 1'), {
    target: { value: '1' }
  });
  await fireEvent.input(screen.getByLabelText('Motivo de la nota'), {
    target: { value: 'Devolución de una camiseta' }
  });
  // $10.00 + IVA $1.30 − retención $0.10
  expect(screen.getByText('$11.20')).toBeInTheDocument();
  expect(submit).toBeEnabled();
  await fireEvent.click(submit);

  expect(salesInvoicesApi.creditNote).toHaveBeenCalledExactlyOnceWith('ccf-1', {
    reason: 'Devolución de una camiseta',
    lines: [{ ccf_line_number: 1, kind: 'return', quantity: '1' }]
  });
  expect(await screen.findByText(/Se está emitiendo la nota de crédito/)).toBeInTheDocument();
});

it('emite una nota de débito con un cargo libre exento', async () => {
  salesInvoicesApi.notes.mockResolvedValue(overview({ withholding: false }));
  salesInvoicesApi.debitNote.mockResolvedValue({ id: 'nd-1' });
  render(FiscalNotesPanel, { document: CCF, canIssue: true });
  await fireEvent.click(await screen.findByRole('button', { name: 'Emitir nota de débito' }));

  await fireEvent.input(screen.getByLabelText('Cargo 1: descripción'), {
    target: { value: 'Flete' }
  });
  await fireEvent.input(screen.getByLabelText('Cargo 1: precio unitario sin IVA'), {
    target: { value: '5' }
  });
  await fireEvent.change(screen.getByLabelText('Cargo 1: tipo de venta'), {
    target: { value: 'exempt' }
  });
  await fireEvent.input(screen.getByLabelText('Motivo de la nota'), {
    target: { value: 'Flete no cobrado' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Emitir nota de débito' }));

  expect(salesInvoicesApi.debitNote).toHaveBeenCalledExactlyOnceWith('ccf-1', {
    reason: 'Flete no cobrado',
    charges: [
      {
        description: 'Flete',
        quantity: '1',
        unit_price: '5',
        ccf_line_number: null,
        nature: 'exempt'
      }
    ]
  });
});

it('muestra el plazo vencido, las notas y el error del servidor', async () => {
  salesInvoicesApi.notes.mockResolvedValue(
    overview({
      credit_blocker: 'El plazo de la nota de crédito venció el 02/04/2026.',
      notes: [
        {
          document: {
            id: 'nd-1',
            document_type: '06',
            status: 'simulated',
            control_number: 'DTE-06-M001P001-000000000000001',
            total: '5.65',
            note_reason: 'Intereses'
          } as unknown as FiscalDocument,
          lines: [
            {
              line_number: 1,
              ccf_line_number: null,
              kind: 'charge',
              nature: 'taxed',
              description: 'Intereses',
              quantity: '1',
              amount: '5.00'
            }
          ]
        }
      ]
    })
  );
  salesInvoicesApi.debitNote.mockRejectedValue(
    new HttpError('sales_note_charge_invalid', 'Cargo 1: describe el cargo.', 422)
  );
  render(FiscalNotesPanel, { document: CCF, canIssue: true });

  expect(await screen.findByText(/venció el 02\/04\/2026/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Emitir nota de crédito' })).toBeDisabled();
  expect(
    screen.getByRole('link', { name: /Nota de débito DTE-06-M001P001-000000000000001/ })
  ).toHaveAttribute('href', '/sales/fiscal-documents/nd-1');
  expect(screen.getByText(/Intereses · Cargo: \$5.00/)).toBeInTheDocument();

  await fireEvent.click(screen.getByRole('button', { name: 'Emitir nota de débito' }));
  await fireEvent.input(screen.getByLabelText('Cargo 1: descripción'), {
    target: { value: 'Intereses' }
  });
  await fireEvent.input(screen.getByLabelText('Cargo 1: precio unitario sin IVA'), {
    target: { value: '3' }
  });
  await fireEvent.input(screen.getByLabelText('Motivo de la nota'), {
    target: { value: 'Intereses por mora' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Emitir nota de débito' }));
  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent('Cargo 1: describe el cargo.')
  );
});

it('sin permiso solo consulta el saldo', async () => {
  salesInvoicesApi.notes.mockResolvedValue(overview());
  render(FiscalNotesPanel, { document: CCF, canIssue: false });
  expect(await screen.findByText('Camiseta', { exact: false })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Emitir/ })).not.toBeInTheDocument();
});
