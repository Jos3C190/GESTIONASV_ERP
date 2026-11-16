import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.hoisted(() => vi.fn());
vi.mock('$lib/api/client', () => ({ apiFetch: apiFetchMock }));

import { productFiscalApi } from '../../src/lib/api/product-fiscal';

describe('productFiscalApi', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue({});
  });

  it('reads and saves the product classification', async () => {
    await productFiscalApi.options();
    expect(apiFetchMock).toHaveBeenLastCalledWith('/product-fiscal/options');
    await productFiscalApi.update(7, {
      tax_treatment: 'taxed',
      dte_item_type: '3',
      additional_tax_codes: ['D1']
    });
    expect(apiFetchMock).toHaveBeenLastCalledWith('/products/7/fiscal', {
      method: 'PUT',
      body: '{"tax_treatment":"taxed","dte_item_type":"3","additional_tax_codes":["D1"]}'
    });
  });

  it('updates the Hacienda unit code', async () => {
    await productFiscalApi.updateUnit(3, null);
    expect(apiFetchMock).toHaveBeenLastCalledWith('/fiscal/units/3', {
      method: 'PUT',
      body: '{"hacienda_unit_code":null}'
    });
  });
});
