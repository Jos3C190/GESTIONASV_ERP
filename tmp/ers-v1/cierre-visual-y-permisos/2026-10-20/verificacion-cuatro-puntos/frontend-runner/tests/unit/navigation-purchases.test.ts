import { describe, expect, it } from 'vitest';
import { NAV_GROUPS } from '$lib/navigation';

describe('purchases navigation', () => {
  it('exposes the implemented purchases route with read permission', () => {
    const purchases = NAV_GROUPS.find((group) => group.label === 'Compras');
    const item = purchases?.items.find((entry) => entry.label === 'Compras');

    expect(item).toMatchObject({
      label: 'Compras',
      route: '/purchases',
      implemented: true,
      requiredPermission: 'purchases:read'
    });

    expect(item?.module).toBeUndefined();
  });
});
