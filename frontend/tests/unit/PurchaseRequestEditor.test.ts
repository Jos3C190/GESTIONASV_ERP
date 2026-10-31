import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseRequestEditor from '$lib/features/purchase-requests/components/PurchaseRequestEditor.svelte';

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  getWarehouses: vi.fn(),
  listProducts: vi.fn(),
  getOperationalContext: vi.fn(),
  goto: vi.fn()
}));

const productFixtures = [
  {
    id_product: 10,
    sku: 'PROD-10',
    name: 'Producto de prueba',
    can_purchase: true
  },
  {
    id_product: 11,
    sku: 'PROD-11',
    name: 'Producto alternativo',
    can_purchase: true
  }
];

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/client', () => ({
  HttpError: class HttpError extends Error {},
  api: {
    operationalContext: {
      get: mocks.getOperationalContext
    }
  }
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
    ],
    configure: vi.fn()
  }
}));

vi.mock('$lib/stores/company.svelte', () => ({
  company: {
    id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: (code: string) => code === 'purchase_requests:manage',
    hasAnyPermission: (codes: string[]) => codes.includes('purchase_requests:manage')
  }
}));

describe('PurchaseRequestEditor', () => {
  beforeEach(() => {
    mocks.create.mockReset();
    mocks.getWarehouses.mockReset();
    mocks.listProducts.mockReset();
    mocks.getOperationalContext.mockReset();
    mocks.goto.mockReset();

    mocks.getOperationalContext.mockResolvedValue({
      branches: [
        {
          id: '11111111-1111-1111-1111-111111111111',
          company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
          name: 'Sucursal Centro',
          code: 'CENTRO',
          is_active: true
        }
      ],
      last_branch_id: '11111111-1111-1111-1111-111111111111'
    });

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

    mocks.listProducts.mockImplementation(
      async (params: { search?: string; page?: number; size?: number } = {}) => {
        const normalizedSearch = params.search?.toLocaleLowerCase('es') ?? '';
        const items = productFixtures.filter((product) =>
          [product.sku, product.name].some((value) =>
            value.toLocaleLowerCase('es').includes(normalizedSearch)
          )
        );

        return {
          items,
          meta: {
            page: params.page ?? 1,
            size: params.size ?? 100,
            total: items.length,
            pages: items.length ? 1 : 0
          }
        };
      }
    );
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
    await fireEvent.click(
      await screen.findByRole('option', {
        name: 'Seleccionar PROD-10 — Producto de prueba'
      })
    );
    expect(
      screen.getByRole('option', { name: 'Seleccionar PROD-10 — Producto de prueba' })
    ).toHaveAttribute('aria-selected', 'true');
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
    expect(screen.getByRole('combobox', { name: 'Producto 1' })).toHaveAttribute(
      'aria-invalid',
      'true'
    );
    expect(screen.getByRole('combobox', { name: 'Producto 1' })).toHaveAttribute(
      'aria-describedby',
      'purchase-request-product-0-hint purchase-request-product-0-error'
    );
    expect(screen.getByRole('combobox', { name: 'Producto 1' })).toHaveAttribute(
      'aria-required',
      'true'
    );
    await waitFor(() => expect(screen.getByLabelText('Justificación')).toHaveFocus());
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it('filters products by SKU or name before assigning them with one click', async () => {
    render(PurchaseRequestEditor);

    const productButton = await screen.findByRole('option', {
      name: 'Seleccionar PROD-10 — Producto de prueba'
    });
    expect(productButton).toBeInTheDocument();

    await fireEvent.input(screen.getByRole('combobox', { name: 'Producto 1' }), {
      target: { value: 'alternativo' }
    });

    expect(
      await screen.findByRole('option', { name: 'Seleccionar PROD-11 — Producto alternativo' })
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.queryByRole('option', { name: 'Seleccionar PROD-10 — Producto de prueba' })
      ).not.toBeInTheDocument()
    );

    await fireEvent.click(
      screen.getByRole('option', { name: 'Seleccionar PROD-11 — Producto alternativo' })
    );

    expect(
      screen.getByRole('option', { name: 'Seleccionar PROD-11 — Producto alternativo' })
    ).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('combobox', { name: 'Producto 1' })).toHaveValue('');
  });

  it('supports selecting a product from the keyboard', async () => {
    render(PurchaseRequestEditor);

    const search = await screen.findByRole('combobox', { name: 'Producto 1' });
    await fireEvent.keyDown(search, { key: 'ArrowDown' });

    const firstProduct = screen.getByRole('option', {
      name: 'Seleccionar PROD-10 — Producto de prueba'
    });
    expect(search).toHaveAttribute('aria-activedescendant', firstProduct.id);

    await fireEvent.keyDown(search, { key: 'Enter' });

    expect(firstProduct).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('Seleccionado')).toBeInTheDocument();
  });

  it('shows an empty state when the product search has no matches', async () => {
    render(PurchaseRequestEditor);

    await screen.findByRole('option', { name: 'Seleccionar PROD-10 — Producto de prueba' });
    await fireEvent.input(screen.getByRole('combobox', { name: 'Producto 1' }), {
      target: { value: 'inexistente' }
    });

    expect(
      await screen.findByText(
        'No hay productos disponibles para compra que coincidan en el catálogo.'
      )
    ).toBeInTheDocument();
  });

  it('searches the entire catalog and finds a product outside the first page', async () => {
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
        meta: { page: 1, size: 100, total: 101, pages: 2 }
      })
      .mockResolvedValueOnce({
        items: [
          {
            id_product: 101,
            sku: 'PROD-101',
            name: 'Producto en segunda página',
            can_purchase: true
          }
        ],
        meta: { page: 1, size: 100, total: 1, pages: 1 }
      });

    render(PurchaseRequestEditor);

    await screen.findByRole('option', { name: 'Seleccionar PROD-10 — Producto de prueba' });
    await fireEvent.input(screen.getByRole('combobox', { name: 'Producto 1' }), {
      target: { value: 'PROD-101' }
    });
    expect(
      await screen.findByRole('option', {
        name: 'Seleccionar PROD-101 — Producto en segunda página'
      })
    ).toBeInTheDocument();
    expect(mocks.listProducts).toHaveBeenLastCalledWith({
      active_only: true,
      search: 'PROD-101',
      page: 1,
      size: 100
    });
  });

  it('retries a failed later catalog page without dropping already loaded products', async () => {
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
        meta: { page: 1, size: 100, total: 101, pages: 2 }
      })
      .mockRejectedValueOnce(new Error('Error temporal de página'))
      .mockResolvedValueOnce({
        items: [
          {
            id_product: 101,
            sku: 'PROD-101',
            name: 'Producto en segunda página',
            can_purchase: true
          }
        ],
        meta: { page: 2, size: 100, total: 101, pages: 2 }
      });

    render(PurchaseRequestEditor);

    await screen.findByRole('option', { name: 'Seleccionar PROD-10 — Producto de prueba' });
    await fireEvent.click(
      screen.getByRole('button', { name: 'Mostrar los siguientes 100 productos' })
    );

    expect(
      await screen.findByText('No se pudieron cargar más productos: Error temporal de página')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: 'Seleccionar PROD-10 — Producto de prueba' })
    ).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar carga de productos' }));

    expect(
      await screen.findByRole('option', {
        name: 'Seleccionar PROD-101 — Producto en segunda página'
      })
    ).toBeInTheDocument();
    expect(mocks.listProducts).toHaveBeenLastCalledWith({ active_only: true, page: 2, size: 100 });
    expect(
      screen.getByRole('option', { name: 'Seleccionar PROD-10 — Producto de prueba' })
    ).toBeInTheDocument();
  });

  it('retries a failed whole-catalog search without needing another query edit', async () => {
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
      .mockRejectedValueOnce(new Error('Error temporal de búsqueda'))
      .mockResolvedValueOnce({
        items: [
          {
            id_product: 101,
            sku: 'PROD-101',
            name: 'Producto en segunda página',
            can_purchase: true
          }
        ],
        meta: { page: 1, size: 100, total: 1, pages: 1 }
      });

    render(PurchaseRequestEditor);

    await screen.findByRole('option', { name: 'Seleccionar PROD-10 — Producto de prueba' });
    await fireEvent.input(screen.getByRole('combobox', { name: 'Producto 1' }), {
      target: { value: 'PROD-101' }
    });

    expect(
      await screen.findByText('No se pudo completar la búsqueda: Error temporal de búsqueda')
    ).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar búsqueda' }));

    expect(
      await screen.findByRole('option', {
        name: 'Seleccionar PROD-101 — Producto en segunda página'
      })
    ).toBeInTheDocument();
    expect(mocks.listProducts).toHaveBeenLastCalledWith({
      active_only: true,
      search: 'PROD-101',
      page: 1,
      size: 100
    });
  });

  it('offers retry after product options fail to load', async () => {
    mocks.listProducts
      .mockRejectedValueOnce(new Error('Error temporal del catálogo'))
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
      });

    render(PurchaseRequestEditor);

    expect(await screen.findByText('Error temporal del catálogo')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(
      await screen.findByRole('option', { name: 'Seleccionar PROD-10 — Producto de prueba' })
    ).toBeInTheDocument();
  });
});
