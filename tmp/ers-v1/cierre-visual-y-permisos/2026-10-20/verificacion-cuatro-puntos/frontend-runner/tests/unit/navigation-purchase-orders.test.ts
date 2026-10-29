import { describe, expect, it } from 'vitest';
import { NAV_GROUPS } from '$lib/navigation';

describe('purchase orders navigation', () => {
  it('exposes the implemented purchase orders route with read permission', () => {
    const purchases = NAV_GROUPS.find((group) => group.label === 'Compras');
    const item = purchases?.items.find((entry) => entry.label === 'Órdenes de compra');

    expect(item).toMatchObject({
      label: 'Órdenes de compra',
      route: '/purchase-orders',
      implemented: true,
      requiredPermission: 'purchase_orders:read'
    });
    expect(item?.module).toBeUndefined();
  });
});
