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
  trend: number[];
  openedAt: string;
}

export const BRANCHES: Branch[] = [
  {
    id: 'br-001', code: 'SAL-01', name: 'Matriz Central', address: 'Calle El Progreso #12, Col. Escalón',
    city: 'San Salvador', phone: '+503 2222-1000', manager: 'Ana García', managerInitials: 'AG',
    lat: 13.6989, lng: -89.1914, status: 'active', employees: 47, warehouses: 3,
    salesThisMonth: 48250, trend: [30, 34, 38, 36, 40, 44, 48], openedAt: '04 Ene, 2018',
  },
  {
    id: 'br-002', code: 'SON-01', name: 'Sucursal Sonsonate', address: 'Av. Independencia #45, Barrio Centro',
    city: 'Sonsonate', phone: '+503 2450-3300', manager: 'Carlos López', managerInitials: 'CL',
    lat: 13.7189, lng: -89.7286, status: 'active', employees: 22, warehouses: 2,
    salesThisMonth: 28800, trend: [20, 22, 21, 24, 26, 27, 28], openedAt: '15 Ago, 2019',
  },
  {
    id: 'br-003', code: 'SAM-01', name: 'Sucursal San Miguel', address: 'Barra Av. Roosevelt #78',
    city: 'San Miguel', phone: '+503 2665-2200', manager: 'María Fernández', managerInitials: 'MF',
    lat: 13.4833, lng: -88.1833, status: 'active', employees: 18, warehouses: 1,
    salesThisMonth: 19500, trend: [10, 12, 13, 15, 16, 18, 19.5], openedAt: '22 Nov, 2021',
  },
  {
    id: 'br-004', code: 'STA-01', name: 'Sucursal Santa Ana', address: '5ta Calle Poniente #22',
    city: 'Santa Ana', phone: '+503 2440-1180', manager: 'Juan Pérez', managerInitials: 'JP',
    lat: 13.9942, lng: -89.5583, status: 'maintenance', employees: 12, warehouses: 1,
    salesThisMonth: 0, trend: [14, 13, 12, 10, 8, 6, 0], openedAt: '09 Mar, 2020',
  },
  {
    id: 'br-005', code: 'CHL-01', name: 'Sucursal Chalatenango', address: 'Barrio El Calvario',
    city: 'Chalatenango', phone: '+503 2301-4400', manager: 'Laura Torres', managerInitials: 'LT',
    lat: 14.0333, lng: -88.9333, status: 'inactive', employees: 0, warehouses: 0,
    salesThisMonth: 0, trend: [0, 0, 0, 0, 0, 0, 0], openedAt: '—',
  },
  {
    id: 'br-006', code: 'USU-01', name: 'Sucursal Usulután', address: 'Zona Franca, Nave 4',
    city: 'Usulután', phone: '+503 2662-0900', manager: 'Roberto Rivas', managerInitials: 'RR',
    lat: 13.3500, lng: -88.4500, status: 'active', employees: 25, warehouses: 2,
    salesThisMonth: 34100, trend: [18, 20, 25, 27, 30, 32, 34], openedAt: '12 Feb, 2020',
  },
  {
    id: 'br-007', code: 'AHU-01', name: 'Sucursal Ahuachapán', address: 'Calle 2ª Poniente #18',
    city: 'Ahuachapán', phone: '+503 2413-8800', manager: 'Elena Martínez', managerInitials: 'EM',
    lat: 13.9214, lng: -89.8450, status: 'active', employees: 15, warehouses: 1,
    salesThisMonth: 16800, trend: [10, 11, 13, 14, 15, 16, 16.8], openedAt: '05 Jun, 2021',
  },
  {
    id: 'br-008', code: 'COJ-01', name: 'Sucursal Cojutepeque', address: 'Av. Raúl Contreras #10',
    city: 'Cojutepeque', phone: '+503 2372-5500', manager: 'Gabriel Aguilar', managerInitials: 'GA',
    lat: 13.7214, lng: -88.9833, status: 'active', employees: 14, warehouses: 1,
    salesThisMonth: 14900, trend: [9, 10, 11, 13, 14, 14.5, 14.9], openedAt: '19 Oct, 2021',
  },
  {
    id: 'br-009', code: 'ZAC-01', name: 'Sucursal Zacatecoluca', address: 'Km 56 Carretera a San Salvador',
    city: 'Zacatecoluca', phone: '+503 2334-1200', manager: 'Sofía Benítez', managerInitials: 'SB',
    lat: 13.5083, lng: -88.8667, status: 'active', employees: 16, warehouses: 1,
    salesThisMonth: 18200, trend: [11, 12, 14, 15, 17, 18, 18.2], openedAt: '03 Ene, 2022',
  },
  {
    id: 'br-010', code: 'LIB-01', name: 'Sucursal La Libertad', address: 'Boulevard El Faro #88',
    city: 'La Libertad', phone: '+503 2347-9000', manager: 'Diego Castillo', managerInitials: 'DC',
    lat: 13.4883, lng: -89.3222, status: 'active', employees: 29, warehouses: 2,
    salesThisMonth: 41500, trend: [24, 28, 32, 35, 38, 40, 41.5], openedAt: '28 Abr, 2019',
  },
  {
    id: 'br-011', code: 'SOY-01', name: 'Sucursal Soyapango', address: 'Plaza Unicentro, Local 14',
    city: 'Soyapango', phone: '+503 2277-3310', manager: 'Patricia Orellana', managerInitials: 'PO',
    lat: 13.7100, lng: -89.1400, status: 'active', employees: 31, warehouses: 2,
    salesThisMonth: 39800, trend: [26, 29, 31, 34, 36, 38, 39.8], openedAt: '17 Sep, 2018',
  },
  {
    id: 'br-012', code: 'UNI-01', name: 'Sucursal La Unión', address: 'Puerto Corsario #2',
    city: 'La Unión', phone: '+503 2604-1190', manager: 'Mario Morales', managerInitials: 'MM',
    lat: 13.3333, lng: -87.8433, status: 'maintenance', employees: 9, warehouses: 1,
    salesThisMonth: 0, trend: [10, 8, 5, 3, 1, 0, 0], openedAt: '11 Nov, 2022',
  },
  {
    id: 'br-013', code: 'VIC-01', name: 'Sucursal San Vicente', address: 'Barrio El Santuario #3',
    city: 'San Vicente', phone: '+503 2393-0040', manager: 'Claudia Mendoza', managerInitials: 'CM',
    lat: 13.6333, lng: -88.7833, status: 'active', employees: 17, warehouses: 1,
    salesThisMonth: 15600, trend: [10, 11, 12, 13, 14, 15, 15.6], openedAt: '20 Jul, 2021',
  },
];

export const STATUS_MAP: Record<string, { label: string; variant: 'success' | 'neutral' | 'warning' }> = {
  active: { label: 'Activa', variant: 'success' },
  inactive: { label: 'Inactiva', variant: 'neutral' },
  maintenance: { label: 'Mantenimiento', variant: 'warning' },
};