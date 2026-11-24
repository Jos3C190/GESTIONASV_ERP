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
  '/privacy': 'Datos personales',
  '/suppliers': 'Proveedores',
  '/customers': 'Clientes',
  '/customers/new': 'Nuevo cliente',
  '/sales/quotations': 'Cotizaciones de venta',
  '/sales/returns': 'Devoluciones',
  '/sales/fiscal-documents': 'Documentos fiscales',
  '/sales/contingencies': 'Contingencia',
  '/sales/fiscal-settings': 'Configuración fiscal',
  '/sales/price-lists': 'Listas de precios',
  '/sales/discount-policies': 'Topes de descuento',
  '/sales/promotions': 'Promociones por sucursal',
  '/sales': 'Pedidos',
  '/purchase-requests': 'Solicitudes de compra',
  '/purchase-quotations': 'Cotizaciones de compra',
  '/purchase-orders': 'Órdenes de compra',
  '/purchases': 'Compras',
  '/retaceos': 'Retaceo',
  '/products': 'Productos',
  '/inventory/categories': 'Categorías de productos',
  '/inventory/units': 'Unidades de medida',
  '/inventory/valuation': 'Valoración de inventario',
  '/inventory/adjustments': 'Ajustes de inventario',
  '/inventory/kardex': 'Kardex',
  '/inventory': 'Inventario',
  '/transfers': 'Traslados',
  '/transfers/settings': 'Reglas de traslados',
  '/purchase-consolidations': 'Consolidados de compra',
  '/expense-types': 'Tipos de gasto',
  '/trash': 'Papelera',
  '/fleet': 'Flota',
  '/fleet/new': 'Nuevo vehículo',
  '/fleet/types': 'Tipos de vehículo',
  '/fleet/inspection-items': 'Puntos de inspección',
  '/fleet/settings': 'Reglas de flota',
  '/fleet/costs': 'Costos de flota',
  '/drivers': 'Conductores',
  '/tracking': 'Seguimiento',
  '/placeholder': 'Módulo'
};

export function routeTitle(pathname: string): string {
  // Check exact match first
  if (TITLES[pathname]) return TITLES[pathname];
  // Gestión de estructuras físicas dentro de un almacén
  if (/^\/customers\/[^/]+\/?$/.test(pathname)) return 'Clientes';
  if (/^\/fleet\/[^/]+\/edit\/?$/.test(pathname)) return 'Editar vehículo';
  if (/^\/fleet\/[^/]+\/?$/.test(pathname)) return 'Flota';
  if (/^\/drivers\/[^/]+\/?$/.test(pathname)) return 'Conductores';
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
  if (pathname.startsWith('/sales/price-lists'))
    return TITLES['/sales/price-lists'] ?? 'Listas de precios';
  if (pathname.startsWith('/sales/fiscal-documents'))
    return TITLES['/sales/fiscal-documents'] ?? 'Documentos fiscales';
  if (pathname.startsWith('/sales/quotations'))
    return TITLES['/sales/quotations'] ?? 'Cotizaciones de venta';
  if (pathname.startsWith('/sales')) return TITLES['/sales'] ?? 'Ventas';
  if (pathname.startsWith('/purchase-consolidations'))
    return TITLES['/purchase-consolidations'] ?? 'Consolidados de compra';
  if (pathname.startsWith('/products')) return TITLES['/products'] ?? 'Productos';
  if (pathname.startsWith('/inventory/categories'))
    return TITLES['/inventory/categories'] ?? 'Categorías de productos';
  if (pathname.startsWith('/inventory/units'))
    return TITLES['/inventory/units'] ?? 'Unidades de medida';
  if (pathname.startsWith('/inventory/handling-units')) return 'Trazabilidad de inventario';
  if (pathname.startsWith('/inventory/adjustments'))
    return TITLES['/inventory/adjustments'] ?? 'Ajustes de inventario';
  // Check prefix for /placeholder?module=X
  for (const key of Object.keys(TITLES)) {
    if (pathname.startsWith(key)) return TITLES[key] ?? '';
  }
  return '';
}
