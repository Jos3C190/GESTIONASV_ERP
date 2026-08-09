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
  '/suppliers': 'Proveedores',
  '/products': 'Productos',
  '/inventory/categories': 'Categorías de productos',
  '/inventory/units': 'Unidades de medida',
  '/placeholder': 'Módulo'
};

export function routeTitle(pathname: string): string {
  // Check exact match first
  if (TITLES[pathname]) return TITLES[pathname];
  // Sub-rutas de empleados (crear / editar / detalle) -> "Empleados"
  if (pathname.startsWith('/employees')) return TITLES['/employees'] ?? 'Empleados';
  // Sub-rutas de sucursales (detalle) -> "Sucursales"
  if (pathname.startsWith('/branches')) return TITLES['/branches'] ?? 'Sucursales';
  // Sub-rutas de almacenes (detalle) -> "Almacenes"
  if (pathname.startsWith('/warehouses')) return TITLES['/warehouses'] ?? 'Almacenes';
  if (pathname.startsWith('/warehouse-categories'))
    return TITLES['/warehouse-categories'] ?? 'Categorías de almacén';
  if (pathname.startsWith('/suppliers')) return TITLES['/suppliers'] ?? 'Proveedores';
  if (pathname.startsWith('/products')) return TITLES['/products'] ?? 'Productos';
  if (pathname.startsWith('/inventory/categories'))
    return TITLES['/inventory/categories'] ?? 'Categorías de productos';
  if (pathname.startsWith('/inventory/units'))
    return TITLES['/inventory/units'] ?? 'Unidades de medida';
  // Check prefix for /placeholder?module=X
  for (const key of Object.keys(TITLES)) {
    if (pathname.startsWith(key)) return TITLES[key] ?? '';
  }
  return '';
}
