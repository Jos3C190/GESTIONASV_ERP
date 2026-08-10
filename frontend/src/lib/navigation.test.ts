import { describe, expect, it } from 'vitest';
import { NAV_GROUPS } from './navigation';
import { routeTitle } from './stores/route-titles';

function itemByRoute(route: string) {
  return NAV_GROUPS.flatMap((group) => group.items).find((item) => item.route === route);
}

describe('catalog navigation', () => {
  it('exposes product categories with product read access', () => {
    expect(itemByRoute('/inventory/categories')).toMatchObject({
      label: 'Categorías de productos',
      implemented: true,
      requiredPermission: 'products:read'
    });
  });

  it('exposes measurement units with reference data access', () => {
    expect(itemByRoute('/inventory/units')).toMatchObject({
      label: 'Unidades de medida',
      implemented: true,
      requiredPermission: 'units:read'
    });
  });

  it('resolves navbar titles for both catalog pages', () => {
    expect(routeTitle('/inventory/categories')).toBe('Categorías de productos');
    expect(routeTitle('/inventory/units')).toBe('Unidades de medida');
  });

  it('exposes the lifecycle trash with its dedicated permission and title', () => {
    expect(itemByRoute('/trash')).toMatchObject({
      label: 'Papelera',
      implemented: true,
      requiredPermission: 'lifecycle:read'
    });
    expect(routeTitle('/trash')).toBe('Papelera');
  });
});
