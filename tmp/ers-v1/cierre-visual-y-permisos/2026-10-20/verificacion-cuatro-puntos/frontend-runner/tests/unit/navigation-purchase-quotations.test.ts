import { describe, expect, it } from 'vitest';
import { NAV_GROUPS } from '$lib/navigation';

describe('purchase quotations navigation', () => {
  it('exposes the implemented purchase quotations route with read permission', () => {
    const purchases = NAV_GROUPS.find((group) => group.label === 'Compras');
    const item = purchases?.items.find((entry) => entry.label === 'Cotizaciones de compra');

    expect(item).toMatchObject({
      label: 'Cotizaciones de compra',
      route: '/purchase-quotations',
      implemented: true,
      requiredPermission: 'purchase_quotations:read'
    });
    expect(item?.module).toBeUndefined();
  });
});
