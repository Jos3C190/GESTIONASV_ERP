export interface BranchImage {
  url: string;
  caption: string;
  public_id?: string;
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
  companyId?: string;
  departmentId?: string;
  municipalityId?: string;
  districtId?: string;
  code: string;
  name: string;
  address: string;
  city: string;
  phone: string;
  email: string;
  manager: string;
  managerEmployeeId?: string | null;
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
  area: number;
  areaBuilt: number;
  areaUnbuilt: number;
  floors: number;
  parking: number;
  capacity: number;
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
  warehousesDetail: WarehouseDetail[];
  constructionType: 'concreto' | 'metalico' | 'mixto' | 'prefabricado';
  constructionYear: number;
  condition: 'excelente' | 'bueno' | 'regular' | 'malo';
  appraisedValue: number;
  monthlyMaintenance: number;
  lastRenovation: string;
  electricalCapacityKVA: number;
  internetProvider: string;
  internetType: 'fibra' | 'adsl' | 'satelital' | '4g';
  waterSource: 'red_publica' | 'pozo' | 'cisterna' | 'mixta';
  acSystem: 'central' | 'individual' | 'mini_split' | 'mixto' | 'sin_ac';
  lighting: 'led' | 'fluorescente' | 'mixta';
  cctvCameras: number;
  accessControl: 'biometrico' | 'tarjetas' | 'teclado' | 'sin_control';
  fireSystem: string[];
  hasAlarm: boolean;
  exteriorMaterial: 'cristal' | 'alucobond' | 'concreto' | 'mixta';
  floorMaterial: 'porcelanato' | 'ceramico' | 'epoxico' | 'concreto_pulido' | 'cemento';
  roofCapacityKgM2: number;
  hasBackupGenerator: boolean;
  hasUPS: boolean;
  cleaningProvider: string;
  cadastralCode: string;
  permitExpiry: string;
  leaseExpiry: string | null;
  landlord: string | null;
  schedule: string;
  scheduleDetail: ScheduleDay[];
  zone: string;
  services: string[];
  facilities: string[];
  avgTicket: number;
  monthlyVisitors: number;
  customerRating: number;
  inventoryTurnover: number;
  lastInspection: string;
  website: string;
  description: string;
  images: BranchImage[];
}
export const STATUS_MAP: Record<
  string,
  { label: string; variant: 'success' | 'neutral' | 'warning' }
> = {
  active: { label: 'Activa', variant: 'success' },
  inactive: { label: 'Inactiva', variant: 'neutral' },
  maintenance: { label: 'Mantenimiento', variant: 'warning' }
};
