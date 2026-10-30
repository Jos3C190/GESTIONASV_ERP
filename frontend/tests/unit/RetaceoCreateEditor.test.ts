import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RetaceoCreateEditor from '$lib/features/retaceos/components/RetaceoCreateEditor.svelte';
import type { Purchase } from '$lib/types/purchase';

const mocks = vi.hoisted(() => ({
  goto: vi.fn(),
  getPurchase: vi.fn(),
  create: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    get: mocks.getPurchase
  }
}));

vi.mock('$lib/api/retaceos', () => ({
  retaceosApi: {
    create: mocks.create
  }
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: { getProduct: vi.fn().mockResolvedValue({ id_product: 10, sku: 'PROD-10', name: 'Producto A' }) }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const purchase: Purchase = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'COM-0001',
  purchase_order_id: '22222222-2222-2222-2222-222222222222',
  supplier_id: 25,
  branch_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  warehouse_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
  created_by_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  purchase_date: '2026-09-20T12:00:00-06:00',
  supplier_invoice_number: 'FAC-001',
  supplier_invoice_date: '2026-09-20',
  currency: 'USD',
  details: [{
    id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
    purchase_id: '11111111-1111-1111-1111-111111111111',
    purchase_order_detail_id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
    product_id: 10,
    quantity_ordered: '2', quantity_received: '2', unit_id: 3,
    unit_price: '50', discount: '0', subtotal: '100', tax_rate: '13',
    tax_amount: '13', total: '113', notes: null, created_at: null, updated_at: null
  }],
  subtotal: '100.000000',
  discount: '0.000000',
  tax: '13.000000',
  total: '113.000000',
  status: 'verified',
  notes: null,
  created_at: null,
  updated_at: null
};

describe('RetaceoCreateEditor', () => {
  beforeEach(() => {
    mocks.goto.mockReset();
    mocks.getPurchase.mockReset();
    mocks.create.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:manage');
    mocks.getPurchase.mockResolvedValue(purchase);
  });

  it('creates a retaceo from the selected purchase and redirects to detail', async () => {
    mocks.create.mockResolvedValue({
      id: '99999999-9999-9999-9999-999999999999'
    });

    render(RetaceoCreateEditor, {
      props: { purchaseId: purchase.id }
    });

    expect(await screen.findByText('COM-0001')).toBeInTheDocument();
    expect(screen.getByText('Verificada')).toBeInTheDocument();

    await fireEvent.input(screen.getByLabelText('Notas'), {
      target: { value: 'Importación septiembre' }
    });
    await fillManualAmounts();

    await fireEvent.submit(screen.getByRole('button', { name: 'Crear retaceo' }).closest('form')!);

    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith({
        purchase_id: purchase.id,
        import_data: {
          origin_country: null, import_invoice_number: 'FAC-001',
          import_invoice_date: '2026-09-20', import_policy_number: null, import_policy_date: null
        },
        fob_lines: [{ purchase_detail_id: purchase.details[0]!.id, amount: '100' }],
        total_freight: '0',
        total_expenses: '0',
        total_dai: '0',
        import_vat: '0',
        notes: 'Importación septiembre'
      });
    });

    expect(mocks.goto).toHaveBeenCalledWith(
      '/retaceos/99999999-9999-9999-9999-999999999999/edit'
    );
  });

  it('does not load purchase data without retaceos:manage', async () => {
    mocks.hasPermission.mockReturnValue(false);

    render(RetaceoCreateEditor, {
      props: { purchaseId: purchase.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para gestionar retaceos.'
    );

    expect(mocks.getPurchase).not.toHaveBeenCalled();
  });

  it('shows backend creation errors', async () => {
    mocks.create.mockRejectedValue(new Error('La compra no es elegible para retaceo.'));

    render(RetaceoCreateEditor, {
      props: { purchaseId: purchase.id }
    });

    expect(await screen.findByText('COM-0001')).toBeInTheDocument();

    await fillManualAmounts();
    await fireEvent.submit(screen.getByRole('button', { name: 'Crear retaceo' }).closest('form')!);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'La compra no es elegible para retaceo.'
    );
  });
});

async function fillManualAmounts() {
  for (const label of ['Flete total (USD)', 'DAI total (USD)', 'IVA de importación (USD)']) {
    await fireEvent.input(screen.getByRole('spinbutton', { name: new RegExp(label.replace(/[()]/g, '\\$&')) }), { target: { value: '0' } });
  }
  await fireEvent.input(screen.getByRole('spinbutton', { name: /FOB total de la línea/ }), { target: { value: '100' } });
}
