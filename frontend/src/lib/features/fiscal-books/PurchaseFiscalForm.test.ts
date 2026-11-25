import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { fiscalBooksApi } = vi.hoisted(() => ({
  fiscalBooksApi: { purchase: vi.fn(), recordPurchase: vi.fn() }
}));
vi.mock('#lib/api/fiscal-books.ts', () => ({ fiscalBooksApi }));

import type { PurchaseFiscal } from '#lib/types/fiscal-books.ts';
import PurchaseFiscalForm from './PurchaseFiscalForm.svelte';

function purchase(overrides: Partial<PurchaseFiscal> = {}): PurchaseFiscal {
  return {
    id: 'p-1',
    code: 'COM-00001',
    status: 'verified',
    supplier_name: 'Harinas de El Salvador S.A. de C.V.',
    supplier_ids: { nrc: '123456' },
    invoice_number: 'F-100',
    invoice_date: '2026-11-08',
    exempt: '0.00',
    taxed: '1850.00',
    vat: '240.50',
    recorded: null,
    recorded_at: null,
    renta_defaults: { operation: 1, classification: 1, sector: 2, cost_type: 5 },
    ...overrides
  };
}

beforeEach(() => {
  fiscalBooksApi.purchase.mockReset();
  fiscalBooksApi.recordPurchase.mockReset();
});

it('registra un crédito fiscal de imprenta con el proveedor y la renta por defecto', async () => {
  fiscalBooksApi.purchase.mockResolvedValue(purchase());
  const saved = purchase({
    recorded: {
      issued_on: '2026-11-08',
      document_class: 1,
      document_type: '03',
      number: '145501',
      control_number: null,
      seal: null,
      supplier_name: 'Harinas de El Salvador S.A. de C.V.',
      supplier_id_type: 'nrc',
      supplier_id: '123456',
      renta: { operation: 1, classification: 1, sector: 2, cost_type: 5 }
    }
  });
  fiscalBooksApi.recordPurchase.mockResolvedValue(saved);
  const onSaved = vi.fn();
  render(PurchaseFiscalForm, { purchaseId: 'p-1', canManage: true, onSaved });

  expect(await screen.findByText('$240.50')).toBeInTheDocument();
  expect(screen.getByLabelText('Clase de documento')).toHaveValue('4');
  // Un DTE pide número de control y sello; uno de imprenta no.
  expect(screen.getByLabelText('Número de control')).toBeInTheDocument();
  await fireEvent.change(screen.getByLabelText('Clase de documento'), { target: { value: '1' } });
  expect(screen.queryByLabelText('Número de control')).not.toBeInTheDocument();
  await fireEvent.input(screen.getByLabelText('Número del documento'), {
    target: { value: '145501' }
  });
  expect(screen.getByLabelText('Número de identificación')).toHaveValue('123456');
  expect(screen.getByLabelText('Tipo de operación')).toHaveValue('1');
  expect(screen.getByLabelText('Tipo de costo o gasto')).toHaveValue('5');
  await fireEvent.click(screen.getByRole('button', { name: 'Guardar documento' }));

  expect(fiscalBooksApi.recordPurchase).toHaveBeenCalledExactlyOnceWith('p-1', {
    issued_on: '2026-11-08',
    document_class: 1,
    document_type: '03',
    number: '145501',
    control_number: null,
    seal: null,
    supplier_name: 'Harinas de El Salvador S.A. de C.V.',
    supplier_id_type: 'nrc',
    supplier_id: '123456',
    renta: { operation: 1, classification: 1, sector: 2, cost_type: 5 }
  });
  expect(await screen.findByText(/ya entra al libro de compras/)).toBeInTheDocument();
  expect(onSaved).toHaveBeenCalledWith(saved);
  expect(screen.getByRole('button', { name: 'Corregir documento' })).toBeInTheDocument();
});

it('sin permiso solo informa que falta el documento', async () => {
  fiscalBooksApi.purchase.mockResolvedValue(purchase());
  render(PurchaseFiscalForm, { purchaseId: 'p-1', canManage: false });
  expect(await screen.findByText(/todavía no tiene registrado/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Guardar documento' })).not.toBeInTheDocument();
});
