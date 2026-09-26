import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseRequestDraftEditor from '$lib/features/purchase-requests/components/PurchaseRequestDraftEditor.svelte';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  update: vi.fn(),
  getWarehouses: vi.fn(),
  listProducts: vi.fn(),
  getProduct: vi.fn(),
  goto: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchase-requests', () => ({
  purchaseRequestsApi: {
    get: mocks.get,
    update: mocks.update
  }
}));

vi.mock('$lib/services/warehouses', () => ({
  getWarehouses: mocks.getWarehouses
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    listProducts: mocks.listProducts,
    getProduct: mocks.getProduct
  }
}));

vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
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

const request = {
  id: '33333333-3333-3333-3333-333333333333',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'SC-0001',
  branch_id: '11111111-1111-1111-1111-111111111111',
  warehouse_id: '22222222-2222-2222-2222-222222222222',
  requested_by_id: '44444444-4444-4444-4444-444444444444',
  request_date: '2026-09-12T15:00:00Z',
  required_date: null,
  justification: 'Reposición de inventario',
  status: 'draft',
  notes: null,
  details: [
    {
      id: '55555555-5555-5555-5555-555555555555',
      purchase_request_id: '33333333-3333-3333-3333-333333333333',
      product_id: 10,
      unit_id: 2,
      quantity: '5.000000',
      description: null,
      notes: null,
      created_at: null,
      updated_at: null
    }
  ],
  created_at: null,
  updated_at: null
} as const;

describe('PurchaseRequestDraftEditor', () => {
  beforeEach(() => {
    mocks.get.mockReset();
    mocks.update.mockReset();
    mocks.getWarehouses.mockReset();
    mocks.listProducts.mockReset();
    mocks.getProduct.mockReset();
    mocks.goto.mockReset();

    mocks.get.mockResolvedValue(request);
    mocks.getWarehouses.mockResolvedValue({
      items: [
        {
          id: request.warehouse_id,
          code: 'ALM-01',
          name: 'Almacén principal',
          branchId: request.branch_id
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
    mocks.getProduct.mockResolvedValue({
      id_product: 99,
      sku: 'PROD-99',
      name: 'Producto guardado en página posterior',
      can_purchase: true
    });
  });

  it('loads a draft and updates it with the PUT contract', async () => {
    mocks.update.mockResolvedValue(request);

    render(PurchaseRequestDraftEditor, {
      props: { requestId: request.id }
    });

    expect(await screen.findByDisplayValue('Reposición de inventario')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Seleccionar PROD-10 — Producto de prueba' })
    ).toHaveAttribute('aria-pressed', 'true');

    await fireEvent.input(screen.getByLabelText('Justificación'), {
      target: { value: 'Reposición actualizada' }
    });

    await fireEvent.submit(
      screen.getByRole('button', { name: 'Guardar cambios' }).closest('form')!
    );

    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith(request.id, {
        branch_id: request.branch_id,
        warehouse_id: request.warehouse_id,
        required_date: null,
        justification: 'Reposición actualizada',
        notes: null,
        details: [
          {
            product_id: 10,
            quantity: 5,
            description: null,
            notes: null
          }
        ]
      });
    });

    expect(mocks.goto).toHaveBeenCalledWith(`/purchase-requests/${request.id}`);
  });

  it('blocks editing when the request is not draft', async () => {
    mocks.get.mockResolvedValue({ ...request, status: 'submitted' });

    render(PurchaseRequestDraftEditor, {
      props: { requestId: request.id }
    });

    expect(
      await screen.findByText('Solo las solicitudes en borrador pueden editarse.')
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Guardar cambios' })).not.toBeInTheDocument();
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('searches and selects a different product in one action while editing a draft', async () => {
    mocks.listProducts
      .mockResolvedValueOnce({
        items: [
          {
            id_product: 10,
            sku: 'PROD-10',
            name: 'Producto de prueba',
            can_purchase: true
          }
        ],
        meta: { page: 1, size: 100, total: 1, pages: 1 }
      })
      .mockResolvedValueOnce({
        items: [
          {
            id_product: 11,
            sku: 'PROD-11',
            name: 'Producto alternativo',
            can_purchase: true
          }
        ],
        meta: { page: 1, size: 100, total: 1, pages: 1 }
      });
    mocks.update.mockResolvedValue(request);

    render(PurchaseRequestDraftEditor, {
      props: { requestId: request.id }
    });

    await screen.findByRole('button', { name: 'Seleccionar PROD-10 — Producto de prueba' });
    await fireEvent.input(screen.getByRole('searchbox', { name: 'Producto 1' }), {
      target: { value: 'PROD-11' }
    });
    await fireEvent.click(
      await screen.findByRole('button', {
        name: 'Seleccionar PROD-11 — Producto alternativo'
      })
    );

    expect(
      screen.getByRole('button', { name: 'Seleccionar PROD-11 — Producto alternativo' })
    ).toHaveAttribute('aria-pressed', 'true');
    await fireEvent.submit(
      screen.getByRole('button', { name: 'Guardar cambios' }).closest('form')!
    );

    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith(
        request.id,
        expect.objectContaining({
          details: [
            {
              product_id: 11,
              quantity: 5,
              description: null,
              notes: null
            }
          ]
        })
      );
    });
  });

  it('loads and shows the existing product even when it is outside the first catalog page', async () => {
    mocks.get.mockResolvedValue({
      ...request,
      details: request.details.map((detail) => ({ ...detail, product_id: 99 }))
    });

    render(PurchaseRequestDraftEditor, {
      props: { requestId: request.id }
    });

    const selectedProductLabels = await screen.findAllByText(
      'Producto guardado en página posterior'
    );
    expect(selectedProductLabels).toHaveLength(2);
    expect(mocks.getProduct).toHaveBeenCalledWith(99);
    expect(
      screen.getByRole('button', {
        name: 'Seleccionar PROD-99 — Producto guardado en página posterior'
      })
    ).toHaveAttribute('aria-pressed', 'true');
  });

  it('retries loading a saved product after its initial lookup fails', async () => {
    mocks.get.mockResolvedValue({
      ...request,
      details: request.details.map((detail) => ({ ...detail, product_id: 99 }))
    });
    mocks.getProduct.mockRejectedValueOnce(new Error('Network error'));

    render(PurchaseRequestDraftEditor, {
      props: { requestId: request.id }
    });

    expect(
      await screen.findByText('No se pudo cargar el nombre del producto.')
    ).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(
      await screen.findByRole('button', {
        name: 'Seleccionar PROD-99 — Producto guardado en página posterior'
      })
    ).toHaveAttribute('aria-pressed', 'true');
    expect(mocks.getProduct).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('No se pudo cargar el nombre del producto.')).not.toBeInTheDocument();
  });
});
