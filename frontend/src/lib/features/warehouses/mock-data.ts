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
}

export const WAREHOUSES: Warehouse[] = [
  { id: 'wh-01', code: 'ALM-SAL-01', name: 'Almacén Central A', branchId: 'br-001', branchName: 'Matriz Central', location: 'Bodega A, Planta Baja', capacity: 5000, used: 4200, status: 'active', products: 1284, lastMovement: 'hace 12 min' },
  { id: 'wh-02', code: 'ALM-SAL-02', name: 'Almacén Central B', branchId: 'br-001', branchName: 'Matriz Central', location: 'Bodega B, Nivel 1', capacity: 3000, used: 2950, status: 'full', products: 842, lastMovement: 'hace 5 min' },
  { id: 'wh-03', code: 'ALM-SAL-03', name: 'Almacén Tránsito', branchId: 'br-001', branchName: 'Matriz Central', location: 'Andén de carga', capacity: 800, used: 320, status: 'active', products: 156, lastMovement: 'hace 1 h' },
  { id: 'wh-04', code: 'ALM-SON-01', name: 'Almacén Sonsonate', branchId: 'br-002', branchName: 'Sucursal Sonsonate', location: 'Bodega principal', capacity: 2500, used: 1800, status: 'active', products: 620, lastMovement: 'hace 2 h' },
  { id: 'wh-05', code: 'ALM-SON-02', name: 'Almacén Sonsonate B', branchId: 'br-002', branchName: 'Sucursal Sonsonate', location: 'Bodega secundaria', capacity: 1200, used: 0, status: 'maintenance', products: 0, lastMovement: 'hace 3 días' },
  { id: 'wh-06', code: 'ALM-SAM-01', name: 'Almacén San Miguel', branchId: 'br-003', branchName: 'Sucursal San Miguel', location: 'Bodega principal', capacity: 2000, used: 1450, status: 'active', products: 430, lastMovement: 'hace 45 min' },
  { id: 'wh-07', code: 'ALM-STA-01', name: 'Almacén Santa Ana', branchId: 'br-004', branchName: 'Sucursal Santa Ana', location: 'Bodega principal', capacity: 1500, used: 890, status: 'active', products: 312, lastMovement: 'hace 3 h' },
];

export const STATUS_MAP: Record<string, { label: string; variant: 'success' | 'neutral' | 'warning' | 'danger' }> = {
  active: { label: 'Activo', variant: 'success' },
  full: { label: 'Lleno', variant: 'danger' },
  maintenance: { label: 'Mantenimiento', variant: 'warning' },
};

export function utilizationPct(wh: Warehouse): number {
  return Math.round((wh.used / wh.capacity) * 100);
}

export function utilizationColor(pct: number): string {
  if (pct > 90) return '239 68 68';
  if (pct > 70) return '237 151 39';
  return '0 168 107';
}