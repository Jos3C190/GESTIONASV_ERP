import { NAV_GROUPS, type NavItem } from '#lib/navigation.ts';

interface PermissionReader {
  readonly isSuperuser: boolean;
  hasPermission(code: string): boolean;
  hasAnyPermission(codes: string[]): boolean;
}

function grantedBy(item: NavItem, permissions: PermissionReader): boolean {
  if (item.requiredPermissions?.length)
    return permissions.hasAnyPermission(item.requiredPermissions);
  if (item.requiredPermission) return permissions.hasPermission(item.requiredPermission);
  return false;
}

/**
 * Un cajero cuyo único módulo con permiso es el punto de venta trabaja en la caja a pantalla
 * completa: entra directo y no ve el menú del ERP. Las entradas sin permiso propio (Dashboard,
 * pendientes) no cuentan.
 */
export function isPosWorkspace(permissions: PermissionReader): boolean {
  if (permissions.isSuperuser) return false;
  if (!permissions.hasAnyPermission(['pos:sell', 'pos:shift_open'])) return false;
  const granted = NAV_GROUPS.flatMap((group) => group.items).filter((item) =>
    grantedBy(item, permissions)
  );
  return granted.length > 0 && granted.every((item) => item.route === '/pos');
}

/** Quien solo tiene módulos del punto de venta (p. ej. un supervisor de tienda) entra a la caja. */
export function hasOnlyPosModules(permissions: PermissionReader): boolean {
  if (permissions.isSuperuser) return false;
  const granted = NAV_GROUPS.flatMap((group) => group.items).filter((item) =>
    grantedBy(item, permissions)
  );
  return (
    granted.some((item) => item.route === '/pos') &&
    granted.every((item) => item.route === '/pos' || item.route.startsWith('/pos/'))
  );
}
