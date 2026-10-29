export type VehicleStatus = 'En ruta' | 'Disponible' | 'Mantenimiento';
export const VEHICLE_TYPES = {
  Refrigerado: { label: 'Refrigerados', image: '/images/fleet/refrigerated-truck.png' },
  Furgón: { label: 'Furgones', image: '/images/fleet/cargo-van.png' },
  'Carga seca': { label: 'Carga seca', image: '/images/fleet/dry-box-truck.png' },
  Pickup: { label: 'Pickups', image: '/images/fleet/pickup.png' },
  Plataforma: { label: 'Plataformas', image: '/images/fleet/flatbed-truck.png' },
  'Panel compacto': { label: 'Paneles compactos', image: '/images/fleet/compact-panel-van.png' },
  'Con lona': { label: 'Camiones con lona', image: '/images/fleet/curtain-side-truck.png' },
  Tráiler: { label: 'Tráileres', image: '/images/fleet/semi-trailer-truck.png' },
  Cisterna: { label: 'Cisternas', image: '/images/fleet/tanker-truck.png' }
} as const;
export type VehicleKind = keyof typeof VEHICLE_TYPES;
export const VEHICLE_KINDS = Object.keys(VEHICLE_TYPES) as VehicleKind[];

export const VEHICLE_DOCUMENTS = {
  circulation: { label: 'Tarjeta de circulación', short: 'Tarjeta de circulación', feminine: true },
  insurance: { label: 'Seguro del vehículo', short: 'Seguro', feminine: false },
  inspection: { label: 'Revisión técnica', short: 'Revisión técnica', feminine: true }
} as const;
export type VehicleDocumentKind = keyof typeof VEHICLE_DOCUMENTS;

export interface VehicleDocument {
  kind: VehicleDocumentKind;
  /** Fecha ISO de vencimiento. */
  expires: string;
}

/** Fecha de referencia de la maqueta; las alertas se calculan contra este día. */
export const FLEET_TODAY = '2026-10-28';

export interface FleetVehicle {
  id: string;
  name: string;
  plate: string;
  kind: VehicleKind;
  model: string;
  year: number;
  status: VehicleStatus;
  driver: string;
  initials: string;
  location: string;
  destination: string;
  capacity: number;
  load: number;
  mileage: number;
  fuel: number;
  progress: number;
  arrival: string;
  /** Fecha ISO del próximo servicio preventivo; null mientras está en taller. */
  serviceDue: string | null;
  documents: VehicleDocument[];
}

// Fictional presentation data. This workspace never reads or writes fleet records.
export const DEMO_VEHICLES: FleetVehicle[] = [
  {
    id: 'FL-001',
    name: 'Refrigerado de distribución',
    plate: 'C 123-456',
    kind: 'Refrigerado',
    model: 'Isuzu ELF 400',
    year: 2024,
    status: 'En ruta',
    driver: 'Carlos Martínez',
    initials: 'CM',
    location: 'San Miguel',
    destination: 'Santa Rosa de Lima',
    capacity: 4000,
    load: 2880,
    mileage: 42680,
    fuel: 78,
    progress: 64,
    arrival: '10:45 a. m.',
    serviceDue: '2026-11-12',
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2026-11-02' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  },
  {
    id: 'FL-002',
    name: 'Furgón de reparto',
    plate: 'C 234-567',
    kind: 'Furgón',
    model: 'Ford Transit',
    year: 2023,
    status: 'Disponible',
    driver: 'Ana Rodríguez',
    initials: 'AR',
    location: 'Centro de distribución',
    destination: 'Sin ruta asignada',
    capacity: 1500,
    load: 0,
    mileage: 31840,
    fuel: 92,
    progress: 0,
    arrival: 'Lista para salir',
    serviceDue: '2026-10-31',
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2027-03-15' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  },
  {
    id: 'FL-003',
    name: 'Camión de carga seca',
    plate: 'C 345-678',
    kind: 'Carga seca',
    model: 'Hino Serie 300',
    year: 2024,
    status: 'En ruta',
    driver: 'José Hernández',
    initials: 'JH',
    location: 'San Miguel',
    destination: 'La Unión',
    capacity: 4000,
    load: 3360,
    mileage: 38650,
    fuel: 64,
    progress: 38,
    arrival: '11:20 a. m.',
    serviceDue: '2026-11-20',
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2027-03-15' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  },
  {
    id: 'FL-004',
    name: 'Pickup de reparto local',
    plate: 'C 456-789',
    kind: 'Pickup',
    model: 'Toyota Hilux',
    year: 2023,
    status: 'En ruta',
    driver: 'Diego Ramírez',
    initials: 'DR',
    location: 'San Miguel',
    destination: 'Usulután',
    capacity: 1000,
    load: 650,
    mileage: 56210,
    fuel: 56,
    progress: 82,
    arrival: '09:50 a. m.',
    serviceDue: '2026-10-25',
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2027-03-15' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  },
  {
    id: 'FL-005',
    name: 'Refrigerado de distribución',
    plate: 'C 567-890',
    kind: 'Refrigerado',
    model: 'Isuzu ELF 400',
    year: 2022,
    status: 'Mantenimiento',
    driver: 'Luis Flores',
    initials: 'LF',
    location: 'Taller central',
    destination: 'Servicio preventivo',
    capacity: 4000,
    load: 0,
    mileage: 82400,
    fuel: 45,
    progress: 0,
    arrival: 'Entrega: 30 oct',
    serviceDue: null,
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2027-03-15' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  },
  {
    id: 'FL-006',
    name: 'Furgón de reparto',
    plate: 'C 678-901',
    kind: 'Furgón',
    model: 'Ford Transit',
    year: 2024,
    status: 'Disponible',
    driver: 'Sofía Castro',
    initials: 'SC',
    location: 'Centro de distribución',
    destination: 'Sin ruta asignada',
    capacity: 1500,
    load: 0,
    mileage: 18920,
    fuel: 88,
    progress: 0,
    arrival: 'Lista para salir',
    serviceDue: '2026-11-25',
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2027-03-15' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  },
  {
    id: 'FL-007',
    name: 'Plataforma de carga',
    plate: 'C 789-012',
    kind: 'Plataforma',
    model: 'Isuzu NPR 75',
    year: 2023,
    status: 'En ruta',
    driver: 'Miguel Pérez',
    initials: 'MP',
    location: 'San Miguel',
    destination: 'Jiquilisco',
    capacity: 4500,
    load: 2745,
    mileage: 64350,
    fuel: 71,
    progress: 46,
    arrival: '11:05 a. m.',
    serviceDue: '2026-11-15',
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2027-03-15' },
      { kind: 'inspection', expires: '2026-10-20' }
    ]
  },
  {
    id: 'FL-008',
    name: 'Pickup de apoyo operativo',
    plate: 'C 890-123',
    kind: 'Pickup',
    model: 'Toyota Hilux',
    year: 2024,
    status: 'Disponible',
    driver: 'Valeria López',
    initials: 'VL',
    location: 'Centro de distribución',
    destination: 'Sin ruta asignada',
    capacity: 1000,
    load: 0,
    mileage: 22740,
    fuel: 96,
    progress: 0,
    arrival: 'Lista para salir',
    serviceDue: '2026-11-28',
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2027-03-15' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  },
  {
    id: 'FL-009',
    name: 'Refrigerado de distribución',
    plate: 'C 901-234',
    kind: 'Refrigerado',
    model: 'Isuzu ELF 400',
    year: 2023,
    status: 'En ruta',
    driver: 'Andrés Rivera',
    initials: 'AR',
    location: 'San Miguel',
    destination: 'El Tránsito',
    capacity: 4000,
    load: 1920,
    mileage: 49210,
    fuel: 82,
    progress: 27,
    arrival: '10:30 a. m.',
    serviceDue: '2026-11-22',
    documents: [
      { kind: 'circulation', expires: '2026-11-20' },
      { kind: 'insurance', expires: '2027-03-15' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  },
  {
    id: 'FL-010',
    name: 'Panel de reparto urbano',
    plate: 'C 102-345',
    kind: 'Panel compacto',
    model: 'Volkswagen Caddy Cargo',
    year: 2025,
    status: 'Disponible',
    driver: 'Gabriela Torres',
    initials: 'GT',
    location: 'Centro de distribución',
    destination: 'Sin ruta asignada',
    capacity: 750,
    load: 0,
    mileage: 12640,
    fuel: 94,
    progress: 0,
    arrival: 'Lista para salir',
    serviceDue: '2026-11-26',
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2027-03-15' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  },
  {
    id: 'FL-011',
    name: 'Camión de carga con lona',
    plate: 'C 213-456',
    kind: 'Con lona',
    model: 'Hino Serie 500',
    year: 2023,
    status: 'En ruta',
    driver: 'Ricardo Aguilar',
    initials: 'RA',
    location: 'San Miguel',
    destination: 'San Salvador',
    capacity: 8000,
    load: 5200,
    mileage: 73560,
    fuel: 76,
    progress: 52,
    arrival: '12:15 p. m.',
    serviceDue: '2026-11-16',
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2027-03-15' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  },
  {
    id: 'FL-012',
    name: 'Tráiler de abastecimiento',
    plate: 'C 324-567',
    kind: 'Tráiler',
    model: 'Volvo FH',
    year: 2024,
    status: 'En ruta',
    driver: 'Fernando Molina',
    initials: 'FM',
    location: 'San Miguel',
    destination: 'Santa Ana',
    capacity: 24000,
    load: 18000,
    mileage: 58720,
    fuel: 83,
    progress: 31,
    arrival: '01:40 p. m.',
    serviceDue: '2026-11-21',
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2026-10-28' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  },
  {
    id: 'FL-013',
    name: 'Cisterna de líquidos alimentarios',
    plate: 'C 435-678',
    kind: 'Cisterna',
    model: 'Isuzu FVR',
    year: 2022,
    status: 'Mantenimiento',
    driver: 'Patricia Vásquez',
    initials: 'PV',
    location: 'Taller central',
    destination: 'Inspección de válvulas',
    capacity: 12000,
    load: 0,
    mileage: 91680,
    fuel: 62,
    progress: 0,
    arrival: 'Entrega: 31 oct',
    serviceDue: null,
    documents: [
      { kind: 'circulation', expires: '2027-06-30' },
      { kind: 'insurance', expires: '2027-03-15' },
      { kind: 'inspection', expires: '2027-01-20' }
    ]
  }
];

export const formatFleetNumber = (value: number) => new Intl.NumberFormat('es-SV').format(value);
export const formatFleetDate = (iso: string) =>
  new Intl.DateTimeFormat('es-SV', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC'
  })
    .format(new Date(`${iso}T00:00:00Z`))
    .replace('.', '');
export const vehicleImage = (vehicle: FleetVehicle) => VEHICLE_TYPES[vehicle.kind].image;

export const statusTone = (status: VehicleStatus) =>
  status === 'En ruta' ? 'route' : status === 'Disponible' ? 'available' : 'maintenance';
