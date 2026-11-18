import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { salesInvoicesApi } = vi.hoisted(() => ({
  salesInvoicesApi: { invalidation: vi.fn(), invalidate: vi.fn(), correct: vi.fn() }
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
import type { FiscalDocument, FiscalInvalidation } from '#lib/types/sales-invoices.ts';
import FiscalInvalidationPanel from './FiscalInvalidationPanel.svelte';

const DOCUMENT = {
  id: 'doc-1',
  status: 'simulated',
  document_type: '01',
  control_number: 'DTE-01-M001P001-000000000000001',
  replaces_document_id: null,
  superseded_by_id: null
} as unknown as FiscalDocument;

const REQUESTER = { name: 'María Rivas', document_type: '13', document_number: '04567890-1' };

function invalidation(overrides: Partial<FiscalInvalidation> = {}): FiscalInvalidation {
  return {
    id: 'inv-1',
    document_id: 'doc-1',
    kind: 2,
    reason: 'El cliente desistió',
    requester: REQUESTER,
    responsible: null,
    replacement_document_id: null,
    cancel_order: false,
    status: 'accepted',
    attempts: 1,
    event_generation_code: 'EVT',
    event_seal: 'SIMULATED-INVALIDATION-1234',
    error_code: null,
    error_message: null,
    created_at: '2026-11-18T16:00:00Z',
    resolved_at: '2026-11-18T16:01:00Z',
    ...overrides
  };
}

async function fillRequester() {
  await fireEvent.input(screen.getByLabelText('Nombre del solicitante'), {
    target: { value: REQUESTER.name }
  });
  await fireEvent.input(screen.getByLabelText('Número de documento del solicitante'), {
    target: { value: REQUESTER.document_number }
  });
}

beforeEach(() => {
  for (const fn of Object.values(salesInvoicesApi)) fn.mockReset();
});

it('anula con motivo y solicitante, y muestra la solicitud', async () => {
  salesInvoicesApi.invalidation
    .mockResolvedValueOnce({
      deadline: '2027-02-18',
      expired: false,
      estimated: false,
      history: []
    })
    .mockResolvedValue({
      deadline: '2027-02-18',
      expired: false,
      estimated: false,
      history: [invalidation({ status: 'pending', event_seal: null })]
    });
  salesInvoicesApi.invalidate.mockResolvedValue(invalidation({ status: 'pending' }));
  const onChanged = vi.fn();
  render(FiscalInvalidationPanel, { document: DOCUMENT, canInvalidate: true, onChanged });

  expect(
    await screen.findByText(/Se puede anular o corregir hasta el 18\/02\/2027/)
  ).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Anular documento' }));
  await fireEvent.input(screen.getByLabelText('Motivo de la anulación'), {
    target: { value: 'El cliente desistió' }
  });
  await fillRequester();
  await fireEvent.click(screen.getByRole('button', { name: 'Anular ante Hacienda' }));

  expect(salesInvoicesApi.invalidate).toHaveBeenCalledExactlyOnceWith('doc-1', {
    reason: 'El cliente desistió',
    requester: REQUESTER
  });
  expect(await screen.findByText(/Se pidió la anulación a Hacienda/)).toBeInTheDocument();
  expect(await screen.findByText('En proceso')).toBeInTheDocument();
  expect(onChanged).toHaveBeenCalled();
  // Con una solicitud en curso ya no se ofrece otra.
  expect(screen.queryByRole('button', { name: 'Anular documento' })).not.toBeInTheDocument();
});

it('corrige con un reemplazo y muestra el error de la API', async () => {
  salesInvoicesApi.invalidation.mockResolvedValue({
    deadline: '2026-12-10',
    expired: false,
    estimated: true,
    history: []
  });
  salesInvoicesApi.correct.mockRejectedValue(
    new HttpError('sales_invoice_responsible_missing', 'Registra al responsable fiscal.', 422)
  );
  render(FiscalInvalidationPanel, { document: DOCUMENT, canInvalidate: true });

  expect(await screen.findByText(/fecha estimada por los feriados/)).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Corregir documento' }));
  expect(screen.queryByLabelText('Motivo de la anulación')).not.toBeInTheDocument();
  await fillRequester();
  await fireEvent.click(screen.getByRole('button', { name: 'Emitir reemplazo' }));
  expect(salesInvoicesApi.correct).toHaveBeenCalledExactlyOnceWith('doc-1', REQUESTER);
  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent('Registra al responsable fiscal.')
  );
});

it('no ofrece acciones vencido, sin permiso o con un reemplazo en curso', async () => {
  salesInvoicesApi.invalidation.mockResolvedValue({
    deadline: '2026-08-01',
    expired: true,
    estimated: false,
    history: [invalidation({ status: 'rejected', error_message: 'Fuera de plazo' })]
  });
  const { unmount } = render(FiscalInvalidationPanel, { document: DOCUMENT, canInvalidate: true });
  expect(await screen.findByText(/venció el 01\/08\/2026/)).toBeInTheDocument();
  expect(screen.getByText('Fuera de plazo')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Anular documento' })).not.toBeInTheDocument();
  unmount();

  salesInvoicesApi.invalidation.mockResolvedValue({
    deadline: '2027-02-18',
    expired: false,
    estimated: false,
    history: []
  });
  render(FiscalInvalidationPanel, {
    document: { ...DOCUMENT, superseded_by_id: 'doc-2' } as FiscalDocument,
    canInvalidate: true
  });
  expect(await screen.findByText(/Se está corrigiendo con/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Corregir documento' })).not.toBeInTheDocument();
});

it('un documento ya invalidado enlaza al que lo reemplaza', async () => {
  salesInvoicesApi.invalidation.mockResolvedValue({
    deadline: null,
    expired: false,
    estimated: false,
    history: [invalidation({ kind: 1 })]
  });
  render(FiscalInvalidationPanel, {
    document: { ...DOCUMENT, status: 'invalidated', superseded_by_id: 'doc-2' } as FiscalDocument,
    canInvalidate: true
  });
  expect(await screen.findByText('Aceptada')).toBeInTheDocument();
  expect(screen.getByText(/Se invalidó y lo reemplaza/)).toBeInTheDocument();
  expect(screen.queryByText(/Se está corrigiendo/)).not.toBeInTheDocument();
});
