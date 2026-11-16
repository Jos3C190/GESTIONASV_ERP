import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.hoisted(() => vi.fn());
vi.mock('$lib/api/client', () => ({ apiFetch: apiFetchMock }));

import { customersApi } from '../../src/lib/api/customers';

function call(index = 0): [string, RequestInit | undefined] {
  return apiFetchMock.mock.calls[index] as [string, RequestInit | undefined];
}

describe('customersApi', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue({});
  });

  it('builds the list query from the filters', async () => {
    await customersApi.list({ search: ' trigal ', customer_type: 'taxpayer', active: true });
    expect(call()[0]).toBe(
      '/customers?search=trigal&customer_type=taxpayer&active=true&page=1&size=20'
    );
    await customersApi.list({ active: null, include_generic: true, page: 2, size: 50 });
    expect(call(1)[0]).toBe('/customers?include_generic=true&page=2&size=50');
  });

  it('updates, toggles status and asks for the generic customer', async () => {
    await customersApi.setActive('c1', false);
    expect(call()).toEqual([
      '/customers/c1/status',
      { method: 'PATCH', body: '{"is_active":false}' }
    ]);
    await customersApi.generic('branch 1');
    expect(call(1)[0]).toBe('/customers/generic?branch_id=branch%201');
  });

  it('manages delivery addresses', async () => {
    const address = {
      label: 'Bodega',
      address_line: 'Km 5',
      geography: null,
      latitude: null,
      longitude: null,
      contact_name: null,
      phone: null,
      is_default: false,
      is_active: true
    };
    await customersApi.addDeliveryAddress('c1', address);
    expect(call()[0]).toBe('/customers/c1/delivery-addresses');
    await customersApi.updateDeliveryAddress('c1', 'a1', address);
    expect(call(1)[0]).toBe('/customers/c1/delivery-addresses/a1');
    expect(call(1)[1]?.method).toBe('PUT');
    await customersApi.deleteDeliveryAddress('c1', 'a1');
    expect(call(2)[1]?.method).toBe('DELETE');
  });
});
