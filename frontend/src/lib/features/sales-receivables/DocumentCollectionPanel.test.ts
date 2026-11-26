import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { salesReceivablesApi } = vi.hoisted(() => ({
  salesReceivablesApi: {
    document: vi.fn(),
    account: vi.fn(),
    apply: vi.fn(),
    recordCertificate: vi.fn()
  }
}));
vi.mock('#lib/api/sales-receivables.ts', () => ({ salesReceivablesApi }));
vi.mock('#lib/stores/branch.svelte.ts', () => ({
  branch: { id: 'branch-1', branches: [{ id: 'branch-1', name: 'Matriz' }] }
}));

import type { AccountDocument, Receipt } from '#lib/types/sales-receivables.ts';
import DocumentCollectionPanel from './DocumentCollectionPanel.svelte';

const DOCUMENT: AccountDocument = {
  id: 'doc-2',
  document_type: '03',
  control_number: 'DTE-03-M001P001-000000000000002',
  issued_on: '2026-11-25',
  due_on: '2026-12-10',
  payable: '50.00',
  credited: '0.00',
  applied: '0.00',
  balance: '50.00',
  bucket: 'current',
  overdue: false,
  invalidated: false,
  sale_id: 'sale-2',
  sale_code: 'PED-2',
  customer_id: 'cust-1',
  withholding: '0.00',
  certificate: null
};

const CREDIT: Receipt = {
  id: 'r-1',
  code: 'RC-000003',
  number: 3,
  branch_id: 'branch-1',
  customer_id: 'cust-1',
  received_on: '2026-11-25',
  total: '766.82',
  unapplied: '76.68',
  notes: null,
  status: 'issued',
  payments: [],
  applications: [],
  annul_reason: null,
  annulled_at: null,
  created_at: null,
  released: '76.68',
  refunds: []
};

function account(receipts: Receipt[]) {
  return {
    customer: { id: 'cust-1', code: 'CLI-1', name: 'Cliente', credit_days: 15, credit_limit: null },
    balance: '50.00',
    overdue: '0.00',
    credit: '76.68',
    aging: { current: '50.00', '1_30': '0', '31_60': '0', '61_90': '0', over_90: '0' },
    documents: [DOCUMENT],
    receipts
  };
}

beforeEach(() => {
  for (const fn of Object.values(salesReceivablesApi)) fn.mockReset();
});

it('aplica el saldo a favor del cliente hasta el saldo del documento', async () => {
  salesReceivablesApi.document
    .mockResolvedValueOnce(DOCUMENT)
    .mockResolvedValueOnce({ ...DOCUMENT, applied: '50.00', balance: '0.00' });
  salesReceivablesApi.account.mockResolvedValue(
    account([CREDIT, { ...CREDIT, id: 'r-2', code: 'RC-000001', status: 'annulled' }])
  );
  salesReceivablesApi.apply.mockResolvedValue(CREDIT);
  render(DocumentCollectionPanel, { documentId: 'doc-2', canCollect: true });

  expect(await screen.findByText('El cliente tiene saldo a favor')).toBeInTheDocument();
  expect(screen.queryByText(/RC-000001/)).not.toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Aplicar $50.00' }));
  expect(salesReceivablesApi.apply).toHaveBeenCalledWith('r-1', [
    { document_id: 'doc-2', amount: '50.00' }
  ]);
  expect(
    await screen.findByText('Se aplicó $50.00 del saldo a favor del recibo RC-000003.')
  ).toBeInTheDocument();
  expect(screen.queryByText('El cliente tiene saldo a favor')).not.toBeInTheDocument();
});

it('sin permiso de cobro no ofrece el saldo a favor', async () => {
  salesReceivablesApi.document.mockResolvedValue(DOCUMENT);
  render(DocumentCollectionPanel, { documentId: 'doc-2', canCollect: false });
  await screen.findByText('Cobro');
  expect(salesReceivablesApi.account).not.toHaveBeenCalled();
  expect(screen.queryByText('El cliente tiene saldo a favor')).not.toBeInTheDocument();
});
