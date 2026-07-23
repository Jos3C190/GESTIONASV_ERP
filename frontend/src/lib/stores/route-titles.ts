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
  '/audit-log': 'Bitácora',
  '/placeholder': 'Módulo',
};

export function routeTitle(pathname: string): string {
  // Check exact match first
  if (TITLES[pathname]) return TITLES[pathname];
  // Check prefix for /placeholder?module=X
  for (const key of Object.keys(TITLES)) {
    if (pathname.startsWith(key)) return TITLES[key];
  }
  return '';
}