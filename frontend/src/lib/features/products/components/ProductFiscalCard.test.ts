import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { productFiscalApi } = vi.hoisted(() => ({
  productFiscalApi: {
    options: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    listUnits: vi.fn(),
    updateUnit: vi.fn()
  }
}));

vi.mock('#lib/api/product-fiscal.ts', async (original) => ({
  ...(await original<typeof import('#lib/api/product-fiscal.ts')>()),
  productFiscalApi
}));
vi.mock('#lib/api/client.ts', () => ({
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

import { permissions } from '#lib/stores/permissions.svelte.ts';
import type { ProductFiscal, UnitFiscal } from '#lib/types/product-fiscal.ts';
import FiscalUnitsPanel from '#lib/features/fiscal/components/FiscalUnitsPanel.svelte';
import ProductFiscalCard from './ProductFiscalCard.svelte';

const unit: UnitFiscal = {
  unit_id: 1,
  code: 'UNIT',
  name: 'Unidad (u)',
  symbol: 'u',
  is_enabled: true,
  hacienda_unit_code: null,
  suggested_code: '59',
  effective_code: '59',
  hacienda_unit_name: 'Unidad'
};

const bread: ProductFiscal = {
  product_id: 7,
  product_uuid: 'p-7',
  sku: 'PAN-01',
  name: 'Pan francés',
  product_kind: 'goods',
  can_sell: true,
  tax_treatment: 'taxed',
  dte_item_type: null,
  effective_item_type: '1',
  additional_taxes: [],
  sale_unit: unit,
  billing_issues: []
};

function grant(...codes: string[]) {
  vi.spyOn(permissions, 'hasPermission').mockImplementation((code: string) => codes.includes(code));
}

describe('product fiscal classification', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    for (const fn of Object.values(productFiscalApi)) fn.mockReset();
    productFiscalApi.options.mockResolvedValue({
      taxes: [
        { code: 'D1', name: 'FOVIAL ($0.20 Ctvs. por galón)' },
        { code: 'C8', name: 'COTRANS ($0.10 Ctvs. por galón)' }
      ],
      units: [
        { code: '59', name: 'Unidad' },
        { code: '99', name: 'Otra' }
      ]
    });
  });

  it('shows the classification and the Hacienda unit of sale', async () => {
    grant('products:fiscal');
    productFiscalApi.get.mockResolvedValue(bread);
    render(ProductFiscalCard, { productId: 7 });
    expect(await screen.findByText('Gravado (IVA 13 %)')).toBeInTheDocument();
    expect(screen.getByText('(según el tipo de producto)')).toBeInTheDocument();
    expect(screen.getByText('Ninguno')).toBeInTheDocument();
  });

  it('lists what blocks invoicing', async () => {
    grant();
    productFiscalApi.get.mockResolvedValue({
      ...bread,
      billing_issues: ['La unidad de venta no está habilitada en la empresa.']
    });
    render(ProductFiscalCard, { productId: 7 });
    expect(await screen.findByText('Para facturar este producto falta:')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument();
  });

  it('saves taxes only for taxed products', async () => {
    grant('products:fiscal');
    productFiscalApi.get.mockResolvedValue(bread);
    productFiscalApi.update.mockResolvedValue({ ...bread, tax_treatment: 'exempt' });
    render(ProductFiscalCard, { productId: 7 });
    await fireEvent.click(await screen.findByRole('button', { name: 'Editar' }));
    await fireEvent.click(await screen.findByLabelText(/D1/));
    await fireEvent.click(screen.getByLabelText('Exento'));
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    await waitFor(() =>
      expect(productFiscalApi.update).toHaveBeenCalledWith(7, {
        tax_treatment: 'exempt',
        dte_item_type: null,
        additional_tax_codes: []
      })
    );
  });

  it('assigns a Hacienda unit and keeps the suggestion visible', async () => {
    productFiscalApi.listUnits.mockResolvedValue([unit]);
    productFiscalApi.updateUnit.mockResolvedValue({ ...unit, hacienda_unit_code: '99' });
    render(FiscalUnitsPanel, { canManage: true });
    expect(await screen.findByText('Sugerido: 59 · Unidad')).toBeInTheDocument();
    await fireEvent.change(screen.getByLabelText('Unidad de Hacienda de Unidad (u)'), {
      target: { value: '99' }
    });
    await waitFor(() => expect(productFiscalApi.updateUnit).toHaveBeenCalledWith(1, '99'));
    expect(await screen.findByText('Elegida por la empresa')).toBeInTheDocument();
  });
});
