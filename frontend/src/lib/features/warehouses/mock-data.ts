// MOCK DATA — Almacenes. Reemplazar por llamadas a la API cuando exista el módulo.

export interface Warehouse {
  id: string;
  code: string;
  name: string;
  branchId: string;
  branchName: string;
  location: string;
  capacity: number;
  used: number;
  status: 'active' | 'full' | 'maintenance';
  products: number;
  lastMovement: string;
  trend?: number[];
}

export const WAREHOUSES: Warehouse[] = [
  { id: 'wh-01', code: 'ALM-SAL-01', name: 'Almacén Central A', branchId: 'br-001', branchName: 'Matriz Central', location: 'Bodega A, Planta Baja', capacity: 5000, used: 4200, status: 'active', products: 1284, lastMovement: 'hace 12 min', trend: [52, 58, 61, 70, 66, 78, 84] },
  { id: 'wh-02', code: 'ALM-SAL-02', name: 'Almacén Central B', branchId: 'br-001', branchName: 'Matriz Central', location: 'Bodega B, Nivel 1', capacity: 3000, used: 2950, status: 'full', products: 842, lastMovement: 'hace 5 min', trend: [70, 74, 80, 85, 90, 95, 98] },
  { id: 'wh-03', code: 'ALM-SAL-03', name: 'Almacén Tránsito', branchId: 'br-001', branchName: 'Matriz Central', location: 'Andén de carga', capacity: 800, used: 320, status: 'active', products: 156, lastMovement: 'hace 1 h', trend: [60, 50, 45, 38, 42, 35, 40] },
  { id: 'wh-04', code: 'ALM-SON-01', name: 'Almacén Sonsonate', branchId: 'br-002', branchName: 'Sucursal Sonsonate', location: 'Bodega principal', capacity: 2500, used: 1800, status: 'active', products: 620, lastMovement: 'hace 2 h', trend: [55, 60, 63, 68, 70, 71, 72] },
  { id: 'wh-05', code: 'ALM-SON-02', name: 'Almacén Sonsonate B', branchId: 'br-002', branchName: 'Sucursal Sonsonate', location: 'Bodega secundaria', capacity: 1200, used: 0, status: 'maintenance', products: 0, lastMovement: 'hace 3 días', trend: [30, 20, 10, 0, 0, 0, 0] },
  { id: 'wh-06', code: 'ALM-SAM-01', name: 'Almacén San Miguel', branchId: 'br-003', branchName: 'Sucursal San Miguel', location: 'Bodega principal', capacity: 2000, used: 1450, status: 'active', products: 430, lastMovement: 'hace 45 min', trend: [65, 68, 70, 72, 71, 73, 73] },
  { id: 'wh-07', code: 'ALM-STA-01', name: 'Almacén Santa Ana', branchId: 'br-004', branchName: 'Sucursal Santa Ana', location: 'Bodega principal', capacity: 1500, used: 890, status: 'active', products: 312, lastMovement: 'hace 3 h', trend: [48, 50, 53, 55, 57, 58, 59] },
  { id: 'wh-08', code: 'ALM-USU-01', name: 'Almacén Usulután', branchId: 'br-005', branchName: 'Sucursal Usulután', location: 'Zona Franca, Nave 2', capacity: 2200, used: 2156, status: 'full', products: 512, lastMovement: 'hace 18 min', trend: [80, 85, 88, 92, 95, 97, 98] },
  { id: 'wh-09', code: 'ALM-COJ-01', name: 'Almacén Cojutepeque', branchId: 'br-006', branchName: 'Sucursal Cojutepeque', location: 'Bodega Central', capacity: 1600, used: 1120, status: 'active', products: 290, lastMovement: 'hace 4 h', trend: [50, 55, 60, 64, 68, 70, 70] },
  { id: 'wh-10', code: 'ALM-AHU-01', name: 'Almacén Ahuachapán', branchId: 'br-007', branchName: 'Sucursal Ahuachapán', location: 'Bodega Norte', capacity: 1800, used: 1152, status: 'active', products: 340, lastMovement: 'hace 1 h', trend: [40, 48, 52, 58, 60, 62, 64] },
  { id: 'wh-11', code: 'ALM-CHA-01', name: 'Almacén Chalatenango', branchId: 'br-008', branchName: 'Sucursal Chalatenango', location: 'Bodega Sur', capacity: 1000, used: 0, status: 'maintenance', products: 0, lastMovement: 'hace 5 días', trend: [20, 10, 0, 0, 0, 0, 0] },
  { id: 'wh-12', code: 'ALM-ZAC-01', name: 'Almacén Zacatecoluca', branchId: 'br-009', branchName: 'Sucursal Zacatecoluca', location: 'Bodega A', capacity: 1400, used: 812, status: 'active', products: 210, lastMovement: 'hace 6 h', trend: [45, 49, 52, 55, 56, 57, 58] },
  { id: 'wh-13', code: 'ALM-SVT-01', name: 'Almacén San Vicente', branchId: 'br-010', branchName: 'Sucursal San Vicente', location: 'Bodega B', capacity: 1300, used: 741, status: 'active', products: 195, lastMovement: 'hace 2 días', trend: [40, 44, 48, 52, 55, 56, 57] },
  { id: 'wh-14', code: 'ALM-GOT-01', name: 'Almacén Gotera', branchId: 'br-011', branchName: 'Sucursal San Francisco Gotera', location: 'Bodega Principal', capacity: 1100, used: 594, status: 'active', products: 170, lastMovement: 'hace 1 día', trend: [35, 40, 45, 48, 50, 52, 54] },
];

export const STATUS_MAP: Record<string, { label: string; variant: 'success' | 'neutral' | 'warning' | 'danger' }> = {
  active: { label: 'Activo', variant: 'success' },
  full: { label: 'Lleno', variant: 'danger' },
  maintenance: { label: 'Mantenimiento', variant: 'warning' },
};

export function utilizationPct(wh: Warehouse): number {
  if (wh.capacity <= 0) return 0;
  return Math.round((wh.used / wh.capacity) * 100);
}

export function utilizationColor(pct: number): string {
  if (pct >= 90) return '239 68 68'; // danger
  if (pct >= 70) return '237 151 39'; // warning
  return '0 168 107'; // success
}

export function getCapacityVariant(pct: number, status: string): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'maintenance') return 'neutral';
  if (pct >= 90) return 'danger';
  if (pct >= 70) return 'warning';
  return 'success';
}

export function getShortWarehouseName(fullName: string): string {
  return fullName.replace(/^Almacén\s+/i, '');
}