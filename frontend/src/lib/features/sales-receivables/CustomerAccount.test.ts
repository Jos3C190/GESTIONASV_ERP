import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { salesReceivablesApi } = vi.hoisted(() => ({
  salesReceivablesApi: { account: vi.fn(), annul: vi.fn(), apply: vi.fn(), register: vi.fn() }
}));
vi.mock('#lib/api/sales-receivables.ts', () => ({ salesReceivablesApi }));
vi.mock('#lib/stores/branch.svelte.ts', () => ({
  branch: { id: 'branch-1', branches: [{ id: 'branch-1', name: 'Matriz' }] }
}));

import type { CustomerAccount, Receipt } from '#lib/types/sales-receivables.ts';
import CustomerAccountView from './CustomerAccount.svelte';

const RECEIPT: Receipt = {
  id: 'r-1',
  code: 'RC-000001',
  number: 1,
  branch_id: 'branch-1',
  customer_id: 'cust-1',
  received_on: '2026-11-20',
  total: '150.00',
  unapplied: '37.00',
  notes: null,
  status: 'issued',
  payments: [{ method: 'transfer', amount: '150.00', reference: 'TRF-9' }],
  applications: [
    {
      document_id: 'doc-1',
      control_number: 'DTE-03-M001P001-000000000000001',
      amount: '113.00',
      applied_on: '2026-11-20',
      document_invalidated: false
    }
  ],
  annul_reason: null,
  annulled_at: null,
  created_at: '2026-11-20T16:00:00Z'
};

function account(overrides: Partial<CustomerAccount> = {}): CustomerAccount {
  return {
    customer: {
      id: 'cust-1',
      code: 'CLI-1',
      name: 'Cafetería El Trigal',
      credit_days: 30,
      credit_limit: '1000.00'
    },
    balance: '50.00',
    overdue: '50.00',
    credit: '37.00',
    aging: { current: '0', '1_30': '50.00', '31_60': '0', '61_90': '0', over_90: '0' },
    documents: [
      {
        id: 'doc-2',
        document_type: '06',
        control_number: 'DTE-06-M001P001-000000000000001',
        issued_on: '2026-10-01',
        due_on: '2026-10-31',
        payable: '50.00',
        credited: '0.00',
        applied: '0.00',
        balance: '50.00',
        bucket: '1_30',
        overdue: true,
        invalidated: false,
        sale_id: 'sale-1',
        sale_code: 'PED-1',
        customer_id: 'cust-1',
        withholding: '0.00',
        certificate: null
      }
    ],
    receipts: [RECEIPT],
    ...overrides
  };
}

beforeEach(() => {
  for (const fn of Object.values(salesReceivablesApi)) fn.mockReset();
});

it('muestra saldos, antigüedad y recibos, y anula con motivo', async () => {
  salesReceivablesApi.account.mockResolvedValue(account());
  salesReceivablesApi.annul.mockResolvedValue({ ...RECEIPT, status: 'annulled' });
  render(CustomerAccountView, { customerId: 'cust-1', canCollect: true });

  expect(await screen.findByText('Cafetería El Trigal')).toBeInTheDocument();
  expect(screen.getByText('Saldo a favor $37.00')).toBeInTheDocument();
  expect(screen.getByText(/Transferencia \$150.00 \(TRF-9\)/)).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Anular' }));
  const confirm = screen.getByRole('button', { name: 'Anular recibo' });
  expect(confirm).toBeDisabled();
  await fireEvent.input(screen.getByLabelText('Motivo de la anulación'), {
    target: { value: 'Transferencia rechazada' }
  });
  await fireEvent.click(confirm);
  expect(salesReceivablesApi.annul).toHaveBeenCalledWith('r-1', 'Transferencia rechazada');
  expect(await screen.findByText(/Se anuló el recibo RC-000001/)).toBeInTheDocument();
});

it('aplica el saldo a favor a un documento abierto', async () => {
  salesReceivablesApi.account.mockResolvedValue(account());
  salesReceivablesApi.apply.mockResolvedValue({ ...RECEIPT, unapplied: '0.00' });
  render(CustomerAccountView, { customerId: 'cust-1', canCollect: true });

  await fireEvent.click(await screen.findByRole('button', { name: 'Aplicar saldo a favor' }));
  await fireEvent.input(
    screen.getByLabelText('Saldo a favor aplicado a DTE-06-M001P001-000000000000001'),
    { target: { value: '37' } }
  );
  await fireEvent.click(screen.getByRole('button', { name: 'Aplicar $37.00' }));
  expect(salesReceivablesApi.apply).toHaveBeenCalledWith('r-1', [
    { document_id: 'doc-2', amount: '37.00' }
  ]);
});

it('sin permiso de cobro solo consulta, y avisa si falla la carga', async () => {
  salesReceivablesApi.account.mockResolvedValue(account());
  render(CustomerAccountView, { customerId: 'cust-1', canCollect: false });
  await screen.findByText('Cafetería El Trigal');
  expect(screen.queryByRole('button', { name: 'Registrar cobro' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Anular' })).not.toBeInTheDocument();

  salesReceivablesApi.account.mockRejectedValue(new Error('down'));
  render(CustomerAccountView, { customerId: 'cust-2', canCollect: true });
  expect(await screen.findByText('No se pudo cargar el estado de cuenta.')).toBeInTheDocument();
});
