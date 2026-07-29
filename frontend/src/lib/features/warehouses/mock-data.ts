// MOCK DATA — Almacenes. Reemplazar por llamadas a la API cuando exista el módulo.

export type WarehouseStatus = 'active' | 'full' | 'maintenance' | 'inactive';
export type WarehouseType = 'general' | 'cold_storage' | 'hazmat' | 'transit' | 'bonded' | 'automated';
export type AccessControlType = 'biometrico' | 'tarjetas' | 'teclado' | 'doble_llave' | 'sin_control';
export type CoolingType = 'industrial_ac' | 'refrigeracion' | 'ventilacion_natural' | 'mixto' | 'sin_climatizacion';

export interface WarehouseProduct {
  sku: string;
  name: string;
  category: string;
  quantity: number;
  unit: string;
  minStock: number;
  maxStock: number;
  expiryDate: string | null;
}

export interface WarehouseMovement {
  id: string;
  date: string;
  type: 'inbound' | 'outbound' | 'transfer' | 'adjustment';
  productSku: string;
  productName: string;
  quantity: number;
  operator: string;
  reference: string;
}

export interface Warehouse {
  // Identidad
  id: string;
  code: string;
  name: string;
  type: WarehouseType;
  status: WarehouseStatus;
  location: string;
  // Sucursal
  branchId: string;
  branchName: string;
  branchAddress: string;
  // Dimensiones físicas
  area: number;
  height: number;
  length: number;
  width: number;
  shelvesTotal: number;
  shelvesOccupied: number;
  // Capacidad y operaciones
  capacity: number;
  used: number;
  products: number;
  // Personal
  manager: string;
  managerInitials: string;
  operators: number;
  shifts: ('mañana' | 'tarde' | 'noche')[];
  // Inventario
  totalSKUs: number;
  topCategories: string[];
  lowStockItems: number;
  expiringItems: number;
  inventoryValue: number;
  inventoryTurnover: number;
  // Movimientos
  lastMovement: string;
  inboundThisMonth: number;
  outboundThisMonth: number;
  dailyMovementsAvg: number;
  trend?: number[];
  recentMovements: WarehouseMovement[];
  topProducts: WarehouseProduct[];
  // Seguridad
  cameras: number;
  accessControl: AccessControlType;
  hasAlarm: boolean;
  fireSystem: string[];
  lastSecurityAudit: string;
  // Condiciones ambientales
  temperatureRange: string;
  humidityRange: string;
  cooling: CoolingType;
  hasVentilation: boolean;
  // Mantenimiento
  lastMaintenance: string;
  nextMaintenance: string;
  maintenanceNotes: string;
  // Compliance / certificaciones
  sanitaryPermit: string | null;
  sanitaryPermitExpiry: string | null;
  lastInspection: string;
  certifications: string[];
  // Información del sistema
  createdAt: string;
  updatedAt: string | null;
}

export const STATUS_MAP: Record<WarehouseStatus, { label: string; variant: 'success' | 'neutral' | 'warning' | 'danger' }> = {
  active: { label: 'Activo', variant: 'success' },
  full: { label: 'Lleno', variant: 'danger' },
  maintenance: { label: 'Mantenimiento', variant: 'warning' },
  inactive: { label: 'Inactivo', variant: 'neutral' },
};

export const TYPE_LABEL: Record<WarehouseType, string> = {
  general: 'Almacén general',
  cold_storage: 'Almacén refrigerado',
  hazmat: 'Materiales peligrosos',
  transit: 'Tránsito / cross-dock',
  bonded: 'Almacén aduanal',
  automated: 'Almacén automatizado',
};

export const WAREHOUSES: Warehouse[] = [
  {
    id: 'wh-01', code: 'ALM-SAL-01', name: 'Almacén Central A',
    type: 'general', status: 'active', location: 'Bodega A, Planta Baja',
    branchId: 'br-001', branchName: 'Matriz Central',
    branchAddress: 'Calle El Progreso #12, Col. Escalón',
    area: 850, height: 6, length: 42, width: 20,
    shelvesTotal: 240, shelvesOccupied: 198,
    capacity: 5000, used: 4200, products: 1284,
    manager: 'Roberto Méndez', managerInitials: 'RM',
    operators: 8, shifts: ['mañana', 'tarde'],
    totalSKUs: 1284, topCategories: ['Electrónica', 'Hogar', 'Oficina'],
    lowStockItems: 23, expiringItems: 4,
    inventoryValue: 1850000, inventoryTurnover: 12.4,
    lastMovement: 'hace 12 min',
    inboundThisMonth: 1248, outboundThisMonth: 1186, dailyMovementsAvg: 84,
    trend: [52, 58, 61, 70, 66, 78, 84],
    recentMovements: [
      { id: 'mv-001', date: '15 Ene 14:32', type: 'inbound', productSku: 'SKU-A1200', productName: 'Laptop Pro 15"', quantity: 24, operator: 'Roberto Méndez', reference: 'PO-2025-0184' },
      { id: 'mv-002', date: '15 Ene 13:18', type: 'outbound', productSku: 'SKU-B0450', productName: 'Mouse Inalámbrico', quantity: 120, operator: 'Ana Gutiérrez', reference: 'SO-2025-3812' },
      { id: 'mv-003', date: '15 Ene 11:45', type: 'transfer', productSku: 'SKU-C0890', productName: 'Teclado Mecánico', quantity: 40, operator: 'Luis Torres', reference: 'TR-2025-0092' },
      { id: 'mv-004', date: '15 Ene 10:12', type: 'outbound', productSku: 'SKU-A1200', productName: 'Laptop Pro 15"', quantity: 18, operator: 'Roberto Méndez', reference: 'SO-2025-3805' },
      { id: 'mv-005', date: '15 Ene 09:30', type: 'inbound', productSku: 'SKU-D2100', productName: 'Monitor 27" 4K', quantity: 36, operator: 'Ana Gutiérrez', reference: 'PO-2025-0181' },
    ],
    topProducts: [
      { sku: 'SKU-A1200', name: 'Laptop Pro 15"', category: 'Electrónica', quantity: 184, unit: 'und', minStock: 50, maxStock: 250, expiryDate: null },
      { sku: 'SKU-B0450', name: 'Mouse Inalámbrico', category: 'Electrónica', quantity: 412, unit: 'und', minStock: 100, maxStock: 600, expiryDate: null },
      { sku: 'SKU-D2100', name: 'Monitor 27" 4K', category: 'Electrónica', quantity: 96, unit: 'und', minStock: 30, maxStock: 200, expiryDate: null },
      { sku: 'SKU-C0890', name: 'Teclado Mecánico', category: 'Electrónica', quantity: 248, unit: 'und', minStock: 80, maxStock: 400, expiryDate: null },
      { sku: 'SKU-F0330', name: 'Auriculares Bluetooth', category: 'Electrónica', quantity: 320, unit: 'und', minStock: 100, maxStock: 500, expiryDate: null },
    ],
    cameras: 12, accessControl: 'biometrico',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Rociadores', 'Extintores ABC', 'Alarma central'],
    lastSecurityAudit: '12 Dic, 2024',
    temperatureRange: '18-24°C', humidityRange: '40-60%',
    cooling: 'industrial_ac', hasVentilation: true,
    lastMaintenance: '08 Ene, 2025', nextMaintenance: '08 Abr, 2025',
    maintenanceNotes: 'Mantenimiento preventivo trimestral. Revisión de montacargas y sistema de climatización.',
    sanitaryPermit: 'SP-DGS-2024-1845', sanitaryPermitExpiry: '31 Dic, 2025',
    lastInspection: '15 Nov, 2024',
    certifications: ['ISO 9001:2015', 'BPM Almacenamiento', 'OHSAS 18001'],
    createdAt: '04 Ene, 2018', updatedAt: '15 Ene, 2025',
  },
  {
    id: 'wh-02', code: 'ALM-SAL-02', name: 'Almacén Central B',
    type: 'general', status: 'full', location: 'Bodega B, Nivel 1',
    branchId: 'br-001', branchName: 'Matriz Central',
    branchAddress: 'Calle El Progreso #12, Col. Escalón',
    area: 620, height: 5, length: 32, width: 19,
    shelvesTotal: 180, shelvesOccupied: 180,
    capacity: 3000, used: 2950, products: 842,
    manager: 'Roberto Méndez', managerInitials: 'RM',
    operators: 6, shifts: ['mañana', 'tarde'],
    totalSKUs: 842, topCategories: ['Ropa', 'Calzado', 'Accesorios'],
    lowStockItems: 8, expiringItems: 2,
    inventoryValue: 980000, inventoryTurnover: 9.8,
    lastMovement: 'hace 5 min',
    inboundThisMonth: 412, outboundThisMonth: 588, dailyMovementsAvg: 42,
    trend: [70, 74, 80, 85, 90, 95, 98],
    recentMovements: [
      { id: 'mv-101', date: '15 Ene 14:48', type: 'outbound', productSku: 'SKU-R0140', productName: 'Camisa Talla M', quantity: 80, operator: 'Roberto Méndez', reference: 'SO-2025-3815' },
      { id: 'mv-102', date: '15 Ene 13:22', type: 'outbound', productSku: 'SKU-R0150', productName: 'Camisa Talla L', quantity: 64, operator: 'Ana Gutiérrez', reference: 'SO-2025-3814' },
      { id: 'mv-103', date: '15 Ene 11:30', type: 'transfer', productSku: 'SKU-S0020', productName: 'Zapatillas Deportivas', quantity: 30, operator: 'Luis Torres', reference: 'TR-2025-0091' },
      { id: 'mv-104', date: '15 Ene 09:15', type: 'outbound', productSku: 'SKU-R0230', productName: 'Pantalón Casual', quantity: 48, operator: 'Roberto Méndez', reference: 'SO-2025-3810' },
    ],
    topProducts: [
      { sku: 'SKU-R0140', name: 'Camisa Talla M', category: 'Ropa', quantity: 240, unit: 'und', minStock: 80, maxStock: 400, expiryDate: null },
      { sku: 'SKU-R0150', name: 'Camisa Talla L', category: 'Ropa', quantity: 180, unit: 'und', minStock: 60, maxStock: 350, expiryDate: null },
      { sku: 'SKU-S0020', name: 'Zapatillas Deportivas', category: 'Calzado', quantity: 145, unit: 'und', minStock: 50, maxStock: 300, expiryDate: null },
      { sku: 'SKU-R0230', name: 'Pantalón Casual', category: 'Ropa', quantity: 168, unit: 'und', minStock: 50, maxStock: 280, expiryDate: null },
    ],
    cameras: 8, accessControl: 'biometrico',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Rociadores', 'Extintores ABC'],
    lastSecurityAudit: '12 Dic, 2024',
    temperatureRange: '18-24°C', humidityRange: '40-60%',
    cooling: 'industrial_ac', hasVentilation: true,
    lastMaintenance: '08 Ene, 2025', nextMaintenance: '08 Abr, 2025',
    maintenanceNotes: 'Capacidad al 98%. Requiere redistribución o ampliación.',
    sanitaryPermit: 'SP-DGS-2024-1846', sanitaryPermitExpiry: '31 Dic, 2025',
    lastInspection: '15 Nov, 2024',
    certifications: ['ISO 9001:2015', 'BPM Almacenamiento'],
    createdAt: '04 Ene, 2018', updatedAt: '15 Ene, 2025',
  },
  {
    id: 'wh-03', code: 'ALM-SAL-03', name: 'Almacén Tránsito',
    type: 'transit', status: 'active', location: 'Andén de carga',
    branchId: 'br-001', branchName: 'Matriz Central',
    branchAddress: 'Calle El Progreso #12, Col. Escalón',
    area: 180, height: 7, length: 25, width: 7,
    shelvesTotal: 30, shelvesOccupied: 12,
    capacity: 800, used: 320, products: 156,
    manager: 'Roberto Méndez', managerInitials: 'RM',
    operators: 4, shifts: ['mañana', 'tarde', 'noche'],
    totalSKUs: 156, topCategories: ['Cross-dock', 'Distribuidor'],
    lowStockItems: 0, expiringItems: 0,
    inventoryValue: 240000, inventoryTurnover: 28.6,
    lastMovement: 'hace 1 h',
    inboundThisMonth: 1840, outboundThisMonth: 1820, dailyMovementsAvg: 124,
    trend: [60, 50, 45, 38, 42, 35, 40],
    recentMovements: [
      { id: 'mv-201', date: '15 Ene 13:42', type: 'transfer', productSku: 'SKU-X0120', productName: 'Mercadería Cross-Dock', quantity: 80, operator: 'Luis Torres', reference: 'TR-2025-0095' },
      { id: 'mv-202', date: '15 Ene 12:55', type: 'outbound', productSku: 'SKU-X0120', productName: 'Mercadería Cross-Dock', quantity: 96, operator: 'Luis Torres', reference: 'TR-2025-0094' },
      { id: 'mv-203', date: '15 Ene 10:18', type: 'inbound', productSku: 'SKU-X0120', productName: 'Mercadería Cross-Dock', quantity: 120, operator: 'Luis Torres', reference: 'TR-2025-0093' },
    ],
    topProducts: [
      { sku: 'SKU-X0120', name: 'Mercadería Cross-Dock', category: 'Cross-dock', quantity: 156, unit: 'pallet', minStock: 0, maxStock: 400, expiryDate: null },
      { sku: 'SKU-X0140', name: 'Mercadería Cross-Dock B', category: 'Cross-dock', quantity: 84, unit: 'pallet', minStock: 0, maxStock: 400, expiryDate: null },
    ],
    cameras: 6, accessControl: 'tarjetas',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Extintores ABC'],
    lastSecurityAudit: '12 Dic, 2024',
    temperatureRange: '15-30°C', humidityRange: '30-70%',
    cooling: 'ventilacion_natural', hasVentilation: true,
    lastMaintenance: '02 Ene, 2025', nextMaintenance: '02 Abr, 2025',
    maintenanceNotes: 'Alta rotación de inventario. Verificar muelles de carga diariamente.',
    sanitaryPermit: null, sanitaryPermitExpiry: null,
    lastInspection: '15 Nov, 2024',
    certifications: ['ISO 9001:2015'],
    createdAt: '04 Ene, 2018', updatedAt: '15 Ene, 2025',
  },
  {
    id: 'wh-04', code: 'ALM-SON-01', name: 'Almacén Sonsonate',
    type: 'general', status: 'active', location: 'Bodega principal',
    branchId: 'br-002', branchName: 'Sucursal Sonsonate',
    branchAddress: 'Av. Independencia #45, Barrio Centro',
    area: 420, height: 5, length: 28, width: 15,
    shelvesTotal: 120, shelvesOccupied: 86,
    capacity: 2500, used: 1800, products: 620,
    manager: 'Carlos López', managerInitials: 'CL',
    operators: 4, shifts: ['mañana', 'tarde'],
    totalSKUs: 620, topCategories: ['Hogar', 'Cocina', 'Limpieza'],
    lowStockItems: 12, expiringItems: 3,
    inventoryValue: 480000, inventoryTurnover: 8.2,
    lastMovement: 'hace 2 h',
    inboundThisMonth: 380, outboundThisMonth: 342, dailyMovementsAvg: 28,
    trend: [55, 60, 63, 68, 70, 71, 72],
    recentMovements: [
      { id: 'mv-301', date: '15 Ene 12:18', type: 'outbound', productSku: 'SKU-H1100', productName: 'Set de Ollas Acero', quantity: 24, operator: 'Carlos López', reference: 'SO-2025-1208' },
      { id: 'mv-302', date: '15 Ene 10:45', type: 'inbound', productSku: 'SKU-H1100', productName: 'Set de Ollas Acero', quantity: 48, operator: 'Carlos López', reference: 'PO-2025-0089' },
    ],
    topProducts: [
      { sku: 'SKU-H1100', name: 'Set de Ollas Acero', category: 'Cocina', quantity: 96, unit: 'und', minStock: 30, maxStock: 200, expiryDate: null },
      { sku: 'SKU-H1200', name: 'Juego de Vajilla', category: 'Cocina', quantity: 48, unit: 'und', minStock: 20, maxStock: 120, expiryDate: null },
      { sku: 'SKU-L0100', name: 'Set de Toallas', category: 'Hogar', quantity: 124, unit: 'und', minStock: 40, maxStock: 250, expiryDate: null },
    ],
    cameras: 6, accessControl: 'tarjetas',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Extintores ABC'],
    lastSecurityAudit: '03 Mar, 2025',
    temperatureRange: '18-26°C', humidityRange: '40-65%',
    cooling: 'industrial_ac', hasVentilation: true,
    lastMaintenance: '15 Dic, 2024', nextMaintenance: '15 Mar, 2025',
    maintenanceNotes: 'Operación estable. Sin novedades.',
    sanitaryPermit: 'SP-DGS-2024-0924', sanitaryPermitExpiry: '15 Jun, 2026',
    lastInspection: '03 Mar, 2025',
    certifications: ['ISO 9001:2015', 'BPM Almacenamiento'],
    createdAt: '15 Ago, 2019', updatedAt: '15 Ene, 2025',
  },
  {
    id: 'wh-05', code: 'ALM-SON-02', name: 'Almacén Sonsonate B',
    type: 'general', status: 'maintenance', location: 'Bodega secundaria',
    branchId: 'br-002', branchName: 'Sucursal Sonsonate',
    branchAddress: 'Av. Independencia #45, Barrio Centro',
    area: 240, height: 5, length: 20, width: 12,
    shelvesTotal: 80, shelvesOccupied: 0,
    capacity: 1200, used: 0, products: 0,
    manager: 'Carlos López', managerInitials: 'CL',
    operators: 0, shifts: [],
    totalSKUs: 0, topCategories: [],
    lowStockItems: 0, expiringItems: 0,
    inventoryValue: 0, inventoryTurnover: 0,
    lastMovement: 'hace 3 días',
    inboundThisMonth: 0, outboundThisMonth: 0, dailyMovementsAvg: 0,
    trend: [30, 20, 10, 0, 0, 0, 0],
    recentMovements: [
      { id: 'mv-401', date: '12 Ene 09:00', type: 'adjustment', productSku: '—', productName: 'Inventario reubicado a ALM-SON-01', quantity: 0, operator: 'Carlos López', reference: 'AJ-2025-002' },
    ],
    topProducts: [],
    cameras: 4, accessControl: 'doble_llave',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Extintores ABC'],
    lastSecurityAudit: '03 Mar, 2025',
    temperatureRange: '18-26°C', humidityRange: '40-65%',
    cooling: 'industrial_ac', hasVentilation: true,
    lastMaintenance: '12 Ene, 2025', nextMaintenance: '12 Feb, 2025',
    maintenanceNotes: 'En mantenimiento. Reparación del sistema de climatización y pintura general.',
    sanitaryPermit: 'SP-DGS-2024-0925', sanitaryPermitExpiry: '15 Jun, 2026',
    lastInspection: '03 Mar, 2025',
    certifications: ['ISO 9001:2015'],
    createdAt: '15 Ago, 2019', updatedAt: '12 Ene, 2025',
  },
  {
    id: 'wh-06', code: 'ALM-SAM-01', name: 'Almacén San Miguel',
    type: 'cold_storage', status: 'active', location: 'Bodega principal',
    branchId: 'br-003', branchName: 'Sucursal San Miguel',
    branchAddress: 'Barra Av. Roosevelt #78',
    area: 320, height: 5, length: 22, width: 14,
    shelvesTotal: 96, shelvesOccupied: 71,
    capacity: 2000, used: 1450, products: 430,
    manager: 'María Fernández', managerInitials: 'MF',
    operators: 5, shifts: ['mañana', 'tarde'],
    totalSKUs: 430, topCategories: ['Alimentos refrigerados', 'Bebidas', 'Lácteos'],
    lowStockItems: 14, expiringItems: 28,
    inventoryValue: 320000, inventoryTurnover: 18.6,
    lastMovement: 'hace 45 min',
    inboundThisMonth: 286, outboundThisMonth: 248, dailyMovementsAvg: 32,
    trend: [65, 68, 70, 72, 71, 73, 73],
    recentMovements: [
      { id: 'mv-501', date: '15 Ene 14:00', type: 'outbound', productSku: 'SKU-AL0100', productName: 'Leche Entera 1L', quantity: 60, operator: 'María Fernández', reference: 'SO-2025-0512' },
      { id: 'mv-502', date: '15 Ene 11:20', type: 'inbound', productSku: 'SKU-AL0100', productName: 'Leche Entera 1L', quantity: 120, operator: 'María Fernández', reference: 'PO-2025-0088' },
    ],
    topProducts: [
      { sku: 'SKU-AL0100', name: 'Leche Entera 1L', category: 'Lácteos', quantity: 240, unit: 'und', minStock: 60, maxStock: 400, expiryDate: '20 Feb, 2025' },
      { sku: 'SKU-AL0200', name: 'Yogurt Natural 1kg', category: 'Lácteos', quantity: 180, unit: 'und', minStock: 50, maxStock: 350, expiryDate: '18 Feb, 2025' },
      { sku: 'SKU-BE0100', name: 'Bebida Energética 500ml', category: 'Bebidas', quantity: 320, unit: 'und', minStock: 100, maxStock: 600, expiryDate: '15 Jul, 2025' },
    ],
    cameras: 8, accessControl: 'biometrico',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Sistema FM-200', 'Extintores ABC'],
    lastSecurityAudit: '21 Ene, 2025',
    temperatureRange: '2-8°C', humidityRange: '60-75%',
    cooling: 'refrigeracion', hasVentilation: true,
    lastMaintenance: '10 Ene, 2025', nextMaintenance: '10 Abr, 2025',
    maintenanceNotes: 'Cadena de frío crítica. Monitoreo de temperatura cada 15 min.',
    sanitaryPermit: 'SP-DGS-2024-1302', sanitaryPermitExpiry: '22 Nov, 2026',
    lastInspection: '21 Ene, 2025',
    certifications: ['ISO 9001:2015', 'BPM Almacenamiento', 'HACCP'],
    createdAt: '22 Nov, 2021', updatedAt: '15 Ene, 2025',
  },
  {
    id: 'wh-07', code: 'ALM-STA-01', name: 'Almacén Santa Ana',
    type: 'general', status: 'active', location: 'Bodega principal',
    branchId: 'br-004', branchName: 'Sucursal Santa Ana',
    branchAddress: '5ta Calle Poniente #22',
    area: 280, height: 5, length: 20, width: 14,
    shelvesTotal: 80, shelvesOccupied: 47,
    capacity: 1500, used: 890, products: 312,
    manager: 'Juan Pérez', managerInitials: 'JP',
    operators: 3, shifts: ['mañana', 'tarde'],
    totalSKUs: 312, topCategories: ['Ferretería', 'Construcción', 'Jardín'],
    lowStockItems: 8, expiringItems: 0,
    inventoryValue: 420000, inventoryTurnover: 7.4,
    lastMovement: 'hace 3 h',
    inboundThisMonth: 142, outboundThisMonth: 128, dailyMovementsAvg: 14,
    trend: [48, 50, 53, 55, 57, 58, 59],
    recentMovements: [
      { id: 'mv-601', date: '15 Ene 11:30', type: 'outbound', productSku: 'SKU-FT0100', productName: 'Martillo Profesional', quantity: 24, operator: 'Juan Pérez', reference: 'SO-2025-0789' },
    ],
    topProducts: [
      { sku: 'SKU-FT0100', name: 'Martillo Profesional', category: 'Ferretería', quantity: 96, unit: 'und', minStock: 30, maxStock: 200, expiryDate: null },
      { sku: 'SKU-FT0200', name: 'Taladro Inalámbrico', category: 'Ferretería', quantity: 42, unit: 'und', minStock: 15, maxStock: 100, expiryDate: null },
    ],
    cameras: 4, accessControl: 'tarjetas',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Extintores ABC'],
    lastSecurityAudit: '09 Mar, 2025',
    temperatureRange: '18-28°C', humidityRange: '40-60%',
    cooling: 'industrial_ac', hasVentilation: true,
    lastMaintenance: '08 Dic, 2024', nextMaintenance: '08 Mar, 2025',
    maintenanceNotes: 'Operación normal. Programar fumigación preventiva.',
    sanitaryPermit: 'SP-DGS-2024-0451', sanitaryPermitExpiry: '09 Mar, 2026',
    lastInspection: '08 Dic, 2024',
    certifications: ['ISO 9001:2015'],
    createdAt: '09 Mar, 2020', updatedAt: '15 Ene, 2025',
  },
  {
    id: 'wh-08', code: 'ALM-USU-01', name: 'Almacén Usulután',
    type: 'automated', status: 'full', location: 'Zona Franca, Nave 2',
    branchId: 'br-005', branchName: 'Sucursal Usulután',
    branchAddress: 'Zona Franca, Nave 4',
    area: 480, height: 9, length: 30, width: 16,
    shelvesTotal: 160, shelvesOccupied: 160,
    capacity: 2200, used: 2156, products: 512,
    manager: 'Roberto Rivas', managerInitials: 'RR',
    operators: 6, shifts: ['mañana', 'tarde', 'noche'],
    totalSKUs: 512, topCategories: ['Distribución', 'Cross-dock', 'Logística inversa'],
    lowStockItems: 0, expiringItems: 1,
    inventoryValue: 680000, inventoryTurnover: 24.8,
    lastMovement: 'hace 18 min',
    inboundThisMonth: 1240, outboundThisMonth: 1180, dailyMovementsAvg: 92,
    trend: [80, 85, 88, 92, 95, 97, 98],
    recentMovements: [
      { id: 'mv-701', date: '15 Ene 14:25', type: 'outbound', productSku: 'SKU-D0100', productName: 'Pallet Mixto Distribuidor', quantity: 24, operator: 'Roberto Rivas', reference: 'SO-2025-0980' },
      { id: 'mv-702', date: '15 Ene 13:00', type: 'outbound', productSku: 'SKU-D0100', productName: 'Pallet Mixto Distribuidor', quantity: 32, operator: 'Roberto Rivas', reference: 'SO-2025-0979' },
      { id: 'mv-703', date: '15 Ene 10:30', type: 'inbound', productSku: 'SKU-D0200', productName: 'Pallet Refacciones', quantity: 48, operator: 'Roberto Rivas', reference: 'PO-2025-0284' },
    ],
    topProducts: [
      { sku: 'SKU-D0100', name: 'Pallet Mixto Distribuidor', category: 'Distribución', quantity: 384, unit: 'pallet', minStock: 100, maxStock: 500, expiryDate: null },
      { sku: 'SKU-D0200', name: 'Pallet Refacciones', category: 'Distribución', quantity: 128, unit: 'pallet', minStock: 50, maxStock: 250, expiryDate: null },
    ],
    cameras: 16, accessControl: 'biometrico',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Rociadores ESFR', 'Extintores ABC', 'Sistema de espuma'],
    lastSecurityAudit: '18 Feb, 2025',
    temperatureRange: '16-22°C', humidityRange: '40-55%',
    cooling: 'mixto', hasVentilation: true,
    lastMaintenance: '01 Ene, 2025', nextMaintenance: '01 Abr, 2025',
    maintenanceNotes: 'Almacén automatizado. Sistema WMS conectado. Capacidad al 98%.',
    sanitaryPermit: 'SP-DGS-2024-1762', sanitaryPermitExpiry: '12 Feb, 2027',
    lastInspection: '18 Feb, 2025',
    certifications: ['ISO 9001:2015', 'BPM Almacenamiento', 'WMS Nivel 3'],
    createdAt: '12 Feb, 2020', updatedAt: '15 Ene, 2025',
  },
  {
    id: 'wh-09', code: 'ALM-COJ-01', name: 'Almacén Cojutepeque',
    type: 'general', status: 'active', location: 'Bodega Central',
    branchId: 'br-006', branchName: 'Sucursal Cojutepeque',
    branchAddress: 'Av. Raúl Contreras #10',
    area: 260, height: 5, length: 20, width: 13,
    shelvesTotal: 72, shelvesOccupied: 51,
    capacity: 1600, used: 1120, products: 290,
    manager: 'Gabriel Aguilar', managerInitials: 'GA',
    operators: 3, shifts: ['mañana', 'tarde'],
    totalSKUs: 290, topCategories: ['Abarrotes', 'Bebidas', 'Limpieza'],
    lowStockItems: 6, expiringItems: 5,
    inventoryValue: 285000, inventoryTurnover: 9.2,
    lastMovement: 'hace 4 h',
    inboundThisMonth: 168, outboundThisMonth: 154, dailyMovementsAvg: 18,
    trend: [50, 55, 60, 64, 68, 70, 70],
    recentMovements: [
      { id: 'mv-801', date: '15 Ene 10:12', type: 'outbound', productSku: 'SKU-AB0100', productName: 'Arroz 1kg', quantity: 48, operator: 'Gabriel Aguilar', reference: 'SO-2025-0456' },
    ],
    topProducts: [
      { sku: 'SKU-AB0100', name: 'Arroz 1kg', category: 'Abarrotes', quantity: 180, unit: 'und', minStock: 60, maxStock: 350, expiryDate: null },
      { sku: 'SKU-BE0200', name: 'Refresco Cola 2L', category: 'Bebidas', quantity: 144, unit: 'und', minStock: 40, maxStock: 300, expiryDate: '15 May, 2025' },
    ],
    cameras: 4, accessControl: 'tarjetas',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Extintores ABC'],
    lastSecurityAudit: '19 Oct, 2024',
    temperatureRange: '18-26°C', humidityRange: '40-65%',
    cooling: 'industrial_ac', hasVentilation: true,
    lastMaintenance: '22 Nov, 2024', nextMaintenance: '22 Feb, 2025',
    maintenanceNotes: 'Operación estable.',
    sanitaryPermit: 'SP-DGS-2024-0582', sanitaryPermitExpiry: '19 Oct, 2027',
    lastInspection: '19 Oct, 2024',
    certifications: ['ISO 9001:2015'],
    createdAt: '19 Oct, 2021', updatedAt: '15 Ene, 2025',
  },
  {
    id: 'wh-10', code: 'ALM-AHU-01', name: 'Almacén Ahuachapán',
    type: 'general', status: 'active', location: 'Bodega Norte',
    branchId: 'br-007', branchName: 'Sucursal Ahuachapán',
    branchAddress: 'Calle 2ª Poniente #18',
    area: 300, height: 5, length: 20, width: 15,
    shelvesTotal: 80, shelvesOccupied: 51,
    capacity: 1800, used: 1152, products: 340,
    manager: 'Elena Martínez', managerInitials: 'EM',
    operators: 3, shifts: ['mañana', 'tarde'],
    totalSKUs: 340, topCategories: ['Abarrotes', 'Hogar', 'Cuidado personal'],
    lowStockItems: 9, expiringItems: 2,
    inventoryValue: 320000, inventoryTurnover: 8.4,
    lastMovement: 'hace 1 h',
    inboundThisMonth: 188, outboundThisMonth: 172, dailyMovementsAvg: 20,
    trend: [40, 48, 52, 58, 60, 62, 64],
    recentMovements: [
      { id: 'mv-901', date: '15 Ene 13:20', type: 'outbound', productSku: 'SKU-AB0200', productName: 'Frijol 1kg', quantity: 36, operator: 'Elena Martínez', reference: 'SO-2025-0321' },
    ],
    topProducts: [
      { sku: 'SKU-AB0200', name: 'Frijol 1kg', category: 'Abarrotes', quantity: 124, unit: 'und', minStock: 50, maxStock: 280, expiryDate: null },
      { sku: 'SKU-CP0100', name: 'Shampoo 400ml', category: 'Cuidado personal', quantity: 96, unit: 'und', minStock: 30, maxStock: 200, expiryDate: '20 Dic, 2025' },
    ],
    cameras: 4, accessControl: 'tarjetas',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Extintores ABC'],
    lastSecurityAudit: '05 Jun, 2025',
    temperatureRange: '18-26°C', humidityRange: '40-60%',
    cooling: 'industrial_ac', hasVentilation: true,
    lastMaintenance: '12 Dic, 2024', nextMaintenance: '12 Mar, 2025',
    maintenanceNotes: 'Operación normal.',
    sanitaryPermit: 'SP-DGS-2024-0614', sanitaryPermitExpiry: '05 Jun, 2027',
    lastInspection: '05 Jun, 2025',
    certifications: ['ISO 9001:2015'],
    createdAt: '05 Jun, 2021', updatedAt: '15 Ene, 2025',
  },
  {
    id: 'wh-11', code: 'ALM-CHA-01', name: 'Almacén Chalatenango',
    type: 'general', status: 'maintenance', location: 'Bodega Sur',
    branchId: 'br-008', branchName: 'Sucursal Chalatenango',
    branchAddress: 'Barrio El Calvario',
    area: 200, height: 4, length: 16, width: 12,
    shelvesTotal: 60, shelvesOccupied: 0,
    capacity: 1000, used: 0, products: 0,
    manager: 'Laura Torres', managerInitials: 'LT',
    operators: 0, shifts: [],
    totalSKUs: 0, topCategories: [],
    lowStockItems: 0, expiringItems: 0,
    inventoryValue: 0, inventoryTurnover: 0,
    lastMovement: 'hace 5 días',
    inboundThisMonth: 0, outboundThisMonth: 0, dailyMovementsAvg: 0,
    trend: [20, 10, 0, 0, 0, 0, 0],
    recentMovements: [
      { id: 'mv-1001', date: '10 Ene 11:00', type: 'adjustment', productSku: '—', productName: 'Cierre temporal por evaluación', quantity: 0, operator: 'Laura Torres', reference: 'AJ-2025-001' },
    ],
    topProducts: [],
    cameras: 2, accessControl: 'doble_llave',
    hasAlarm: false, fireSystem: ['Extintores ABC'],
    lastSecurityAudit: '15 Oct, 2023',
    temperatureRange: '18-30°C', humidityRange: '40-70%',
    cooling: 'ventilacion_natural', hasVentilation: true,
    lastMaintenance: '08 Ene, 2025', nextMaintenance: '08 Feb, 2025',
    maintenanceNotes: 'Almacén cerrado temporalmente. Evaluación de reactivación.',
    sanitaryPermit: 'SP-DGS-2023-0092', sanitaryPermitExpiry: '15 Jun, 2025',
    lastInspection: '15 Oct, 2023',
    certifications: [],
    createdAt: '—', updatedAt: '10 Ene, 2025',
  },
  {
    id: 'wh-12', code: 'ALM-ZAC-01', name: 'Almacén Zacatecoluca',
    type: 'general', status: 'active', location: 'Bodega A',
    branchId: 'br-009', branchName: 'Sucursal Zacatecoluca',
    branchAddress: 'Km 56 Carretera a San Salvador',
    area: 250, height: 5, length: 20, width: 12,
    shelvesTotal: 72, shelvesOccupied: 42,
    capacity: 1400, used: 812, products: 210,
    manager: 'Sofía Benítez', managerInitials: 'SB',
    operators: 3, shifts: ['mañana', 'tarde'],
    totalSKUs: 210, topCategories: ['Abarrotes', 'Bebidas'],
    lowStockItems: 5, expiringItems: 1,
    inventoryValue: 240000, inventoryTurnover: 8.6,
    lastMovement: 'hace 6 h',
    inboundThisMonth: 124, outboundThisMonth: 118, dailyMovementsAvg: 12,
    trend: [45, 49, 52, 55, 56, 57, 58],
    recentMovements: [
      { id: 'mv-1101', date: '15 Ene 08:42', type: 'outbound', productSku: 'SKU-AB0300', productName: 'Azúcar 1kg', quantity: 30, operator: 'Sofía Benítez', reference: 'SO-2025-0214' },
    ],
    topProducts: [
      { sku: 'SKU-AB0300', name: 'Azúcar 1kg', category: 'Abarrotes', quantity: 102, unit: 'und', minStock: 40, maxStock: 220, expiryDate: null },
      { sku: 'SKU-BE0300', name: 'Agua Embotellada 1L', category: 'Bebidas', quantity: 180, unit: 'und', minStock: 60, maxStock: 360, expiryDate: null },
    ],
    cameras: 4, accessControl: 'tarjetas',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Extintores ABC'],
    lastSecurityAudit: '14 Jun, 2025',
    temperatureRange: '18-28°C', humidityRange: '40-65%',
    cooling: 'industrial_ac', hasVentilation: true,
    lastMaintenance: '12 Dic, 2024', nextMaintenance: '12 Mar, 2025',
    maintenanceNotes: 'Operación estable.',
    sanitaryPermit: 'SP-DGS-2024-0689', sanitaryPermitExpiry: '03 Ene, 2028',
    lastInspection: '14 Jun, 2025',
    certifications: ['ISO 9001:2015'],
    createdAt: '03 Ene, 2022', updatedAt: '15 Ene, 2025',
  },
  {
    id: 'wh-13', code: 'ALM-SVT-01', name: 'Almacén San Vicente',
    type: 'general', status: 'active', location: 'Bodega B',
    branchId: 'br-010', branchName: 'Sucursal San Vicente',
    branchAddress: 'Barrio El Santuario #3',
    area: 240, height: 5, length: 20, width: 12,
    shelvesTotal: 64, shelvesOccupied: 37,
    capacity: 1300, used: 741, products: 195,
    manager: 'Claudia Mendoza', managerInitials: 'CM',
    operators: 2, shifts: ['mañana'],
    totalSKUs: 195, topCategories: ['Abarrotes', 'Limpieza'],
    lowStockItems: 4, expiringItems: 2,
    inventoryValue: 195000, inventoryTurnover: 7.6,
    lastMovement: 'hace 2 días',
    inboundThisMonth: 96, outboundThisMonth: 84, dailyMovementsAvg: 8,
    trend: [40, 44, 48, 52, 55, 56, 57],
    recentMovements: [
      { id: 'mv-1201', date: '13 Ene 14:22', type: 'inbound', productSku: 'SKU-AB0400', productName: 'Aceite 1L', quantity: 24, operator: 'Claudia Mendoza', reference: 'PO-2025-0067' },
    ],
    topProducts: [
      { sku: 'SKU-AB0400', name: 'Aceite 1L', category: 'Abarrotes', quantity: 84, unit: 'und', minStock: 30, maxStock: 180, expiryDate: null },
    ],
    cameras: 4, accessControl: 'tarjetas',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Extintores ABC'],
    lastSecurityAudit: '11 Jul, 2025',
    temperatureRange: '18-28°C', humidityRange: '40-65%',
    cooling: 'industrial_ac', hasVentilation: true,
    lastMaintenance: '14 Jun, 2025', nextMaintenance: '14 Sep, 2025',
    maintenanceNotes: 'Operación estable. Solo turno matutino.',
    sanitaryPermit: 'SP-DGS-2024-0722', sanitaryPermitExpiry: '20 Jul, 2027',
    lastInspection: '11 Jul, 2025',
    certifications: ['ISO 9001:2015'],
    createdAt: '20 Jul, 2021', updatedAt: '13 Ene, 2025',
  },
  {
    id: 'wh-14', code: 'ALM-GOT-01', name: 'Almacén Gotera',
    type: 'general', status: 'active', location: 'Bodega Principal',
    branchId: 'br-011', branchName: 'Sucursal San Francisco Gotera',
    branchAddress: 'Plaza Unicentro, Local 14',
    area: 220, height: 5, length: 18, width: 12,
    shelvesTotal: 60, shelvesOccupied: 32,
    capacity: 1100, used: 594, products: 170,
    manager: 'Patricia Orellana', managerInitials: 'PO',
    operators: 2, shifts: ['mañana'],
    totalSKUs: 170, topCategories: ['Abarrotes', 'Bebidas'],
    lowStockItems: 3, expiringItems: 1,
    inventoryValue: 165000, inventoryTurnover: 6.8,
    lastMovement: 'hace 1 día',
    inboundThisMonth: 78, outboundThisMonth: 72, dailyMovementsAvg: 6,
    trend: [35, 40, 45, 48, 50, 52, 54],
    recentMovements: [
      { id: 'mv-1301', date: '14 Ene 10:18', type: 'outbound', productSku: 'SKU-AB0500', productName: 'Pasta 500g', quantity: 36, operator: 'Patricia Orellana', reference: 'SO-2025-0389' },
    ],
    topProducts: [
      { sku: 'SKU-AB0500', name: 'Pasta 500g', category: 'Abarrotes', quantity: 96, unit: 'und', minStock: 40, maxStock: 200, expiryDate: null },
    ],
    cameras: 3, accessControl: 'tarjetas',
    hasAlarm: true, fireSystem: ['Detectores de humo', 'Extintores ABC'],
    lastSecurityAudit: '17 Sep, 2024',
    temperatureRange: '18-28°C', humidityRange: '40-65%',
    cooling: 'industrial_ac', hasVentilation: true,
    lastMaintenance: '20 Sep, 2024', nextMaintenance: '20 Mar, 2025',
    maintenanceNotes: 'Operación estable.',
    sanitaryPermit: 'SP-DGS-2024-0798', sanitaryPermitExpiry: '17 Sep, 2028',
    lastInspection: '17 Sep, 2024',
    certifications: ['ISO 9001:2015'],
    createdAt: '17 Sep, 2018', updatedAt: '14 Ene, 2025',
  },
];

export function utilizationPct(wh: Warehouse): number {
  if (wh.capacity <= 0) return 0;
  return Math.round((wh.used / wh.capacity) * 100);
}

export function utilizationColor(pct: number): string {
  if (pct >= 90) return '239 68 68';
  if (pct >= 70) return '237 151 39';
  return '0 168 107';
}

export function getCapacityVariant(pct: number, status: WarehouseStatus): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'maintenance' || status === 'inactive') return 'neutral';
  if (pct >= 90) return 'danger';
  if (pct >= 70) return 'warning';
  return 'success';
}

export function getShortWarehouseName(fullName: string): string {
  return fullName.replace(/^Almacén\s+/i, '');
}