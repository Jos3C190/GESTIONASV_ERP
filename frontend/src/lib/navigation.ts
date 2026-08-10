/**
 * Navigation metadata — single source of truth for the sidebar.
 *
 * Implemented modules route to real pages. Future modules route to the
 * placeholder '/placeholder' with a module label. The sidebar filters items
 * by requiredPermission (using the permissions store); items without a
 * matching permission are hidden for non-superusers.
 *
 * Icons are inline SVG paths (Lucide-style) to avoid a runtime icon dependency.
 */

export interface NavItem {
  label: string;
  icon: string; // SVG path data
  route: string;
  implemented: boolean;
  requiredPermission?: string;
  module?: string; // for the placeholder
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

// SVG icon paths (24x24 viewBox, stroke-based, Lucide-style).
const ICONS = {
  dashboard:
    'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
  users:
    'M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-2a4 4 0 100-8 4 4 0 000 8zm6 0a3 3 0 100-6 3 3 0 000 6zm-12 0a3 3 0 100-6 3 3 0 000 6z',
  roles: 'M12 15a3 3 0 100-6 3 3 0 000 6z M19 12a7 7 0 11-14 0 7 7 0 0114 0z',
  employees: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
  departments:
    'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5',
  audit:
    'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
  clients: 'M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-2a4 4 0 100-8 4 4 0 000 8z',
  suppliers: 'M3 7l3-3h12l3 3M3 7l3 3h12l3-3M3 7v10a2 2 0 002 2h14a2 2 0 002-2V7',
  products: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4',
  purchaseQuotes:
    'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
  purchaseOrders: 'M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z',
  purchases:
    'M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z',
  retazeo:
    'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10',
  pricing:
    'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  inventory: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4',
  warehouses: 'M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3m4-3v3m4-3v3',
  branches:
    'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5',
  transfers: 'M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4',
  salesQuotes:
    'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
  sales:
    'M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z',
  returns: 'M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6',
  fleet:
    'M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1',
  kardex:
    'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2 M9 5a2 2 0 012-2h2a2 2 0 012 2 M9 5a2 2 0 002 2h2a2 2 000-2 M7 11h10M7 15h10',
  settings:
    'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z'
};

export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Principal',
    items: [{ label: 'Dashboard', icon: ICONS.dashboard, route: '/dashboard', implemented: true }]
  },
  {
    label: 'Administración',
    items: [
      {
        label: 'Usuarios',
        icon: ICONS.users,
        route: '/users',
        implemented: true,
        requiredPermission: 'users:read'
      },
      {
        label: 'Roles y permisos',
        icon: ICONS.roles,
        route: '/roles',
        implemented: true,
        requiredPermission: 'roles:read'
      },
      {
        label: 'Bitácora',
        icon: ICONS.audit,
        route: '/audit-log',
        implemented: true,
        requiredPermission: 'logs.view'
      }
    ]
  },
  {
    label: 'Recursos Humanos',
    items: [
      {
        label: 'Empleados',
        icon: ICONS.employees,
        route: '/employees',
        implemented: true,
        requiredPermission: 'employees:read'
      },
      {
        label: 'Departamentos',
        icon: ICONS.departments,
        route: '/departments',
        implemented: true,
        requiredPermission: 'employees:read'
      }
    ]
  },
  {
    label: 'Compras',
    items: [
      {
        label: 'Clientes',
        icon: ICONS.clients,
        route: '/placeholder?module=Clientes',
        implemented: false,
        module: 'Clientes'
      },
      {
        label: 'Proveedores',
        icon: ICONS.suppliers,
        route: '/suppliers',
        implemented: true,
        requiredPermission: 'suppliers:read'
      },
      {
        label: 'Productos',
        icon: ICONS.products,
        route: '/products',
        implemented: true,
        requiredPermission: 'products:read'
      },
      {
        label: 'Categorías de productos',
        icon: ICONS.inventory,
        route: '/inventory/categories',
        implemented: true,
        requiredPermission: 'products:read'
      },
      {
        label: 'Unidades de medida',
        icon: ICONS.pricing,
        route: '/inventory/units',
        implemented: true,
        requiredPermission: 'units:read'
      },
      {
        label: 'Cotizaciones de compra',
        icon: ICONS.purchaseQuotes,
        route: '/placeholder?module=Cotizaciones de compra',
        implemented: false,
        module: 'Cotizaciones de compra'
      },
      {
        label: 'Órdenes de compra',
        icon: ICONS.purchaseOrders,
        route: '/placeholder?module=Órdenes de compra',
        implemented: false,
        module: 'Órdenes de compra'
      },
      {
        label: 'Compras',
        icon: ICONS.purchases,
        route: '/placeholder?module=Compras',
        implemented: false,
        module: 'Compras'
      },
      {
        label: 'Retaceo',
        icon: ICONS.retazeo,
        route: '/placeholder?module=Retaceo',
        implemented: false,
        module: 'Retaceo'
      },
      {
        label: 'Asignación de precios',
        icon: ICONS.pricing,
        route: '/placeholder?module=Asignación de precios',
        implemented: false,
        module: 'Asignación de precios'
      }
    ]
  },
  {
    label: 'Inventario',
    items: [
      {
        label: 'Inventario',
        icon: ICONS.inventory,
        route: '/placeholder?module=Inventario',
        implemented: false,
        module: 'Inventario'
      },
      { label: 'Almacenes', icon: ICONS.warehouses, route: '/warehouses', implemented: true, requiredPermission: 'warehouses.view' },
      { label: 'Categorías de almacén', icon: ICONS.inventory, route: '/warehouse-categories', implemented: true, requiredPermission: 'warehouse_categories.view' },
      { label: 'Sucursales', icon: ICONS.branches, route: '/branches', implemented: true, requiredPermission: 'branches.view' },
      {
        label: 'Traslados',
        icon: ICONS.transfers,
        route: '/placeholder?module=Traslados',
        implemented: false,
        module: 'Traslados'
      }
    ]
  },
  {
    label: 'Ventas',
    items: [
      {
        label: 'Cotizaciones de venta',
        icon: ICONS.salesQuotes,
        route: '/placeholder?module=Cotizaciones de venta',
        implemented: false,
        module: 'Cotizaciones de venta'
      },
      {
        label: 'Ventas',
        icon: ICONS.sales,
        route: '/placeholder?module=Ventas',
        implemented: false,
        module: 'Ventas'
      },
      {
        label: 'Devoluciones',
        icon: ICONS.returns,
        route: '/placeholder?module=Devoluciones',
        implemented: false,
        module: 'Devoluciones'
      }
    ]
  },
  {
    label: 'Logística',
    items: [
      {
        label: 'Flota y conductores',
        icon: ICONS.fleet,
        route: '/placeholder?module=Flota y conductores',
        implemented: false,
        module: 'Flota y conductores'
      },
      {
        label: 'Kardex',
        icon: ICONS.kardex,
        route: '/placeholder?module=Kardex',
        implemented: false,
        module: 'Kardex'
      }
    ]
  },
  {
    label: 'Sistema',
    items: [
      {
        label: 'Configuración',
        icon: ICONS.settings,
        route: '/placeholder?module=Configuración',
        implemented: false,
        module: 'Configuración'
      }
    ]
  }
];
