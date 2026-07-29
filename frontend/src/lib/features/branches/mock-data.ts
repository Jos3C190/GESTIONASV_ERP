// MOCK DATA — Sucursales. Reemplazar por llamadas a la API cuando exista el módulo.

export interface BranchImage {
  url: string;
  caption: string;
}

export interface ScheduleDay {
  day: string;
  open: string | null;
  close: string | null;
}

export interface WarehouseDetail {
  name: string;
  code: string;
  location: string;
  capacity: number;
  used: number;
  status: 'active' | 'full' | 'maintenance';
  products: number;
}

export interface Branch {
  id: string;
  code: string;
  name: string;
  address: string;
  city: string;
  phone: string;
  email: string;
  manager: string;
  managerInitials: string;
  lat: number;
  lng: number;
  status: 'active' | 'inactive' | 'maintenance';
  employees: number;
  warehouses: number;
  salesThisMonth: number;
  salesLastMonth: number;
  salesYTD: number;
  trend: number[];
  openedAt: string;
  // Infraestructura básica
  area: number;
  areaBuilt: number;
  areaUnbuilt: number;
  floors: number;
  parking: number;
  capacity: number;
  // Infraestructura física detallada
  propertyType: 'propio' | 'alquilado' | 'arrendado' | 'cedido';
  areaAvailable: number;
  storageCapacity: number;
  buildingAge: number;
  offices: number;
  meetingRooms: number;
  bathrooms: number;
  accesses: number;
  emergencyExits: number;
  accessibility: string[];
  // Almacenes detallados
  warehousesDetail: WarehouseDetail[];
  // Datos técnicos y administrativos del inmueble
  constructionType: 'concreto' | 'metalico' | 'mixto' | 'prefabricado';
  constructionYear: number;
  condition: 'excelente' | 'bueno' | 'regular' | 'malo';
  appraisedValue: number;
  monthlyMaintenance: number;
  lastRenovation: string;
  // Servicios básicos
  electricalCapacityKVA: number;
  internetProvider: string;
  internetType: 'fibra' | 'adsl' | 'satelital' | '4g';
  waterSource: 'red_publica' | 'pozo' | 'cisterna' | 'mixta';
  acSystem: 'central' | 'individual' | 'mini_split' | 'mixto' | 'sin_ac';
  lighting: 'led' | 'fluorescente' | 'mixta';
  // Seguridad
  cctvCameras: number;
  accessControl: 'biometrico' | 'tarjetas' | 'teclado' | 'sin_control';
  fireSystem: string[];
  hasAlarm: boolean;
  // Características técnicas
  exteriorMaterial: 'cristal' | 'alucobond' | 'concreto' | 'mixta';
  floorMaterial: 'porcelanato' | 'ceramico' | 'epoxico' | 'concreto_pulido' | 'cemento';
  roofCapacityKgM2: number;
  hasBackupGenerator: boolean;
  hasUPS: boolean;
  cleaningProvider: string;
  // Información legal/administrativa
  cadastralCode: string;
  permitExpiry: string;
  leaseExpiry: string | null;
  landlord: string | null;
  // Operativo
  schedule: string;
  scheduleDetail: ScheduleDay[];
  zone: string;
  services: string[];
  facilities: string[];
  // Métricas de rendimiento
  avgTicket: number;
  monthlyVisitors: number;
  customerRating: number;
  inventoryTurnover: number;
  lastInspection: string;
  // Contacto / redes
  website: string;
  // Descripción
  description: string;
  images: BranchImage[];
}

function images(seed: string, captions: string[]): BranchImage[] {
  return captions.map((c, i) => ({
    url: `https://picsum.photos/seed/${seed}-${i + 1}/1200/800`,
    caption: c,
  }));
}

function wh(name: string, code: string, location: string, capacity: number, used: number, status: 'active' | 'full' | 'maintenance', products: number): WarehouseDetail {
  return { name, code, location, capacity, used, status, products };
}

const STD_SCHEDULE: ScheduleDay[] = [
  { day: 'Lunes', open: '08:00', close: '20:00' },
  { day: 'Martes', open: '08:00', close: '20:00' },
  { day: 'Miércoles', open: '08:00', close: '20:00' },
  { day: 'Jueves', open: '08:00', close: '20:00' },
  { day: 'Viernes', open: '08:00', close: '20:00' },
  { day: 'Sábado', open: '08:00', close: '18:00' },
  { day: 'Domingo', open: '09:00', close: '14:00' },
];

const STD_SERVICES = ['Punto de venta', 'Bodega', 'Servicio al cliente', 'Devoluciones'];
const STD_FACILITIES = ['Estacionamiento', 'Aire acondicionado', 'CCTV', 'WiFi clientes'];

export const BRANCHES: Branch[] = [
  {
    id: 'br-001', code: 'SAL-01', name: 'Matriz Central', address: 'Calle El Progreso #12, Col. Escalón',
    city: 'San Salvador', phone: '+503 2222-1000', email: 'matriz@erp-system.dev',
    manager: 'Ana García', managerInitials: 'AG',
    lat: 13.6989, lng: -89.1914, status: 'active', employees: 47, warehouses: 3,
    salesThisMonth: 48250, salesLastMonth: 44800, salesYTD: 538900,
    trend: [30, 34, 38, 36, 40, 44, 48], openedAt: '04 Ene, 2018',
    area: 1200, areaBuilt: 850, areaUnbuilt: 350, floors: 3, parking: 40, capacity: 180,
    propertyType: 'propio', areaAvailable: 120, storageCapacity: 500,
    buildingAge: 8, offices: 12, meetingRooms: 3, bathrooms: 6, accesses: 3, emergencyExits: 4,
    accessibility: ['Rampas', 'Ascensor', 'Baño accesible', 'Estacionamiento preferencial'],
    warehousesDetail: [
      wh('Almacén Central A', 'ALM-SAL-01', 'Bodega A, Planta Baja', 200, 168, 'active', 1284),
      wh('Almacén Central B', 'ALM-SAL-02', 'Bodega B, Nivel 1', 180, 177, 'full', 842),
      wh('Almacén Tránsito', 'ALM-SAL-03', 'Andén de carga', 120, 48, 'active', 156),
    ],
    constructionType: 'concreto', constructionYear: 2017, condition: 'excelente',
    appraisedValue: 1850000, monthlyMaintenance: 3200, lastRenovation: '15 Mar, 2023',
    electricalCapacityKVA: 75, internetProvider: 'Tigo Business', internetType: 'fibra',
    waterSource: 'red_publica', acSystem: 'central', lighting: 'led',
    cctvCameras: 24, accessControl: 'biometrico',
    fireSystem: ['Detectores de humo', 'Rociadores', 'Extintores ABC', 'Alarma central'],
    hasAlarm: true, exteriorMaterial: 'cristal', floorMaterial: 'porcelanato',
    roofCapacityKgM2: 500, hasBackupGenerator: true, hasUPS: true,
    cleaningProvider: 'CleanPro SV',
    cadastralCode: 'CSS-SS-1234-A', permitExpiry: '31 Dic, 2026',
    leaseExpiry: null, landlord: null,
    schedule: 'Lun–Sáb 8:00–20:00, Dom 9:00–14:00',
    scheduleDetail: STD_SCHEDULE,
    zone: 'Metropolitana',
    services: ['Punto de venta', 'Bodega', 'Servicio al cliente', 'Devoluciones', 'Entregas a domicilio', 'Cobros de servicios', 'Atención corporativa B2B'],
    facilities: ['Estacionamiento', 'Aire acondicionado', 'CCTV 24/7', 'WiFi clientes', 'Ascensor', 'Cafetería', 'Sala de reuniones', 'Generador eléctrico'],
    avgTicket: 48.5, monthlyVisitors: 4200, customerRating: 4.8, inventoryTurnover: 12.4,
    lastInspection: '12 May, 2025',
    website: 'https://erp-system.dev/sucursales/matriz',
    description: 'Sede principal y centro de operaciones corporativas. Cuenta con 3 niveles, área de ventas abierta, bodegas internas, oficinas administrativas y sala de capacitación ejecutiva.',
    images: images('br001', ['Fachada principal', 'Área de ventas', 'Bodega interna', 'Oficinas administrativas']),
  },
  {
    id: 'br-002', code: 'SON-01', name: 'Sucursal Sonsonate', address: 'Av. Independencia #45, Barrio Centro',
    city: 'Sonsonate', phone: '+503 2450-3300', email: 'sonsonate@erp-system.dev',
    manager: 'Carlos López', managerInitials: 'CL',
    lat: 13.7189, lng: -89.7286, status: 'active', employees: 22, warehouses: 2,
    salesThisMonth: 28800, salesLastMonth: 27500, salesYTD: 312400,
    trend: [20, 22, 21, 24, 26, 27, 28], openedAt: '15 Ago, 2019',
    area: 580, areaBuilt: 420, areaUnbuilt: 160, floors: 1, parking: 15, capacity: 80,
    propertyType: 'alquilado', areaAvailable: 40, storageCapacity: 180,
    buildingAge: 6, offices: 3, meetingRooms: 1, bathrooms: 2, accesses: 2, emergencyExits: 2,
    accessibility: ['Rampas', 'Estacionamiento preferencial'],
    warehousesDetail: [
      wh('Almacén Sonsonate', 'ALM-SON-01', 'Bodega principal', 120, 86, 'active', 620),
      wh('Almacén Sonsonate B', 'ALM-SON-02', 'Bodega secundaria', 60, 0, 'maintenance', 0),
    ],
    constructionType: 'mixto', constructionYear: 2019, condition: 'bueno',
    appraisedValue: 380000, monthlyMaintenance: 950, lastRenovation: '—',
    electricalCapacityKVA: 25, internetProvider: 'Claro Empresas', internetType: 'fibra',
    waterSource: 'red_publica', acSystem: 'mini_split', lighting: 'led',
    cctvCameras: 8, accessControl: 'tarjetas',
    fireSystem: ['Extintores ABC', 'Detectores de humo'],
    hasAlarm: true, exteriorMaterial: 'alucobond', floorMaterial: 'ceramico',
    roofCapacityKgM2: 300, hasBackupGenerator: false, hasUPS: true,
    cleaningProvider: 'Limpieza Total',
    cadastralCode: 'CSS-SON-0452-B', permitExpiry: '15 Jun, 2026',
    leaseExpiry: '31 Dic, 2027', landlord: 'Inmob. Sonsonate S.A. de C.V.',
    schedule: 'Lun–Sáb 8:00–18:00',
    scheduleDetail: [
      { day: 'Lunes', open: '08:00', close: '18:00' },
      { day: 'Martes', open: '08:00', close: '18:00' },
      { day: 'Miércoles', open: '08:00', close: '18:00' },
      { day: 'Jueves', open: '08:00', close: '18:00' },
      { day: 'Viernes', open: '08:00', close: '18:00' },
      { day: 'Sábado', open: '08:00', close: '18:00' },
      { day: 'Domingo', open: null, close: null },
    ],
    zone: 'Occidental',
    services: STD_SERVICES,
    facilities: ['Estacionamiento', 'Aire acondicionado', 'CCTV', 'WiFi clientes'],
    avgTicket: 36.2, monthlyVisitors: 2100, customerRating: 4.5, inventoryTurnover: 9.8,
    lastInspection: '03 Mar, 2025',
    website: 'https://erp-system.dev/sucursales/sonsonate',
    description: 'Punto de venta estratégico en el occidente del país. Atiende clientes de Sonsonate y municipios cercanos con bodega de media capacidad.',
    images: images('br002', ['Fachada', 'Interior', 'Mostrador de atención', 'Estacionamiento']),
  },
  {
    id: 'br-003', code: 'SAM-01', name: 'Sucursal San Miguel', address: 'Barra Av. Roosevelt #78',
    city: 'San Miguel', phone: '+503 2665-2200', email: 'sanmiguel@erp-system.dev',
    manager: 'María Fernández', managerInitials: 'MF',
    lat: 13.4833, lng: -88.1833, status: 'active', employees: 18, warehouses: 1,
    salesThisMonth: 19500, salesLastMonth: 18400, salesYTD: 208600,
    trend: [10, 12, 13, 15, 16, 18, 19.5], openedAt: '22 Nov, 2021',
    area: 720, areaBuilt: 520, areaUnbuilt: 200, floors: 2, parking: 20, capacity: 120,
    propertyType: 'alquilado', areaAvailable: 60, storageCapacity: 150,
    buildingAge: 4, offices: 5, meetingRooms: 1, bathrooms: 3, accesses: 2, emergencyExits: 3,
    accessibility: ['Rampas', 'Ascensor', 'Baño accesible'],
    warehousesDetail: [
      wh('Almacén San Miguel', 'ALM-SAM-01', 'Bodega principal', 150, 109, 'active', 430),
    ],
    constructionType: 'concreto', constructionYear: 2021, condition: 'excelente',
    appraisedValue: 520000, monthlyMaintenance: 1450, lastRenovation: '—',
    electricalCapacityKVA: 40, internetProvider: 'Tigo Business', internetType: 'fibra',
    waterSource: 'red_publica', acSystem: 'individual', lighting: 'led',
    cctvCameras: 12, accessControl: 'tarjetas',
    fireSystem: ['Detectores de humo', 'Extintores ABC'],
    hasAlarm: true, exteriorMaterial: 'cristal', floorMaterial: 'porcelanato',
    roofCapacityKgM2: 400, hasBackupGenerator: true, hasUPS: true,
    cleaningProvider: 'ServiLimp',
    cadastralCode: 'CSS-SM-0782-A', permitExpiry: '22 Nov, 2027',
    leaseExpiry: '30 Nov, 2026', landlord: 'Corp. Inversiones Oriental',
    schedule: 'Lun–Sáb 8:00–19:00, Dom 9:00–13:00',
    scheduleDetail: [
      { day: 'Lunes', open: '08:00', close: '19:00' },
      { day: 'Martes', open: '08:00', close: '19:00' },
      { day: 'Miércoles', open: '08:00', close: '19:00' },
      { day: 'Jueves', open: '08:00', close: '19:00' },
      { day: 'Viernes', open: '08:00', close: '19:00' },
      { day: 'Sábado', open: '08:00', close: '19:00' },
      { day: 'Domingo', open: '09:00', close: '13:00' },
    ],
    zone: 'Oriental',
    services: STD_SERVICES,
    facilities: ['Estacionamiento', 'Aire acondicionado', 'CCTV', 'WiFi clientes', 'Rampa de acceso'],
    avgTicket: 32.4, monthlyVisitors: 1750, customerRating: 4.3, inventoryTurnover: 8.5,
    lastInspection: '21 Ene, 2025',
    website: 'https://erp-system.dev/sucursales/san-miguel',
    description: 'Sucursal oriental con cobertura sobre la zona paracentral y departamento de San Miguel. Operación de dos niveles con bodega en planta alta.',
    images: images('br003', ['Fachada nocturna', 'Pasillo principal', 'Caja registradora', 'Almacén']),
  },
  {
    id: 'br-004', code: 'STA-01', name: 'Sucursal Santa Ana', address: '5ta Calle Poniente #22',
    city: 'Santa Ana', phone: '+503 2440-1180', email: 'santaana@erp-system.dev',
    manager: 'Juan Pérez', managerInitials: 'JP',
    lat: 13.9942, lng: -89.5583, status: 'maintenance', employees: 12, warehouses: 1,
    salesThisMonth: 0, salesLastMonth: 0, salesYTD: 142800,
    trend: [14, 13, 12, 10, 8, 6, 0], openedAt: '09 Mar, 2020',
    area: 500, areaBuilt: 350, areaUnbuilt: 150, floors: 1, parking: 12, capacity: 70,
    propertyType: 'propio', areaAvailable: 0, storageCapacity: 90,
    buildingAge: 6, offices: 3, meetingRooms: 1, bathrooms: 2, accesses: 1, emergencyExits: 2,
    accessibility: ['Rampas'],
    warehousesDetail: [
      wh('Almacén Santa Ana', 'ALM-STA-01', 'Bodega principal', 90, 53, 'active', 312),
    ],
    constructionType: 'mixto', constructionYear: 2020, condition: 'regular',
    appraisedValue: 420000, monthlyMaintenance: 1850, lastRenovation: '01 Feb, 2025',
    electricalCapacityKVA: 30, internetProvider: 'Claro Empresas', internetType: 'fibra',
    waterSource: 'red_publica', acSystem: 'mini_split', lighting: 'mixta',
    cctvCameras: 8, accessControl: 'teclado',
    fireSystem: ['Extintores ABC'],
    hasAlarm: true, exteriorMaterial: 'alucobond', floorMaterial: 'ceramico',
    roofCapacityKgM2: 350, hasBackupGenerator: false, hasUPS: false,
    cleaningProvider: '—',
    cadastralCode: 'CSS-SA-0341-C', permitExpiry: '09 Mar, 2026',
    leaseExpiry: null, landlord: null,
    schedule: 'Lun–Vie 8:00–17:00',
    scheduleDetail: [
      { day: 'Lunes', open: '08:00', close: '17:00' },
      { day: 'Martes', open: '08:00', close: '17:00' },
      { day: 'Miércoles', open: '08:00', close: '17:00' },
      { day: 'Jueves', open: '08:00', close: '17:00' },
      { day: 'Viernes', open: '08:00', close: '17:00' },
      { day: 'Sábado', open: null, close: null },
      { day: 'Domingo', open: null, close: null },
    ],
    zone: 'Occidental',
    services: ['Punto de venta', 'Bodega'],
    facilities: ['Estacionamiento', 'CCTV'],
    avgTicket: 0, monthlyVisitors: 0, customerRating: 4.1, inventoryTurnover: 0,
    lastInspection: '08 Dic, 2024',
    website: 'https://erp-system.dev/sucursales/santa-ana',
    description: 'Sucursal en proceso de remodelación y ampliación de área de ventas. Reapertura programada para el próximo trimestre con mejoras en infraestructura.',
    images: images('br004', ['Fachada en remodelación', 'Interior en obra', 'Área de bodega', 'Planos del proyecto']),
  },
  {
    id: 'br-005', code: 'CHL-01', name: 'Sucursal Chalatenango', address: 'Barrio El Calvario',
    city: 'Chalatenango', phone: '+503 2301-4400', email: 'chala@erp-system.dev',
    manager: 'Laura Torres', managerInitials: 'LT',
    lat: 14.0333, lng: -88.9333, status: 'inactive', employees: 0, warehouses: 0,
    salesThisMonth: 0, salesLastMonth: 0, salesYTD: 0,
    trend: [0, 0, 0, 0, 0, 0, 0], openedAt: '—',
    area: 450, areaBuilt: 280, areaUnbuilt: 170, floors: 1, parking: 8, capacity: 60,
    propertyType: 'alquilado', areaAvailable: 240, storageCapacity: 60,
    buildingAge: 12, offices: 2, meetingRooms: 0, bathrooms: 2, accesses: 1, emergencyExits: 1,
    accessibility: ['Rampas'],
    warehousesDetail: [],
    constructionType: 'prefabricado', constructionYear: 2013, condition: 'malo',
    appraisedValue: 180000, monthlyMaintenance: 420, lastRenovation: '—',
    electricalCapacityKVA: 15, internetProvider: '—', internetType: '4g',
    waterSource: 'pozo', acSystem: 'sin_ac', lighting: 'fluorescente',
    cctvCameras: 0, accessControl: 'sin_control', fireSystem: ['Extintores ABC'],
    hasAlarm: false, exteriorMaterial: 'concreto', floorMaterial: 'cemento',
    roofCapacityKgM2: 200, hasBackupGenerator: false, hasUPS: false,
    cleaningProvider: '—',
    cadastralCode: 'CSS-CHA-0009-D', permitExpiry: '15 Jun, 2025',
    leaseExpiry: '31 Mar, 2026', landlord: 'Fam. Torres Mendoza',
    schedule: 'Cerrada temporalmente',
    scheduleDetail: STD_SCHEDULE.map((d) => ({ ...d, open: null, close: null })),
    zone: 'Septentrional',
    services: [],
    facilities: ['Estacionamiento'],
    avgTicket: 0, monthlyVisitors: 0, customerRating: 0, inventoryTurnover: 0,
    lastInspection: '15 Oct, 2023',
    website: 'https://erp-system.dev/sucursales/chalatenango',
    description: 'Sucursal inactiva. En evaluación para reactivación según demanda de la zona norte. Inventario trasladado a Matriz Central.',
    images: images('br005', ['Fachada cerrada', 'Interior sin uso', 'Estacionamiento', 'Letrero exterior']),
  },
  {
    id: 'br-006', code: 'USU-01', name: 'Sucursal Usulután', address: 'Zona Franca, Nave 4',
    city: 'Usulután', phone: '+503 2662-0900', email: 'usulutan@erp-system.dev',
    manager: 'Roberto Rivas', managerInitials: 'RR',
    lat: 13.3500, lng: -88.4500, status: 'active', employees: 25, warehouses: 2,
    salesThisMonth: 34100, salesLastMonth: 32800, salesYTD: 378600,
    trend: [18, 20, 25, 27, 30, 32, 34], openedAt: '12 Feb, 2020',
    area: 900, areaBuilt: 600, areaUnbuilt: 300, floors: 1, parking: 25, capacity: 140,
    propertyType: 'arrendado', areaAvailable: 80, storageCapacity: 350,
    buildingAge: 5, offices: 4, meetingRooms: 1, bathrooms: 3, accesses: 3, emergencyExits: 4,
    accessibility: ['Rampas', 'Andén de carga accesible'],
    warehousesDetail: [
      wh('Almacén Usulután A', 'ALM-USU-01', 'Zona Franca, Nave 2', 220, 216, 'full', 512),
      wh('Almacén Usulután B', 'ALM-USU-02', 'Zona Franca, Nave 4', 130, 78, 'active', 280),
    ],
    constructionType: 'metalico', constructionYear: 2020, condition: 'excelente',
    appraisedValue: 620000, monthlyMaintenance: 2100, lastRenovation: '—',
    electricalCapacityKVA: 110, internetProvider: 'Tigo Business', internetType: 'fibra',
    waterSource: 'cisterna', acSystem: 'mixto', lighting: 'led',
    cctvCameras: 16, accessControl: 'biometrico',
    fireSystem: ['Detectores de humo', 'Rociadores', 'Extintores ABC', 'Sistema de espuma'],
    hasAlarm: true, exteriorMaterial: 'alucobond', floorMaterial: 'epoxico',
    roofCapacityKgM2: 800, hasBackupGenerator: true, hasUPS: true,
    cleaningProvider: 'IndustrialClean',
    cadastralCode: 'CSS-USU-0067-B', permitExpiry: '12 Feb, 2027',
    leaseExpiry: '31 Ene, 2030', landlord: 'Zona Franca La Unión S.A.',
    schedule: 'Lun–Sáb 7:30–19:00',
    scheduleDetail: [
      { day: 'Lunes', open: '07:30', close: '19:00' },
      { day: 'Martes', open: '07:30', close: '19:00' },
      { day: 'Miércoles', open: '07:30', close: '19:00' },
      { day: 'Jueves', open: '07:30', close: '19:00' },
      { day: 'Viernes', open: '07:30', close: '19:00' },
      { day: 'Sábado', open: '07:30', close: '19:00' },
      { day: 'Domingo', open: null, close: null },
    ],
    zone: 'Oriental',
    services: ['Punto de venta', 'Bodega', 'Servicio al cliente', 'Devoluciones', 'Logística de distribución'],
    facilities: ['Estacionamiento', 'Aire acondicionado', 'CCTV', 'WiFi clientes', 'Andén de carga', 'Montacargas'],
    avgTicket: 38.7, monthlyVisitors: 2400, customerRating: 4.6, inventoryTurnover: 11.2,
    lastInspection: '18 Feb, 2025',
    website: 'https://erp-system.dev/sucursales/usulutan',
    description: 'Sucursal en zona franca oriental con alto volumen de distribución y bodega de gran capacidad. Andén de carga para flota de distribución.',
    images: images('br006', ['Nave industrial', 'Andén de carga', 'Interior amplio', 'Oficinas']),
  },
  {
    id: 'br-007', code: 'AHU-01', name: 'Sucursal Ahuachapán', address: 'Calle 2ª Poniente #18',
    city: 'Ahuachapán', phone: '+503 2413-8800', email: 'ahuachapan@erp-system.dev',
    manager: 'Elena Martínez', managerInitials: 'EM',
    lat: 13.9214, lng: -89.8450, status: 'active', employees: 15, warehouses: 1,
    salesThisMonth: 16800, salesLastMonth: 15900, salesYTD: 182400,
    trend: [10, 11, 13, 14, 15, 16, 16.8], openedAt: '05 Jun, 2021',
    area: 540, areaBuilt: 380, areaUnbuilt: 160, floors: 1, parking: 14, capacity: 75,
    propertyType: 'alquilado', areaAvailable: 35, storageCapacity: 100,
    buildingAge: 5, offices: 3, meetingRooms: 1, bathrooms: 2, accesses: 2, emergencyExits: 2,
    accessibility: ['Rampas', 'Estacionamiento preferencial'],
    warehousesDetail: [
      wh('Almacén Ahuachapán', 'ALM-AHU-01', 'Bodega Norte', 100, 64, 'active', 340),
    ],
    constructionType: 'mixto', constructionYear: 2021, condition: 'bueno',
    appraisedValue: 310000, monthlyMaintenance: 820, lastRenovation: '—',
    electricalCapacityKVA: 22, internetProvider: 'Claro Empresas', internetType: 'fibra',
    waterSource: 'red_publica', acSystem: 'mini_split', lighting: 'led',
    cctvCameras: 8, accessControl: 'tarjetas',
    fireSystem: ['Extintores ABC', 'Detectores de humo'],
    hasAlarm: true, exteriorMaterial: 'alucobond', floorMaterial: 'ceramico',
    roofCapacityKgM2: 300, hasBackupGenerator: false, hasUPS: true,
    cleaningProvider: 'Limpieza Total',
    cadastralCode: 'CSS-AHU-0192-A', permitExpiry: '05 Jun, 2027',
    leaseExpiry: '30 Jun, 2026', landlord: 'Inmob. Ahuachapán S.A.',
    schedule: 'Lun–Sáb 8:00–18:00',
    scheduleDetail: [
      { day: 'Lunes', open: '08:00', close: '18:00' },
      { day: 'Martes', open: '08:00', close: '18:00' },
      { day: 'Miércoles', open: '08:00', close: '18:00' },
      { day: 'Jueves', open: '08:00', close: '18:00' },
      { day: 'Viernes', open: '08:00', close: '18:00' },
      { day: 'Sábado', open: '08:00', close: '18:00' },
      { day: 'Domingo', open: null, close: null },
    ],
    zone: 'Occidental',
    services: STD_SERVICES,
    facilities: ['Estacionamiento', 'Aire acondicionado', 'CCTV', 'WiFi clientes'],
    avgTicket: 28.5, monthlyVisitors: 1450, customerRating: 4.4, inventoryTurnover: 7.9,
    lastInspection: '22 Nov, 2024',
    website: 'https://erp-system.dev/sucursales/ahuachapan',
    description: 'Sucursal occidental con cobertura sobre Ahuachapán y la frontera con Guatemala. Atención bilingüe disponible.',
    images: images('br007', ['Fachada', 'Mostrador', 'Pasillo de productos', 'Bodega']),
  },
  {
    id: 'br-008', code: 'COJ-01', name: 'Sucursal Cojutepeque', address: 'Av. Raúl Contreras #10',
    city: 'Cojutepeque', phone: '+503 2372-5500', email: 'cojute@erp-system.dev',
    manager: 'Gabriel Aguilar', managerInitials: 'GA',
    lat: 13.7214, lng: -88.9833, status: 'active', employees: 14, warehouses: 1,
    salesThisMonth: 14900, salesLastMonth: 14200, salesYTD: 161200,
    trend: [9, 10, 11, 13, 14, 14.5, 14.9], openedAt: '19 Oct, 2021',
    area: 470, areaBuilt: 320, areaUnbuilt: 150, floors: 1, parking: 10, capacity: 65,
    propertyType: 'alquilado', areaAvailable: 30, storageCapacity: 80,
    buildingAge: 4, offices: 2, meetingRooms: 1, bathrooms: 2, accesses: 1, emergencyExits: 2,
    accessibility: ['Rampas'],
    warehousesDetail: [
      wh('Almacén Cojutepeque', 'ALM-COJ-01', 'Bodega Central', 80, 56, 'active', 290),
    ],
    constructionType: 'concreto', constructionYear: 2021, condition: 'bueno',
    appraisedValue: 280000, monthlyMaintenance: 680, lastRenovation: '—',
    electricalCapacityKVA: 18, internetProvider: 'Tigo Business', internetType: 'adsl',
    waterSource: 'red_publica', acSystem: 'mini_split', lighting: 'led',
    cctvCameras: 6, accessControl: 'tarjetas',
    fireSystem: ['Extintores ABC'],
    hasAlarm: true, exteriorMaterial: 'alucobond', floorMaterial: 'ceramico',
    roofCapacityKgM2: 280, hasBackupGenerator: false, hasUPS: false,
    cleaningProvider: '—',
    cadastralCode: 'CSS-COJ-0284-B', permitExpiry: '19 Oct, 2027',
    leaseExpiry: '31 Oct, 2026', landlord: 'Inmob. Central Cuscatlán',
    schedule: 'Lun–Sáb 8:00–18:00',
    scheduleDetail: [
      { day: 'Lunes', open: '08:00', close: '18:00' },
      { day: 'Martes', open: '08:00', close: '18:00' },
      { day: 'Miércoles', open: '08:00', close: '18:00' },
      { day: 'Jueves', open: '08:00', close: '18:00' },
      { day: 'Viernes', open: '08:00', close: '18:00' },
      { day: 'Sábado', open: '08:00', close: '18:00' },
      { day: 'Domingo', open: null, close: null },
    ],
    zone: 'Central',
    services: STD_SERVICES,
    facilities: ['Estacionamiento', 'Aire acondicionado', 'CCTV'],
    avgTicket: 25.8, monthlyVisitors: 1200, customerRating: 4.2, inventoryTurnover: 7.4,
    lastInspection: '07 Abr, 2025',
    website: 'https://erp-system.dev/sucursales/cojutepeque',
    description: 'Punto de venta en el corredor central del país, con atención a Cuscatlán y municipios aledaños.',
    images: images('br008', ['Local comercial', 'Interior', 'Caja', 'Almacén']),
  },
  {
    id: 'br-009', code: 'ZAC-01', name: 'Sucursal Zacatecoluca', address: 'Km 56 Carretera a San Salvador',
    city: 'Zacatecoluca', phone: '+503 2334-1200', email: 'zacate@erp-system.dev',
    manager: 'Sofía Benítez', managerInitials: 'SB',
    lat: 13.5083, lng: -88.8667, status: 'active', employees: 16, warehouses: 1,
    salesThisMonth: 18200, salesLastMonth: 17400, salesYTD: 198600,
    trend: [11, 12, 14, 15, 17, 18, 18.2], openedAt: '03 Ene, 2022',
    area: 580, areaBuilt: 400, areaUnbuilt: 180, floors: 1, parking: 18, capacity: 90,
    propertyType: 'propio', areaAvailable: 50, storageCapacity: 130,
    buildingAge: 4, offices: 3, meetingRooms: 1, bathrooms: 2, accesses: 2, emergencyExits: 2,
    accessibility: ['Rampas', 'Estacionamiento preferencial'],
    warehousesDetail: [
      wh('Almacén Zacatecoluca', 'ALM-ZAC-01', 'Bodega A', 130, 75, 'active', 210),
    ],
    constructionType: 'mixto', constructionYear: 2022, condition: 'excelente',
    appraisedValue: 365000, monthlyMaintenance: 890, lastRenovation: '—',
    electricalCapacityKVA: 30, internetProvider: 'Claro Empresas', internetType: 'fibra',
    waterSource: 'red_publica', acSystem: 'mini_split', lighting: 'led',
    cctvCameras: 8, accessControl: 'tarjetas',
    fireSystem: ['Extintores ABC', 'Detectores de humo'],
    hasAlarm: true, exteriorMaterial: 'alucobond', floorMaterial: 'porcelanato',
    roofCapacityKgM2: 350, hasBackupGenerator: false, hasUPS: true,
    cleaningProvider: 'CleanPro SV',
    cadastralCode: 'CSS-ZAC-0108-A', permitExpiry: '03 Ene, 2028',
    leaseExpiry: null, landlord: null,
    schedule: 'Lun–Sáb 8:00–18:00',
    scheduleDetail: [
      { day: 'Lunes', open: '08:00', close: '18:00' },
      { day: 'Martes', open: '08:00', close: '18:00' },
      { day: 'Miércoles', open: '08:00', close: '18:00' },
      { day: 'Jueves', open: '08:00', close: '18:00' },
      { day: 'Viernes', open: '08:00', close: '18:00' },
      { day: 'Sábado', open: '08:00', close: '18:00' },
      { day: 'Domingo', open: null, close: null },
    ],
    zone: 'Paracentral',
    services: STD_SERVICES,
    facilities: ['Estacionamiento', 'Aire acondicionado', 'CCTV', 'WiFi clientes'],
    avgTicket: 31.2, monthlyVisitors: 1380, customerRating: 4.3, inventoryTurnover: 8.1,
    lastInspection: '14 Jun, 2025',
    website: 'https://erp-system.dev/sucursales/zacatecoluca',
    description: 'Sucursal en la zona paracentral costera, atiende el comercio de La Paz y el litoral. Acceso directo desde carretera.',
    images: images('br009', ['Fachada', 'Interior', 'Mostrador', 'Bodega']),
  },
  {
    id: 'br-010', code: 'LIB-01', name: 'Sucursal La Libertad', address: 'Boulevard El Faro #88',
    city: 'La Libertad', phone: '+503 2347-9000', email: 'lalibertad@erp-system.dev',
    manager: 'Diego Castillo', managerInitials: 'DC',
    lat: 13.4883, lng: -89.3222, status: 'active', employees: 29, warehouses: 2,
    salesThisMonth: 41500, salesLastMonth: 38900, salesYTD: 451200,
    trend: [24, 28, 32, 35, 38, 40, 41.5], openedAt: '28 Abr, 2019',
    area: 1050, areaBuilt: 720, areaUnbuilt: 330, floors: 2, parking: 35, capacity: 160,
    propertyType: 'propio', areaAvailable: 90, storageCapacity: 280,
    buildingAge: 7, offices: 8, meetingRooms: 2, bathrooms: 4, accesses: 3, emergencyExits: 4,
    accessibility: ['Rampas', 'Ascensor', 'Baño accesible', 'Estacionamiento preferencial', 'Terraza accesible'],
    warehousesDetail: [
      wh('Almacén La Libertad A', 'ALM-LIB-01', 'Bodega automatizada', 180, 126, 'active', 680),
      wh('Almacén La Libertad B', 'ALM-LIB-02', 'Bodega anexa', 100, 70, 'active', 420),
    ],
    constructionType: 'concreto', constructionYear: 2019, condition: 'excelente',
    appraisedValue: 780000, monthlyMaintenance: 2400, lastRenovation: '10 Ene, 2024',
    electricalCapacityKVA: 85, internetProvider: 'Tigo Business', internetType: 'fibra',
    waterSource: 'red_publica', acSystem: 'central', lighting: 'led',
    cctvCameras: 22, accessControl: 'biometrico',
    fireSystem: ['Detectores de humo', 'Rociadores', 'Extintores ABC', 'Alarma central'],
    hasAlarm: true, exteriorMaterial: 'cristal', floorMaterial: 'porcelanato',
    roofCapacityKgM2: 500, hasBackupGenerator: true, hasUPS: true,
    cleaningProvider: 'CleanPro SV',
    cadastralCode: 'CSS-LIB-0098-B', permitExpiry: '28 Abr, 2027',
    leaseExpiry: null, landlord: null,
    schedule: 'Lun–Dom 7:00–21:00',
    scheduleDetail: STD_SCHEDULE.map((d) => ({ ...d, open: '07:00', close: '21:00' })),
    zone: 'Costera',
    services: ['Punto de venta', 'Bodega', 'Servicio al cliente', 'Devoluciones', 'Entregas a domicilio', 'Click & Collect'],
    facilities: ['Estacionamiento', 'Aire acondicionado', 'CCTV 24/7', 'WiFi clientes', 'Cafetería', 'Terraza', 'Generador eléctrico'],
    avgTicket: 44.3, monthlyVisitors: 3200, customerRating: 4.7, inventoryTurnover: 13.1,
    lastInspection: '02 May, 2025',
    website: 'https://erp-system.dev/sucursales/la-libertad',
    description: 'Sucursal de alto rendimiento en la zona costera occidental, con flujo turístico y comercial elevado. Operación extendida 7 días a la semana.',
    images: images('br010', ['Fachada moderna', 'Área de ventas', 'Cafetería interna', 'Bodega automatizada']),
  },
  {
    id: 'br-011', code: 'SOY-01', name: 'Sucursal Soyapango', address: 'Plaza Unicentro, Local 14',
    city: 'Soyapango', phone: '+503 2277-3310', email: 'soyapango@erp-system.dev',
    manager: 'Patricia Orellana', managerInitials: 'PO',
    lat: 13.7100, lng: -89.1400, status: 'active', employees: 31, warehouses: 2,
    salesThisMonth: 39800, salesLastMonth: 37200, salesYTD: 432500,
    trend: [26, 29, 31, 34, 36, 38, 39.8], openedAt: '17 Sep, 2018',
    area: 980, areaBuilt: 680, areaUnbuilt: 300, floors: 2, parking: 30, capacity: 150,
    propertyType: 'arrendado', areaAvailable: 70, storageCapacity: 240,
    buildingAge: 8, offices: 7, meetingRooms: 2, bathrooms: 4, accesses: 2, emergencyExits: 3,
    accessibility: ['Rampas', 'Ascensor', 'Baño accesible'],
    warehousesDetail: [
      wh('Almacén Soyapango A', 'ALM-SOY-01', 'Bodega mezzanine', 140, 112, 'active', 540),
      wh('Almacén Soyapango B', 'ALM-SOY-02', 'Bodega sótano', 100, 65, 'active', 380),
    ],
    constructionType: 'concreto', constructionYear: 2018, condition: 'excelente',
    appraisedValue: 720000, monthlyMaintenance: 2100, lastRenovation: '20 Sep, 2024',
    electricalCapacityKVA: 70, internetProvider: 'Tigo Business', internetType: 'fibra',
    waterSource: 'red_publica', acSystem: 'central', lighting: 'led',
    cctvCameras: 20, accessControl: 'biometrico',
    fireSystem: ['Detectores de humo', 'Rociadores', 'Extintores ABC', 'Alarma central'],
    hasAlarm: true, exteriorMaterial: 'cristal', floorMaterial: 'porcelanato',
    roofCapacityKgM2: 480, hasBackupGenerator: true, hasUPS: true,
    cleaningProvider: 'ServiLimp',
    cadastralCode: 'CSS-SOY-0167-C', permitExpiry: '17 Sep, 2027',
    leaseExpiry: '31 Ago, 2028', landlord: 'Plaza Unicentro S.A.',
    schedule: 'Lun–Dom 8:00–20:00',
    scheduleDetail: STD_SCHEDULE.map((d) => ({ ...d, open: '08:00', close: '20:00' })),
    zone: 'Metropolitana',
    services: ['Punto de venta', 'Bodega', 'Servicio al cliente', 'Devoluciones', 'Entregas a domicilio', 'Cobros de servicios'],
    facilities: ['Estacionamiento', 'Aire acondicionado', 'CCTV 24/7', 'WiFi clientes', 'Ascensor', 'Rampa de acceso'],
    avgTicket: 42.1, monthlyVisitors: 2900, customerRating: 4.6, inventoryTurnover: 12.8,
    lastInspection: '19 Mar, 2025',
    website: 'https://erp-system.dev/sucursales/soyapango',
    description: 'Sucursal en el área metropolitana de San Salvador, alto flujo de clientes y rotación de inventario. Ubicada en centro comercial.',
    images: images('br011', ['Entrada principal', 'Pasillo central', 'Cajas rápidas', 'Bodega mezzanine']),
  },
  {
    id: 'br-012', code: 'UNI-01', name: 'Sucursal La Unión', address: 'Puerto Corsario #2',
    city: 'La Unión', phone: '+503 2604-1190', email: 'launion@erp-system.dev',
    manager: 'Mario Morales', managerInitials: 'MM',
    lat: 13.3333, lng: -87.8433, status: 'maintenance', employees: 9, warehouses: 1,
    salesThisMonth: 0, salesLastMonth: 0, salesYTD: 98400,
    trend: [10, 8, 5, 3, 1, 0, 0], openedAt: '11 Nov, 2022',
    area: 430, areaBuilt: 300, areaUnbuilt: 130, floors: 1, parking: 10, capacity: 60,
    propertyType: 'alquilado', areaAvailable: 0, storageCapacity: 75,
    buildingAge: 4, offices: 2, meetingRooms: 0, bathrooms: 2, accesses: 1, emergencyExits: 2,
    accessibility: ['Rampas'],
    warehousesDetail: [
      wh('Almacén La Unión', 'ALM-UNI-01', 'Bodega principal', 75, 30, 'maintenance', 120),
    ],
    constructionType: 'mixto', constructionYear: 2022, condition: 'regular',
    appraisedValue: 240000, monthlyMaintenance: 1450, lastRenovation: '—',
    electricalCapacityKVA: 20, internetProvider: 'Tigo Business', internetType: 'adsl',
    waterSource: 'cisterna', acSystem: 'mini_split', lighting: 'mixta',
    cctvCameras: 4, accessControl: 'teclado',
    fireSystem: ['Extintores ABC'],
    hasAlarm: false, exteriorMaterial: 'alucobond', floorMaterial: 'cemento',
    roofCapacityKgM2: 250, hasBackupGenerator: false, hasUPS: false,
    cleaningProvider: '—',
    cadastralCode: 'CSS-UNI-0023-D', permitExpiry: '11 Nov, 2026',
    leaseExpiry: '31 Oct, 2026', landlord: 'Fam. Morales Quintanilla',
    schedule: 'Lun–Vie 8:00–17:00',
    scheduleDetail: [
      { day: 'Lunes', open: '08:00', close: '17:00' },
      { day: 'Martes', open: '08:00', close: '17:00' },
      { day: 'Miércoles', open: '08:00', close: '17:00' },
      { day: 'Jueves', open: '08:00', close: '17:00' },
      { day: 'Viernes', open: '08:00', close: '17:00' },
      { day: 'Sábado', open: null, close: null },
      { day: 'Domingo', open: null, close: null },
    ],
    zone: 'Oriental',
    services: ['Punto de venta', 'Bodega'],
    facilities: ['Estacionamiento', 'CCTV'],
    avgTicket: 0, monthlyVisitors: 0, customerRating: 3.9, inventoryTurnover: 0,
    lastInspection: '30 Sep, 2024',
    website: 'https://erp-system.dev/sucursales/la-union',
    description: 'Sucursal oriental en mantenimiento preventivo de infraestructura eléctrica y de climatización. Reapertura estimada en 6 semanas.',
    images: images('br012', ['Exterior', 'Área de trabajo', 'Sistema eléctrico', 'Bodega']),
  },
  {
    id: 'br-013', code: 'VIC-01', name: 'Sucursal San Vicente', address: 'Barrio El Santuario #3',
    city: 'San Vicente', phone: '+503 2393-0040', email: 'sanvicente@erp-system.dev',
    manager: 'Claudia Mendoza', managerInitials: 'CM',
    lat: 13.6333, lng: -88.7833, status: 'active', employees: 17, warehouses: 1,
    salesThisMonth: 15600, salesLastMonth: 14900, salesYTD: 168900,
    trend: [10, 11, 12, 13, 14, 15, 15.6], openedAt: '20 Jul, 2021',
    area: 520, areaBuilt: 360, areaUnbuilt: 160, floors: 1, parking: 12, capacity: 70,
    propertyType: 'alquilado', areaAvailable: 40, storageCapacity: 95,
    buildingAge: 5, offices: 3, meetingRooms: 1, bathrooms: 2, accesses: 2, emergencyExits: 2,
    accessibility: ['Rampas', 'Estacionamiento preferencial'],
    warehousesDetail: [
      wh('Almacén San Vicente', 'ALM-VIC-01', 'Bodega principal', 95, 58, 'active', 250),
    ],
    constructionType: 'mixto', constructionYear: 2021, condition: 'bueno',
    appraisedValue: 295000, monthlyMaintenance: 760, lastRenovation: '—',
    electricalCapacityKVA: 20, internetProvider: 'Claro Empresas', internetType: 'fibra',
    waterSource: 'red_publica', acSystem: 'mini_split', lighting: 'led',
    cctvCameras: 6, accessControl: 'tarjetas',
    fireSystem: ['Extintores ABC', 'Detectores de humo'],
    hasAlarm: true, exteriorMaterial: 'alucobond', floorMaterial: 'ceramico',
    roofCapacityKgM2: 280, hasBackupGenerator: false, hasUPS: false,
    cleaningProvider: 'Limpieza Total',
    cadastralCode: 'CSS-VIC-0071-A', permitExpiry: '20 Jul, 2027',
    leaseExpiry: '31 Jul, 2026', landlord: 'Inmob. Vicenteña S.A.',
    schedule: 'Lun–Sáb 8:00–18:00',
    scheduleDetail: [
      { day: 'Lunes', open: '08:00', close: '18:00' },
      { day: 'Martes', open: '08:00', close: '18:00' },
      { day: 'Miércoles', open: '08:00', close: '18:00' },
      { day: 'Jueves', open: '08:00', close: '18:00' },
      { day: 'Viernes', open: '08:00', close: '18:00' },
      { day: 'Sábado', open: '08:00', close: '18:00' },
      { day: 'Domingo', open: null, close: null },
    ],
    zone: 'Paracentral',
    services: STD_SERVICES,
    facilities: ['Estacionamiento', 'Aire acondicionado', 'CCTV', 'WiFi clientes'],
    avgTicket: 26.4, monthlyVisitors: 1150, customerRating: 4.2, inventoryTurnover: 7.6,
    lastInspection: '11 Jul, 2025',
    website: 'https://erp-system.dev/sucursales/san-vicente',
    description: 'Sucursal en el departamento de San Vicente, con cobertura sobre el corredor paracentral y zonas rurales aledañas.',
    images: images('br013', ['Fachada', 'Interior', 'Mostrador', 'Bodega']),
  },
];

export const STATUS_MAP: Record<string, { label: string; variant: 'success' | 'neutral' | 'warning' }> = {
  active: { label: 'Activa', variant: 'success' },
  inactive: { label: 'Inactiva', variant: 'neutral' },
  maintenance: { label: 'Mantenimiento', variant: 'warning' },
};