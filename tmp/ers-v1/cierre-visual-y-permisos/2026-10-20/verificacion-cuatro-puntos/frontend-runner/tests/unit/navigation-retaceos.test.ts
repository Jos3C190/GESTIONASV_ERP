import { describe, expect, it } from 'vitest';
import { NAV_GROUPS } from '$lib/navigation';

describe('retaceos navigation', () => {
  it('exposes the implemented retaceos route with read permission', () => {
    const purchases = NAV_GROUPS.find((group) => group.label === 'Compras');
    const item = purchases?.items.find((entry) => entry.label === 'Retaceo');

    expect(item).toMatchObject({
      label: 'Retaceo',
      route: '/retaceos',
      implemented: true,
      requiredPermission: 'retaceos:read'
    });

    expect(item?.module).toBeUndefined();
  });
});
