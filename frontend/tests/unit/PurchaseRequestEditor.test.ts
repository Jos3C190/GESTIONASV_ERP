import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseRequestEditor from '$lib/features/purchase-requests/components/PurchaseRequestEditor.svelte';

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  getWarehouses: vi.fn(),
  listProducts: vi.fn(),
  goto: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchase-requests', () => ({
  purchaseRequestsApi: {
    create: mocks.create
  }
}));

vi.mock('$lib/services/warehouses', () => ({
  getWarehouses: mocks.getWarehouses
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    listProducts: mocks.listProducts
  }
}));

vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    id: '11111111-1111-1111-1111-111111111111',
    branches: [
      {
        id: '11111111-1111-1111-1111-111111111111',
        company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        name: 'Sucursal Centro',
        code: 'CENTRO',
        is_active: true
      }
    ]
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: (code: string) => code === 'purchase_requests:manage'
  }
}));

describe('PurchaseRequestEditor', () => {
  beforeEach(() => {
    mocks.create.mockReset();
    mocks.getWarehouses.mockReset();
    mocks.listProducts.mockReset();
    mocks.goto.mockReset();

    mocks.getWarehouses.mockResolvedValue({
      items: [
        {
          id: '22222222-2222-2222-2222-222222222222',
          code: 'ALM-01',
          name: 'Almacén principal',
          branchId: '11111111-1111-1111-1111-111111111111'
        }
      ],
      meta: { page: 1, size: 100, total: 1, pages: 1 },
      summary: {}
    });

    mocks.listProducts.mockResolvedValue({
      items: [
        {
          id_product: 10,
          sku: 'PROD-10',
          name: 'Producto de prueba',
          can_purchase: true
        }
      ],
      meta: { page: 1, size: 100, total: 1, pages: 1 }
    });
  });

  it('creates a draft using the backend contract', async () => {
    mocks.create.mockResolvedValue({
      id: '33333333-3333-3333-3333-333333333333'
    });

    render(PurchaseRequestEditor);

    await screen.findByRole('option', { name: 'ALM-01 — Almacén principal' });

    await fireEvent.input(screen.getByLabelText('Justificación'), {
      target: { value: 'Reposición de inventario' }
    });
    await fireEvent.change(screen.getByLabelText('Producto 1'), {
      target: { value: '10' }
    });
    await fireEvent.submit(screen.getByRole('button', { name: 'Crear borrador' }).closest('form')!);

    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith({
        branch_id: '11111111-1111-1111-1111-111111111111',
        warehouse_id: '22222222-2222-2222-2222-222222222222',
        required_date: null,
        justification: 'Reposición de inventario',
        notes: null,
        details: [
          {
            product_id: 10,
            quantity: 1,
            description: null,
            notes: null
          }
        ]
      });
    });

    expect(mocks.goto).toHaveBeenCalledWith(
      '/purchase-requests/33333333-3333-3333-3333-333333333333'
    );
  });

  it('does not submit when justification and product are missing', async () => {
    render(PurchaseRequestEditor);

    await screen.findByRole('option', { name: 'ALM-01 — Almacén principal' });
    await fireEvent.submit(screen.getByRole('button', { name: 'Crear borrador' }).closest('form')!);

    expect(await screen.findByText('La justificación es obligatoria.')).toBeInTheDocument();
    expect(screen.getByText('Selecciona un producto.')).toBeInTheDocument();
    expect(mocks.create).not.toHaveBeenCalled();
  });
});
