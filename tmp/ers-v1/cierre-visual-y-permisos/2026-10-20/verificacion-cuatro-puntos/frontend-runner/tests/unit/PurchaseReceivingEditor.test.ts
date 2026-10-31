import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseReceivingEditor from '$lib/features/purchases/components/PurchaseReceivingEditor.svelte';

const mocks = vi.hoisted(() => ({
  getReceivable: vi.fn(),
  create: vi.fn(),
  listUnits: vi.fn(),
  getProduct: vi.fn(),
  goto: vi.fn()
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    getReceivable: mocks.getReceivable,
    create: mocks.create
  }
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    listUnits: mocks.listUnits,
    getProduct: mocks.getProduct
  }
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: vi.fn(() => true)
  }
}));

const receivable = {
  purchase_order_id: '11111111-1111-1111-1111-111111111111',
  code: 'OC-0001',
  status: 'sent',
  supplier_id: 25,
  branch_id: '22222222-2222-2222-2222-222222222222',
  warehouse_id: '33333333-3333-3333-3333-333333333333',
  currency: 'USD',
  lines: [
    {
      purchase_order_detail_id: '44444444-4444-4444-4444-444444444444',
      product_id: 10,
      unit_id: 3,
      quantity_ordered: '5.000000',
      quantity_received: '1.000000',
      quantity_pending: '4.000000',
      unit_price: '12.500000',
      discount: '0.000000',
      tax_rate: '13.000000',
      notes: null
    }
  ]
} as const;

describe('PurchaseReceivingEditor', () => {
  beforeEach(() => {
    mocks.getReceivable.mockReset();
    mocks.create.mockReset();
    mocks.listUnits.mockReset();
    mocks.getProduct.mockReset();
    mocks.goto.mockReset();

    mocks.getReceivable.mockResolvedValue(receivable);
    mocks.create.mockResolvedValue({});
    mocks.listUnits.mockResolvedValue([
      {
        id_unit: 3,
        code: 'UND',
        name: 'Unidad'
      }
    ]);
    mocks.getProduct.mockResolvedValue({
      id_product: 10,
      sku: 'SKU-001',
      name: 'Producto E2E'
    });
  });

  it('shows ordered, received and pending quantities and creates a partial draft', async () => {
    render(PurchaseReceivingEditor, {
      props: {
        orderId: receivable.purchase_order_id
      }
    });

    expect(await screen.findByText(/OC-0001/)).toBeInTheDocument();
    expect(await screen.findByText('SKU-001 — Producto E2E')).toBeInTheDocument();

    expect(screen.getByText('Ordenado')).toBeInTheDocument();
    expect(screen.getByText('Recibido')).toBeInTheDocument();
    expect(screen.getByText('Pendiente')).toBeInTheDocument();

    const quantityInput = await screen.findByRole('spinbutton', {
      name: /Cantidad a recibir/
    });

    await fireEvent.input(quantityInput, {
      target: { value: '2' }
    });

    await fireEvent.input(screen.getByPlaceholderText('Ej. FAC-00125'), {
      target: { value: 'FAC-900' }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));

    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith({
        purchase_order_id: receivable.purchase_order_id,
        supplier_invoice_number: 'FAC-900',
        supplier_invoice_date: null,
        lines: [
          {
            purchase_order_detail_id: '44444444-4444-4444-4444-444444444444',
            quantity_received: 2
          }
        ],
        notes: null
      });
    });

    expect(mocks.goto).toHaveBeenCalledWith('/purchases');
  });

  it('requires at least one positive received quantity', async () => {
    render(PurchaseReceivingEditor, {
      props: {
        orderId: receivable.purchase_order_id
      }
    });

    expect(await screen.findByText(/OC-0001/)).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ingresa una cantidad mayor que cero en al menos una línea.'
    );

    expect(mocks.create).not.toHaveBeenCalled();
  });
});
