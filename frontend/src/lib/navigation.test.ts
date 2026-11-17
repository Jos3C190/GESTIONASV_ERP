import { describe, expect, it } from 'vitest';
import { NAV_GROUPS } from './navigation';
import { routeTitle } from './stores/route-titles';

function itemByRoute(route: string) {
  return NAV_GROUPS.flatMap((group) => group.items).find((item) => item.route === route);
}

describe('catalog navigation', () => {
  it('exposes the B06 commercial routes only with their own read permissions', () => {
    expect(itemByRoute('/customers')).toMatchObject({
      label: 'Clientes',
      implemented: true,
      requiredPermission: 'sales_customers:read'
    });
    expect(itemByRoute('/sales/quotations')).toMatchObject({
      label: 'Cotizaciones de venta',
      implemented: true,
      requiredPermission: 'sales_quotations:read'
    });
    expect(itemByRoute('/sales')).toMatchObject({
      label: 'Pedidos',
      implemented: true,
      requiredPermission: 'sales:read'
    });
    expect(routeTitle('/sales/quotations/quote-1/edit')).toBe('Cotizaciones de venta');
    expect(routeTitle('/sales/sale-1')).toBe('Pedidos');
    expect(itemByRoute('/sales/fiscal-documents')).toMatchObject({
      label: 'Documentos fiscales',
      implemented: true,
      requiredPermission: 'sales_invoices:read'
    });
    expect(routeTitle('/sales/fiscal-documents/doc-1')).toBe('Documentos fiscales');
  });

  it('exposes the DTE issuer settings with the fiscal read permission', () => {
    expect(itemByRoute('/sales/fiscal-settings')).toMatchObject({
      label: 'Configuración fiscal',
      implemented: true,
      requiredPermission: 'fiscal_settings:read'
    });
    expect(routeTitle('/sales/fiscal-settings')).toBe('Configuración fiscal');
  });

  it('exposes personal data protection under administration', () => {
    expect(itemByRoute('/privacy')).toMatchObject({
      label: 'Datos personales',
      implemented: true,
      requiredPermission: 'privacy:read'
    });
    expect(routeTitle('/privacy')).toBe('Datos personales');
  });

  it('exposes price lists under sales and drops the old placeholder', () => {
    expect(itemByRoute('/sales/price-lists')).toMatchObject({
      label: 'Listas de precios',
      implemented: true,
      requiredPermission: 'price_lists:read'
    });
    expect(routeTitle('/sales/price-lists/list-1')).toBe('Listas de precios');
    const labels = NAV_GROUPS.flatMap((group) => group.items).map((item) => item.label);
    expect(labels).not.toContain('Asignación de precios');
    expect(itemByRoute('/sales/discount-policies')).toMatchObject({
      label: 'Topes de descuento',
      requiredPermission: 'sales_discounts:manage'
    });
    expect(routeTitle('/sales/discount-policies')).toBe('Topes de descuento');
  });

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

  it('opens the implemented Kardex with physical inventory read permission', () => {
    expect(itemByRoute('/inventory/kardex')).toMatchObject({
      label: 'Kardex',
      implemented: true,
      requiredPermission: 'inventory:read'
    });
  });

  it('exposes the logistics modules with their own read permissions', () => {
    expect(itemByRoute('/fleet')).toMatchObject({
      implemented: true,
      requiredPermission: 'fleet:read'
    });
    expect(itemByRoute('/drivers')).toMatchObject({
      label: 'Conductores',
      implemented: true,
      requiredPermission: 'drivers:read'
    });
    expect(itemByRoute('/tracking')).toMatchObject({
      implemented: true,
      requiredPermission: 'tracking:read'
    });
    expect(routeTitle('/fleet/new')).toBe('Nuevo vehículo');
    expect(routeTitle('/fleet/v1/edit')).toBe('Editar vehículo');
    expect(routeTitle('/drivers/d1')).toBe('Conductores');
  });
  it('exposes the transfer rules only to people who can configure them', () => {
    expect(itemByRoute('/transfers')).toMatchObject({
      label: 'Traslados',
      requiredPermission: 'inventory:read'
    });
    expect(itemByRoute('/transfers/settings')).toMatchObject({
      label: 'Reglas de traslados',
      implemented: true,
      requiredPermission: 'inventory:transfer_settings'
    });
    expect(routeTitle('/transfers/settings')).toBe('Reglas de traslados');
    expect(routeTitle('/transfers')).toBe('Traslados');
  });

  it('gives every implemented module its sidebar label as the navbar title', () => {
    const implemented = NAV_GROUPS.flatMap((group) => group.items).filter(
      (item) => item.implemented
    );
    for (const item of implemented) {
      expect(routeTitle(item.route), item.route).toBe(item.label);
    }
  });

  it('keeps the module title on purchase sub-pages', () => {
    expect(routeTitle('/purchase-quotations/q1/response')).toBe('Cotizaciones de compra');
    expect(routeTitle('/purchase-orders/o1/edit')).toBe('Órdenes de compra');
    expect(routeTitle('/purchases/new')).toBe('Compras');
    expect(routeTitle('/retaceos/r1')).toBe('Retaceo');
  });
});
