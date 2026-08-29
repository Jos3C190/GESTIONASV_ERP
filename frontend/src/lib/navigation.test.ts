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

  it('resolves the available warehouse page titles', () => {
    expect(routeTitle('/warehouses/warehouse-1/structures')).toBe(
      'Estructuras y límites compartidos'
    );
    expect(routeTitle('/warehouses/warehouse-1/locations/new')).toBe('Nueva ubicación');
    expect(routeTitle('/warehouses/warehouse-1/locations/generate')).toBe(
      'Generar ubicaciones por rangos'
    );
    expect(routeTitle('/warehouses/warehouse-1/locations/location-1/edit')).toBe(
      'Editar ubicación'
    );
  });

  it('does not expose a dedicated title for the hidden location import route', () => {
    expect(routeTitle('/warehouses/warehouse-1/locations/import')).toBe('Almacenes');
  });

  it('exposes the lifecycle trash with its dedicated permission and title', () => {
    expect(itemByRoute('/trash')).toMatchObject({
      label: 'Papelera',
      implemented: true,
      requiredPermission: 'lifecycle:read'
    });
    expect(routeTitle('/trash')).toBe('Papelera');
  });

  it('uses the valid document icon path for Kardex', () => {
    expect(itemByRoute('/placeholder?module=Kardex')?.icon).toBe(
      'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z'
    );
  });
});
