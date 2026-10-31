/**
 * Route titles — maps the current path to a human-readable module name
 * for the header breadcrumb. Used by the (app) layout.
 */
const TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/users': 'Usuarios',
  '/roles': 'Roles y permisos',
  '/employees': 'Empleados',
  '/departments': 'Departamentos',
  '/branches': 'Sucursales',
  '/warehouses': 'Almacenes',
  '/warehouse-categories': 'Categorías de almacén',
  '/audit-log': 'Bitácora',
  '/documents': 'Documentos',
  '/suppliers': 'Proveedores',
  '/customers': 'Clientes',
  '/sales/quotations': 'Cotizaciones de venta',
  '/sales': 'Ventas',
  '/products': 'Productos',
  '/inventory/categories': 'Categorías de productos',
  '/inventory/units': 'Unidades de medida',
  '/inventory/valuation': 'Valoración de inventario',
  '/inventory/adjustments': 'Ajustes de inventario',
  '/transfers': 'Traslados',
  '/purchase-consolidations': 'Consolidados de compra',
  '/expense-types': 'Tipos de gasto',
  '/trash': 'Papelera',
  '/placeholder': 'Módulo'
};

export function routeTitle(pathname: string): string {
  // Check exact match first
  if (TITLES[pathname]) return TITLES[pathname];
  // Gestión de estructuras físicas dentro de un almacén
  if (/^\/warehouses\/[^/]+\/structures\/?$/.test(pathname)) {
    return 'Estructuras y límites compartidos';
  }
  if (/^\/warehouses\/[^/]+\/locations\/new\/?$/.test(pathname)) return 'Nueva ubicación';
  if (/^\/warehouses\/[^/]+\/locations\/generate\/?$/.test(pathname)) {
    return 'Generar ubicaciones por rangos';
  }
  if (/^\/warehouses\/[^/]+\/locations\/[^/]+\/edit\/?$/.test(pathname)) {
    return 'Editar ubicación';
  }
  // Sub-rutas de empleados (crear / editar / detalle) -> "Empleados"
  if (pathname.startsWith('/employees')) return TITLES['/employees'] ?? 'Empleados';
  if (pathname.startsWith('/documents')) return TITLES['/documents'] ?? 'Documentos';
  // Sub-rutas de sucursales (detalle) -> "Sucursales"
  if (pathname.startsWith('/branches')) return TITLES['/branches'] ?? 'Sucursales';
  // Sub-rutas de almacenes (detalle) -> "Almacenes"
  if (pathname.startsWith('/warehouses')) return TITLES['/warehouses'] ?? 'Almacenes';
  if (pathname.startsWith('/warehouse-categories'))
    return TITLES['/warehouse-categories'] ?? 'Categorías de almacén';
  if (pathname.startsWith('/suppliers')) return TITLES['/suppliers'] ?? 'Proveedores';
  if (pathname.startsWith('/customers')) return TITLES['/customers'] ?? 'Clientes';
  if (pathname.startsWith('/sales/quotations')) return TITLES['/sales/quotations'] ?? 'Cotizaciones de venta';
  if (pathname.startsWith('/sales')) return TITLES['/sales'] ?? 'Ventas';
  if (pathname.startsWith('/purchase-consolidations'))
    return TITLES['/purchase-consolidations'] ?? 'Consolidados de compra';
  if (pathname.startsWith('/products')) return TITLES['/products'] ?? 'Productos';
  if (pathname.startsWith('/inventory/categories'))
    return TITLES['/inventory/categories'] ?? 'Categorías de productos';
  if (pathname.startsWith('/inventory/units'))
    return TITLES['/inventory/units'] ?? 'Unidades de medida';
  if (pathname.startsWith('/inventory/handling-units')) return 'Trazabilidad de inventario';
  if (pathname.startsWith('/inventory/adjustments')) return TITLES['/inventory/adjustments'] ?? 'Ajustes de inventario';
  // Check prefix for /placeholder?module=X
  for (const key of Object.keys(TITLES)) {
    if (pathname.startsWith(key)) return TITLES[key] ?? '';
  }
  return '';
}
