import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseOrderEditor from '$lib/features/purchase-orders/components/PurchaseOrderEditor.svelte';

const mocks = vi.hoisted(() => ({
  getQuotation: vi.fn(),
  createOrder: vi.fn(),
  createFromConsolidation: vi.fn(),
  getConsolidation: vi.fn(),
  getAwardBoard: vi.fn(),
  listExpenseTypes: vi.fn(),
  getSupplier: vi.fn(),
  getProduct: vi.fn(),
  listUnits: vi.fn(),
  getWarehouses: vi.fn(),
  goto: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchase-quotations', () => ({
  purchaseQuotationsApi: {
    get: mocks.getQuotation
  }
}));

vi.mock('$lib/api/purchase-orders', () => ({
  purchaseOrdersApi: {
    create: mocks.createOrder,
    createFromConsolidation: mocks.createFromConsolidation,
    listExpenseTypes: mocks.listExpenseTypes
  }
}));

vi.mock('$lib/api/purchase-consolidations', () => ({
  purchaseConsolidationsApi: {
    get: mocks.getConsolidation,
    getAwardBoard: mocks.getAwardBoard
  }
}));

vi.mock('$lib/api/suppliers', () => ({
  suppliersApi: {
    getSupplier: mocks.getSupplier
  }
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    getProduct: mocks.getProduct,
    listUnits: mocks.listUnits
  }
}));

vi.mock('$lib/services/warehouses', () => ({
  getWarehouses: mocks.getWarehouses
}));

vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    branches: [
      {
        id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        company_id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
        name: 'Sucursal Centro',
        code: 'CENTRO',
        is_active: true
      }
    ]
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const quotation = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
  code: 'CQ-0007',
  supplier_id: 25,
  quotation_date: '2026-09-13T12:00:00-06:00',
  currency: 'USD',
  created_by_id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
  request_links: [],
  details: [
    {
      id: '22222222-2222-2222-2222-222222222222',
      purchase_quotation_id: '11111111-1111-1111-1111-111111111111',
      product_id: 10,
      unit_id: 2,
      quantity: '5.000000',
      unit_price: '12.500000',
      discount: '0.000000',
      subtotal: '62.500000',
      tax_rate: '13.000000',
      tax_amount: '8.125000',
      total: '70.625000',
      delivery_days: 3,
      available_quantity: '5.000000',
      notes: null,
      created_at: null,
      updated_at: null
    },
    {
      id: '33333333-3333-3333-3333-333333333333',
      purchase_quotation_id: '11111111-1111-1111-1111-111111111111',
      product_id: 20,
      unit_id: 2,
      quantity: '3.000000',
      unit_price: '8.000000',
      discount: '0.000000',
      subtotal: '24.000000',
      tax_rate: '13.000000',
      tax_amount: '3.120000',
      total: '27.120000',
      delivery_days: 3,
      available_quantity: null,
      notes: null,
      created_at: null,
      updated_at: null
    }
  ],
  expenses: [
    {
      id: '77777777-7777-7777-7777-777777777777',
      purchase_quotation_id: '11111111-1111-1111-1111-111111111111',
      expense_type_id: '88888888-8888-8888-8888-888888888888',
      amount: '15.000000',
      description: 'Flete cotizado',
      created_at: null,
      updated_at: null
    }
  ],
  valid_until: null,
  payment_terms: '30 días',
  delivery_days: 3,
  subtotal: '86.500000',
  discount: '0.000000',
  tax: '11.245000',
  total: '112.745000',
  status: 'selected',
  notes: null,
  created_at: null,
  updated_at: null
} as const;

const createdOrder = {
  id: '99999999-9999-9999-9999-999999999999'
};

const consolidationId = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
const centralWarehouseId = 'cccccccc-cccc-cccc-cccc-cccccccccccc';
const consolidationQuotation = {
  ...quotation,
  consolidation_id: consolidationId,
  status: 'under_evaluation' as const
};
const consolidationBoard = {
  consolidation_id: consolidationId,
  consolidation_code: 'CD-00002',
  currencies: ['USD'],
  lines: [
    {
      id: '44444444-4444-4444-4444-444444444444',
      product_id: 10,
      product_sku: 'PROD-10',
      product_name: 'Producto A',
      unit_id: 2,
      unit_name: 'Unidad',
      demand_quantity: '8.000000',
      awarded_quantity: '4.000000',
      remaining_quantity: '4.000000',
      offers: [
        {
          quotation_id: quotation.id,
          quotation_code: 'CQ-0007',
          quotation_version: 1,
          supplier_id: 25,
          quotation_status: 'under_evaluation',
          currency: 'USD',
          valid_until: null,
          delivery_days: 3,
          payment_terms: '30 días',
          quotation_total: '70.625000',
          quotation_expenses_total: '15.000000',
          quotation_detail_id: quotation.details[0].id,
          requested_quantity: '8.000000',
          offered_quantity: '5.000000',
          available_quantity: '4.000000',
          awarded_quantity: '4.000000',
          remaining_offer_quantity: '0.000000',
          unit_price: '12.500000',
          discount: '0.000000',
          subtotal: '62.500000',
          tax_rate: '13.000000',
          tax_amount: '8.125000',
          line_total: '70.625000',
          line_delivery_days: 3,
          notes: null,
          can_award: false,
          blocked_reason: null
        }
      ],
      decisions: [
        {
          id: '55555555-5555-5555-5555-555555555555',
          quotation_id: quotation.id,
          quotation_code: 'CQ-0007',
          supplier_id: 25,
          quantity: '4.000000',
          reason: 'Entrega confirmada',
          decided_by_id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
          created_at: '2026-10-05T12:00:00Z',
          revoked_at: null,
          revoked_by_id: null,
          revocation_reason: null,
          ordered_quantity: '1.000000',
          remaining_to_order_quantity: '3.000000'
        }
      ]
    }
  ]
};

describe('PurchaseOrderEditor', () => {
  beforeEach(() => {
    mocks.getQuotation.mockReset();
    mocks.createOrder.mockReset();
    mocks.createFromConsolidation.mockReset();
    mocks.getConsolidation.mockReset();
    mocks.getAwardBoard.mockReset();
    mocks.listExpenseTypes.mockReset();
    mocks.getSupplier.mockReset();
    mocks.getProduct.mockReset();
    mocks.listUnits.mockReset();
    mocks.getWarehouses.mockReset();
    mocks.goto.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_orders:manage');
    mocks.getQuotation.mockResolvedValue(quotation);
    mocks.getConsolidation.mockResolvedValue({
      id: consolidationId,
      central_warehouse_id: centralWarehouseId
    });
    mocks.getAwardBoard.mockResolvedValue(consolidationBoard);
    mocks.listExpenseTypes.mockResolvedValue([
      {
        id: '88888888-8888-8888-8888-888888888888',
        name: 'Flete',
        description: 'Transporte de mercadería'
      }
    ]);
    mocks.getSupplier.mockResolvedValue({
      id_supplier: 25,
      code: 'PRV-025',
      name: 'Proveedor Central'
    });
    mocks.getProduct.mockImplementation((id: number) =>
      Promise.resolve({
        id_product: id,
        sku: `PROD-${id}`,
        name: id === 10 ? 'Producto A' : 'Producto B'
      })
    );
    mocks.listUnits.mockResolvedValue([
      {
        id_unit: 2,
        code: 'UND',
        name: 'Unidad',
        symbol: 'u'
      }
    ]);
    mocks.getWarehouses.mockResolvedValue({
      items: [
        {
          id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
          code: 'ALM-01',
          name: 'Almacén principal',
          branchId: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        },
        {
          id: centralWarehouseId,
          code: 'BM-001',
          name: 'Bodega madre Grupo Lorena',
          branchId: null,
          isCentral: true,
          status: 'active',
          storageEligible: true
        }
      ],
      meta: { page: 1, size: 100, total: 1, pages: 1 },
      summary: {}
    });
  });

  it('creates from selected quotation detail ids and allows a subset of lines', async () => {
    mocks.createOrder.mockResolvedValue(createdOrder);

    render(PurchaseOrderEditor, {
      props: { quotationId: quotation.id }
    });

    expect(await screen.findByText('Crear desde CQ-0007')).toBeInTheDocument();
    expect(await screen.findByText('PROD-10 — Producto A')).toBeInTheDocument();
    expect(screen.getByText(/PRV-025 — Proveedor Central/)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Crear orden' })).not.toBeDisabled();
    });

    await fireEvent.click(screen.getByLabelText('Incluir PROD-20 — Producto B'));
    await fireEvent.input(screen.getByLabelText('Cantidad a ordenar de PROD-10 — Producto A'), {
      target: { value: '2.5' }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Agregar gasto' }));
    expect(screen.getByRole('option', { name: 'Flete' })).toBeInTheDocument();
    await fireEvent.input(screen.getByLabelText('Monto gasto 1'), {
      target: { value: '15.25' }
    });
    await fireEvent.input(screen.getByLabelText('Descripción gasto 1'), {
      target: { value: 'Flete de la orden' }
    });

    await fireEvent.submit(screen.getByRole('button', { name: 'Crear orden' }).closest('form')!);

    await waitFor(() => {
      expect(mocks.createOrder).toHaveBeenCalledWith({
        purchase_quotation_id: quotation.id,
        branch_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        warehouse_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        expected_date: null,
        lines: [
          {
            purchase_quotation_detail_id: quotation.details[0].id,
            quantity: 2.5
          }
        ],
        expenses: [
          {
            expense_type_id: '88888888-8888-8888-8888-888888888888',
            amount: 15.25,
            description: 'Flete de la orden'
          }
        ],
        notes: null
      });
    });

    expect(mocks.goto).toHaveBeenCalledWith(`/purchase-orders/${createdOrder.id}`);
  });

  it('does not offer creation when the source quotation is not selected', async () => {
    mocks.getQuotation.mockResolvedValue({ ...quotation, status: 'received' });

    render(PurchaseOrderEditor, {
      props: { quotationId: quotation.id }
    });

    expect(
      await screen.findByText(
        'Solo una cotización seleccionada puede originar una orden de compra.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Crear orden' })).not.toBeInTheDocument();
    expect(mocks.createOrder).not.toHaveBeenCalled();
  });

  it('creates a consolidation order with server-derived pending award lines', async () => {
    mocks.getQuotation.mockResolvedValue(consolidationQuotation);
    mocks.createFromConsolidation.mockResolvedValue(createdOrder);

    render(PurchaseOrderEditor, {
      props: { quotationId: quotation.id, consolidationId }
    });

    expect(await screen.findByText('Cantidades adjudicadas')).toBeInTheDocument();
    const awardedCard = screen.getByRole('article', { name: 'PROD-10 — Producto A' });
    expect(within(awardedCard).getByText(/3\s+UND — Unidad/)).toBeInTheDocument();
    expect(await screen.findByText(/PRV-025 — Proveedor Central/)).toBeInTheDocument();
    expect(
      screen.queryByLabelText('Cantidad a ordenar de PROD-10 — Producto A')
    ).not.toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Crear orden desde adjudicación' })
      ).not.toBeDisabled();
    });

    await fireEvent.submit(
      screen.getByRole('button', { name: 'Crear orden desde adjudicación' }).closest('form')!
    );

    await waitFor(() =>
      expect(mocks.createFromConsolidation).toHaveBeenCalledWith(consolidationId, quotation.id, {
        branch_id: null,
        warehouse_id: centralWarehouseId,
        expected_date: null,
        expenses: [],
        notes: null
      })
    );
    expect(mocks.createOrder).not.toHaveBeenCalled();
    expect(mocks.goto).toHaveBeenCalledWith(`/purchase-orders/${createdOrder.id}`);
  });

  it('surfaces backend business errors without inventing remaining availability', async () => {
    mocks.createOrder.mockRejectedValue(
      new Error('La cantidad ordenada supera la disponibilidad restante de la cotización.')
    );

    render(PurchaseOrderEditor, {
      props: { quotationId: quotation.id }
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Crear orden' })).not.toBeDisabled();
    });

    await fireEvent.submit(screen.getByRole('button', { name: 'Crear orden' }).closest('form')!);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'La cantidad ordenada supera la disponibilidad restante de la cotización.'
    );
    expect(mocks.goto).not.toHaveBeenCalled();
  });
});
