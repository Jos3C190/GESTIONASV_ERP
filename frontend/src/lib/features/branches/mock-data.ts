// MOCK DATA — Sucursales. Reemplazar por llamadas a la API cuando exista el módulo.

export interface Branch {
  id: string;
  code: string;
  name: string;
  address: string;
  city: string;
  phone: string;
  manager: string;
  managerInitials: string;
  lat: number;
  lng: number;
  status: 'active' | 'inactive' | 'maintenance';
  employees: number;
  warehouses: number;
  salesThisMonth: number;
  openedAt: string;
}

export const BRANCHES: Branch[] = [
  {
    id: 'br-001', code: 'SAL-01', name: 'Matriz Central', address: 'Av. Las Magnolias #45, Col. Escalón',
    city: 'San Salvador', phone: '+503 2222-3300', manager: 'Ana García', managerInitials: 'AG',
    lat: 13.6989, lng: -89.1914, status: 'active', employees: 47, warehouses: 3,
    salesThisMonth: 48250, openedAt: '15 Mar, 2018',
  },
  {
    id: 'br-002', code: 'SON-01', name: 'Sucursal Sonsonate', address: 'Calle a Izalco #12, Barrio Centro',
    city: 'Sonsonate', phone: '+503 2433-1100', manager: 'Carlos López', managerInitials: 'CL',
    lat: 13.7189, lng: -89.7286, status: 'active', employees: 22, warehouses: 2,
    salesThisMonth: 28800, openedAt: '08 Jul, 2020',
  },
  {
    id: 'br-003', code: 'SAM-01', name: 'Sucursal San Miguel', address: 'Barra Av. Roosevelt #78',
    city: 'San Miguel', phone: '+503 2665-2200', manager: 'María Fernández', managerInitials: 'MF',
    lat: 13.4833, lng: -88.1833, status: 'active', employees: 18, warehouses: 1,
    salesThisMonth: 19500, openedAt: '22 Nov, 2021',
  },
  {
    id: 'br-004', code: 'STA-01', name: 'Sucursal Santa Ana', address: 'Av. Independencia #34',
    city: 'Santa Ana', phone: '+503 2440-3300', manager: 'Juan Pérez', managerInitials: 'JP',
    lat: 13.9942, lng: -89.5583, status: 'maintenance', employees: 12, warehouses: 1,
    salesThisMonth: 0, openedAt: '10 Ene, 2022',
  },
  {
    id: 'br-005', code: 'CHL-01', name: 'Sucursal Chalatenango', address: 'Calle Principal #5',
    city: 'Chalatenango', phone: '+503 2639-4400', manager: 'Laura Torres', managerInitials: 'LT',
    lat: 14.0333, lng: -88.9333, status: 'inactive', employees: 0, warehouses: 0,
    salesThisMonth: 0, openedAt: '05 May, 2023',
  },
];

export const STATUS_MAP: Record<string, { label: string; variant: 'success' | 'neutral' | 'warning' }> = {
  active: { label: 'Activa', variant: 'success' },
  inactive: { label: 'Inactiva', variant: 'neutral' },
  maintenance: { label: 'Mantenimiento', variant: 'warning' },
};