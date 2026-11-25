import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { salesReceivablesApi } = vi.hoisted(() => ({
  salesReceivablesApi: { register: vi.fn() }
}));
vi.mock('#lib/api/sales-receivables.ts', () => ({ salesReceivablesApi }));
vi.mock('#lib/stores/branch.svelte.ts', () => ({
  branch: { id: 'branch-1', branches: [{ id: 'branch-1', name: 'Matriz' }] }
}));

import type { AccountDocument, Receipt } from '#lib/types/sales-receivables.ts';
import ReceiptForm from './ReceiptForm.svelte';
import { todayLocal } from './labels.ts';

function document(overrides: Partial<AccountDocument> = {}): AccountDocument {
  return {
    id: 'doc-1',
    document_type: '03',
    control_number: 'DTE-03-M001P001-000000000000001',
    issued_on: '2026-10-01',
    due_on: '2026-10-31',
    payable: '113.00',
    credited: '0.00',
    applied: '0.00',
    balance: '113.00',
    bucket: '1_30',
    overdue: true,
    invalidated: false,
    sale_id: 'sale-1',
    sale_code: 'PED-1',
    customer_id: 'cust-1',
    withholding: '0.00',
    certificate: null,
    ...overrides
  };
}

beforeEach(() => salesReceivablesApi.register.mockReset());

it('registra un cobro mixto y lo aplica a los documentos más antiguos', async () => {
  salesReceivablesApi.register.mockResolvedValue({ id: 'r-1', code: 'RC-000001' } as Receipt);
  const onDone = vi.fn();
  render(ReceiptForm, {
    customerId: 'cust-1',
    documents: [
      document(),
      document({
        id: 'doc-2',
        control_number: 'DTE-03-M001P001-000000000000002',
        due_on: '2026-11-30',
        balance: '50.00'
      })
    ],
    onDone,
    onCancel: vi.fn()
  });

  await fireEvent.input(screen.getByLabelText('Monto del pago 1'), { target: { value: '100' } });
  await fireEvent.click(screen.getByRole('button', { name: 'Agregar forma de pago' }));
  await fireEvent.input(screen.getByLabelText('Monto del pago 2'), { target: { value: '30' } });
  // Sin referencia la tarjeta no se acepta.
  expect(screen.getByRole('button', { name: 'Registrar cobro' })).toBeDisabled();
  await fireEvent.input(screen.getByLabelText('Referencia del pago 2'), {
    target: { value: 'AUT-77' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Aplicar a los más antiguos' }));
  expect(screen.getByLabelText(/Monto aplicado a DTE-03-M001P001-000000000000001/)).toHaveValue(
    113
  );
  // Cobrado y aplicado: $130.00; saldo a favor en cero.
  expect(screen.getAllByText('$130.00')).toHaveLength(2);
  expect(screen.getByRole('button', { name: 'Registrar cobro' })).toBeEnabled();
  await fireEvent.submit(screen.getByRole('form', { name: 'Nuevo recibo de cobro' }));

  const payload = salesReceivablesApi.register.mock.calls[0]?.[0];
  expect(payload).toMatchObject({
    branch_id: 'branch-1',
    customer_id: 'cust-1',
    received_on: todayLocal(),
    payments: [
      { method: 'cash', amount: '100.00', reference: null },
      { method: 'card', amount: '30.00', reference: 'AUT-77' }
    ],
    applications: [
      { document_id: 'doc-1', amount: '113.00' },
      { document_id: 'doc-2', amount: '17.00' }
    ]
  });
  expect(payload.idempotency_key).toMatch(/^rc-/);
  expect(onDone).toHaveBeenCalled();
});

it('no deja aplicar más que el saldo del documento', async () => {
  render(ReceiptForm, {
    customerId: 'cust-1',
    documents: [document()],
    preset: { document_id: 'doc-1', amount: '113.00' },
    onDone: vi.fn(),
    onCancel: vi.fn()
  });
  await fireEvent.input(screen.getByLabelText(/Monto aplicado a/), { target: { value: '120' } });
  expect(screen.getByText(/pasa de su saldo/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Registrar cobro' })).toBeDisabled();
});
