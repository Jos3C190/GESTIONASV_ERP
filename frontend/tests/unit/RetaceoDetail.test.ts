import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RetaceoDetail from '$lib/features/retaceos/components/RetaceoDetail.svelte';
import type { Retaceo } from '$lib/types/retaceo';

const mocks = vi.hoisted(() => ({
  getRetaceo: vi.fn(),
  getPurchase: vi.fn(),
  listUnits: vi.fn(),
  getProduct: vi.fn()
}));

vi.mock('$lib/api/retaceos', () => ({
  retaceosApi: {
    get: mocks.getRetaceo
  }
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    get: mocks.getPurchase
  }
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    listUnits: mocks.listUnits,
    getProduct: mocks.getProduct
  }
}));

const retaceo: Retaceo = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'RET-0001',
  purchase_id: '22222222-2222-2222-2222-222222222222',
  branch_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  created_by_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  currency: 'USD',
  details: [
    {
      id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
      retaceo_id: '11111111-1111-1111-1111-111111111111',
      purchase_detail_id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
      product_id: 10,
      unit_id: 3,
      quantity: '2.000000',
      cost_fob: '100.000000',
      freight: '10.000000',
      expenses: '5.000000',
      dai: '3.000000',
      total_cost: '118.000000',
      unit_cost: '59.000000',
      created_at: null,
      updated_at: null
    }
  ],
  total_fob: '100.000000',
  total_freight: '10.000000',
  total_expenses: '5.000000',
  total_dai: '3.000000',
  import_vat: '15.340000',
  total_cost: '118.000000',
  freight_percentage: '10.000000',
  expense_percentage: '5.000000',
  dai_percentage: '3.000000',
  status: 'calculated',
  notes: 'Importación septiembre',
  created_at: '2026-09-20T12:00:00-06:00',
  updated_at: null
};

describe('RetaceoDetail', () => {
  beforeEach(() => {
    mocks.getRetaceo.mockReset();
    mocks.getPurchase.mockReset();
    mocks.listUnits.mockReset();
    mocks.getProduct.mockReset();

    mocks.getRetaceo.mockResolvedValue(retaceo);

    mocks.getPurchase.mockResolvedValue({
      id: retaceo.purchase_id,
      code: 'COM-0001'
    });

    mocks.listUnits.mockResolvedValue([
      {
        id_unit: 3,
        code: 'UND',
        name: 'Unidad'
      }
    ]);

    mocks.getProduct.mockResolvedValue({
      id_product: 10,
      sku: 'PROD-10',
      name: 'Producto A'
    });
  });

  it('renders backend-derived landed-cost information and source traceability', async () => {
    render(RetaceoDetail, {
      props: { id: retaceo.id }
    });

    expect(await screen.findByText('RET-0001')).toBeInTheDocument();

    expect(screen.getByRole('link', { name: 'COM-0001' })).toHaveAttribute(
      'href',
      `/purchases/${retaceo.purchase_id}`
    );

    expect(screen.getByText('PROD-10 — Producto A')).toBeInTheDocument();
    expect(screen.getByText('UND — Unidad')).toBeInTheDocument();

    expect(screen.getByText('Calculado')).toBeInTheDocument();
    expect(screen.getByText(/Flete · 10/)).toBeInTheDocument();
    expect(screen.getByText(/Gastos · 5/)).toBeInTheDocument();
    expect(screen.getByText(/DAI · 3/)).toBeInTheDocument();

    expect(
      screen.getByText('Informativo. No forma parte del costo aterrizado.')
    ).toBeInTheDocument();

    expect(screen.getByText('Importación septiembre')).toBeInTheDocument();
  });

  it('renders an error and retries the retaceo request', async () => {
    mocks.getRetaceo
      .mockRejectedValueOnce(new Error('No disponible'))
      .mockResolvedValueOnce(retaceo);

    render(RetaceoDetail, {
      props: { id: retaceo.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('No disponible');

    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByText('RET-0001')).toBeInTheDocument();
    expect(mocks.getRetaceo).toHaveBeenCalledTimes(2);
  });
});
