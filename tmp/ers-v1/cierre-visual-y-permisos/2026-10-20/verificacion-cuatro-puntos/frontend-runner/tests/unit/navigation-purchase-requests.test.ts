import { describe, expect, it } from 'vitest';
import { NAV_GROUPS } from '$lib/navigation';

describe('purchase requests navigation', () => {
  it('registers the implemented route with the backend read permission', () => {
    const purchasesGroup = NAV_GROUPS.find((group) => group.label === 'Compras');
    const item = purchasesGroup?.items.find((entry) => entry.label === 'Solicitudes de compra');

    expect(item).toMatchObject({
      route: '/purchase-requests',
      implemented: true,
      requiredPermission: 'purchase_requests:read'
    });
  });
});
