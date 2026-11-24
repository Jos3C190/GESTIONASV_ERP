import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { priceListsApi, branchesApi, discountPoliciesApi } = vi.hoisted(() => ({
  priceListsApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    prices: vi.fn(),
    history: vi.fn(),
    setPrice: vi.fn(),
    endPrice: vi.fn(),
    cancelPrice: vi.fn(),
    categories: vi.fn(),
    categoryMargins: vi.fn(),
    replaceCategoryMargins: vi.fn(),
    volumeDiscounts: vi.fn(),
    addVolumeDiscount: vi.fn(),
    removeVolumeDiscount: vi.fn()
  },
  branchesApi: { list: vi.fn() },
  discountPoliciesApi: { list: vi.fn(), save: vi.fn(), mine: vi.fn() }
}));

vi.mock('#lib/api/price-lists.ts', () => ({ priceListsApi, discountPoliciesApi }));
vi.mock('#lib/api/client.ts', () => ({
  api: { branches: branchesApi },
  HttpError: class HttpError extends Error {
    constructor(
      readonly code: string,
      message: string,
      readonly status: number
    ) {
      super(message);
    }
  }
}));

import { HttpError } from '#lib/api/client.ts';
import {
  counterpartPrice,
  formatPrice,
  todayInElSalvador,
  validityText
} from '#lib/features/price-lists/labels.ts';
import { permissions } from '#lib/stores/permissions.svelte.ts';
import type { ListedPrice, PriceList } from '#lib/types/price-list.ts';
import DiscountPoliciesPage from './DiscountPoliciesPage.svelte';
import PriceListDetail from './PriceListDetail.svelte';
import PriceListsOverview from './PriceListsOverview.svelte';

const counter: PriceList = {
  id: 'list-1',
  code: 'MOSTRADOR',
  name: 'Mostrador',
  description: null,
  prices_include_vat: true,
  is_default: true,
  is_active: true,
  price_count: 3,
  customer_count: 0,
  updated_at: '2026-11-16T15:00:00Z',
  target_margin_percent: '30.00'
};

const row: ListedPrice = {
  unit: {
    product_id: 7,
    variant_id: null,
    sku: 'JAR-001',
    name: 'Jarabe artesanal',
    unit_id: 1,
    unit_name: 'Unidad (u)',
    factor: '1',
    is_base: true
  },
  current: {
    id: 'entry-1',
    price_list_id: 'list-1',
    product_id: 7,
    variant_id: null,
    unit_id: 1,
    branch_id: null,
    branch_name: null,
    price: '1.13000000',
    valid_from: '2026-11-01',
    valid_to: null,
    status: 'current',
    created_by_name: 'Admin',
    created_at: '2026-11-01T15:00:00Z'
  },
  next: null,
  branch_overrides: 0
};

beforeEach(() => {
  for (const fn of [
    ...Object.values(priceListsApi),
    ...Object.values(discountPoliciesApi),
    branchesApi.list
  ])
    fn.mockReset();
  permissions.set(['price_lists:read', 'price_lists:manage'], false);
  branchesApi.list.mockResolvedValue([{ id: 'branch-1', name: 'Roosevelt' }]);
});

describe('price list labels', () => {
  it('formats prices, validity and the counterpart with or without VAT', () => {
    expect(formatPrice('1.13000000')).toBe('$1.13');
    expect(formatPrice('0.88495575')).toBe('$0.885');
    expect(formatPrice(null)).toBe('—');
    expect(validityText('2026-11-16', null)).toBe('desde 16/11/2026');
    expect(validityText('2026-11-16', '2026-11-30')).toBe('16/11/2026 al 30/11/2026');
    expect(counterpartPrice('1.13', true)).toBe('$1.00');
    expect(counterpartPrice('1.00', false)).toBe('$1.13');
    expect(todayInElSalvador(new Date('2026-11-17T03:00:00Z'))).toBe('2026-11-16');
  });
});

describe('PriceListsOverview', () => {
  it('lists the price lists and creates a new one', async () => {
    priceListsApi.list.mockResolvedValue([counter]);
    priceListsApi.create.mockResolvedValue({});
    render(PriceListsOverview);

    expect(await screen.findByText('Mostrador')).toBeInTheDocument();
    expect(screen.getByText('Predeterminada')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Nueva lista' }));
    await fireEvent.input(screen.getByLabelText('Código'), { target: { value: 'MAYOREO' } });
    await fireEvent.input(screen.getByLabelText('Nombre'), { target: { value: 'Mayoreo' } });
    await fireEvent.click(screen.getByLabelText(/No incluyen IVA/));
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    expect(priceListsApi.create).toHaveBeenCalledWith({
      code: 'MAYOREO',
      name: 'Mayoreo',
      description: null,
      prices_include_vat: false,
      is_default: false,
      is_active: true,
      target_margin_percent: null
    });
  });

  it('offers to create the first list on the empty state', async () => {
    priceListsApi.list.mockResolvedValue([]);
    render(PriceListsOverview);
    expect(await screen.findByText('Aún no hay listas de precios')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Crear lista' }));
    expect(screen.getByLabelText(/Lista predeterminada/)).toBeChecked();
  });

  it('shows a readable error', async () => {
    priceListsApi.list.mockRejectedValue(new HttpError('forbidden', 'Sin permiso.', 403));
    render(PriceListsOverview);
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin permiso.');
  });
});

describe('PriceListDetail', () => {
  it('shows the current price and saves a branch price from a date', async () => {
    priceListsApi.get.mockResolvedValue(counter);
    priceListsApi.prices.mockResolvedValue([row]);
    priceListsApi.setPrice.mockResolvedValue({});
    render(PriceListDetail, { listId: 'list-1' });

    expect(await screen.findByText('$1.13')).toBeInTheDocument();
    expect(screen.getByText('Sin IVA: $1.00')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Cambiar' }));
    await fireEvent.input(screen.getByLabelText('Precio (USD)'), { target: { value: '1.25' } });
    await fireEvent.input(screen.getByLabelText('Rige desde'), {
      target: { value: '2099-01-01' }
    });
    await fireEvent.change(screen.getByLabelText('Aplica a'), { target: { value: 'branch-1' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar precio' }));
    expect(priceListsApi.setPrice).toHaveBeenCalledWith('list-1', {
      product_id: 7,
      variant_id: null,
      unit_id: 1,
      branch_id: 'branch-1',
      price: '1.25',
      valid_from: '2099-01-01'
    });
  });

  it('opens the history and hides changes without manage permission', async () => {
    permissions.set(['price_lists:read'], false);
    priceListsApi.get.mockResolvedValue(counter);
    priceListsApi.prices.mockResolvedValue([row]);
    priceListsApi.history.mockResolvedValue([row.current]);
    render(PriceListDetail, { listId: 'list-1' });

    await fireEvent.click(await screen.findByRole('button', { name: 'Historial' }));
    expect(await screen.findByText('Vigente')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cambiar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Terminar hoy' })).not.toBeInTheDocument();
  });

  it('explains when no product matches the search', async () => {
    priceListsApi.get.mockResolvedValue(counter);
    priceListsApi.prices.mockResolvedValue([]);
    render(PriceListDetail, { listId: 'list-1' });
    expect(await screen.findByText('No hay productos para vender.')).toBeInTheDocument();
  });
});

describe('V2c: margen, escalas y topes', () => {
  const costed: ListedPrice = {
    ...row,
    cost: '1.40000000',
    margin_percent: '24.67',
    target_margin_percent: '30.00',
    suggested_price: '2.26',
    below_cost: false,
    below_target: true
  };

  it('shows cost and margin and uses the suggested price', async () => {
    priceListsApi.get.mockResolvedValue(counter);
    priceListsApi.prices.mockResolvedValue([costed]);
    priceListsApi.setPrice.mockResolvedValue({});
    render(PriceListDetail, { listId: 'list-1' });

    expect(await screen.findByText('margen 24.67 %')).toBeInTheDocument();
    expect(screen.getByText('Bajo el objetivo')).toBeInTheDocument();
    expect(screen.getByText('Margen objetivo: 30 %')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Cambiar' }));
    expect(screen.getByText('$2.26')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Usar' }));
    expect(screen.getByLabelText('Precio (USD)')).toHaveValue(2.26);
  });

  it('hides cost when the user cannot see it', async () => {
    priceListsApi.get.mockResolvedValue(counter);
    priceListsApi.prices.mockResolvedValue([row]);
    render(PriceListDetail, { listId: 'list-1' });
    expect(await screen.findByText('$1.13')).toBeInTheDocument();
    expect(screen.queryByText(/Costo/)).not.toBeInTheDocument();
  });

  it('adds a volume scale for the product', async () => {
    priceListsApi.get.mockResolvedValue(counter);
    priceListsApi.prices.mockResolvedValue([row]);
    priceListsApi.volumeDiscounts.mockResolvedValue([]);
    priceListsApi.addVolumeDiscount.mockResolvedValue({});
    render(PriceListDetail, { listId: 'list-1' });

    await fireEvent.click(await screen.findByRole('button', { name: 'Volumen' }));
    expect(
      await screen.findByText('Este producto no tiene escalas en la lista.')
    ).toBeInTheDocument();
    await fireEvent.input(screen.getByLabelText('Desde la cantidad'), { target: { value: '10' } });
    await fireEvent.input(screen.getByLabelText('Descuento (%)'), { target: { value: '3' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Agregar escala' }));
    expect(priceListsApi.addVolumeDiscount).toHaveBeenCalledWith(
      'list-1',
      expect.objectContaining({
        product_id: 7,
        unit_id: 1,
        min_quantity: '10',
        discount_percent: '3'
      })
    );
  });

  it('saves the discount limits of a role', async () => {
    discountPoliciesApi.list.mockResolvedValue([
      {
        role_id: 'role-1',
        role_name: 'GERENTE DE SUCURSAL',
        configured: false,
        updated_at: null,
        max_line_discount_percent: '0.00',
        max_global_discount_percent: '0.00'
      }
    ]);
    discountPoliciesApi.save.mockResolvedValue({
      role_id: 'role-1',
      role_name: 'GERENTE DE SUCURSAL',
      configured: true,
      updated_at: '2026-11-16T15:00:00Z',
      max_line_discount_percent: '10.00',
      max_global_discount_percent: '0.00'
    });
    render(DiscountPoliciesPage);

    expect(await screen.findByText('Sin topes')).toBeInTheDocument();
    const save = screen.getByRole('button', { name: 'Guardar' });
    expect(save).toBeDisabled();
    await fireEvent.input(screen.getByLabelText('Por línea (%)'), { target: { value: '10' } });
    await fireEvent.click(save);
    expect(discountPoliciesApi.save).toHaveBeenCalledWith('role-1', {
      max_line_discount_percent: '10',
      max_global_discount_percent: '0'
    });
    expect(
      await screen.findByText('Se guardaron los topes de GERENTE DE SUCURSAL.')
    ).toBeInTheDocument();
  });
});
