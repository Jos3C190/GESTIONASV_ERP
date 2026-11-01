/** Vehicle kinds, statuses and formatting shared by Fleet, Drivers and Tracking. */

export const VEHICLE_KINDS = [
  'refrigerated',
  'cargo_van',
  'dry_box',
  'pickup',
  'flatbed',
  'compact_van',
  'curtain_side',
  'semi_trailer',
  'tanker'
] as const;
export type VehicleKind = (typeof VEHICLE_KINDS)[number];

/** Base images are shared by every company; the company's logo is applied on top. */
export const KIND_META: Record<VehicleKind, { label: string; plural: string; image: string }> = {
  refrigerated: {
    label: 'Refrigerado',
    plural: 'Refrigerados',
    image: '/images/fleet/refrigerated-truck.png'
  },
  cargo_van: { label: 'Furgón', plural: 'Furgones', image: '/images/fleet/cargo-van.png' },
  dry_box: { label: 'Carga seca', plural: 'Carga seca', image: '/images/fleet/dry-box-truck.png' },
  pickup: { label: 'Pickup', plural: 'Pickups', image: '/images/fleet/pickup.png' },
  flatbed: { label: 'Plataforma', plural: 'Plataformas', image: '/images/fleet/flatbed-truck.png' },
  compact_van: {
    label: 'Panel compacto',
    plural: 'Paneles compactos',
    image: '/images/fleet/compact-panel-van.png'
  },
  curtain_side: {
    label: 'Con lona',
    plural: 'Camiones con lona',
    image: '/images/fleet/curtain-side-truck.png'
  },
  semi_trailer: {
    label: 'Tráiler',
    plural: 'Tráileres',
    image: '/images/fleet/semi-trailer-truck.png'
  },
  tanker: { label: 'Cisterna', plural: 'Cisternas', image: '/images/fleet/tanker-truck.png' }
};

export type VehicleStatus = 'active' | 'maintenance' | 'out_of_service' | 'retired';
export type OperationalStatus =
  'available' | 'in_route' | 'maintenance' | 'out_of_service' | 'retired';

export const OPERATIONAL_META: Record<
  OperationalStatus,
  { label: string; tone: 'available' | 'route' | 'maintenance' | 'muted' }
> = {
  available: { label: 'Disponible', tone: 'available' },
  in_route: { label: 'En ruta', tone: 'route' },
  maintenance: { label: 'Mantenimiento', tone: 'maintenance' },
  out_of_service: { label: 'Fuera de servicio', tone: 'muted' },
  retired: { label: 'Dado de baja', tone: 'muted' }
};

export const VEHICLE_STATUS_LABELS: Record<VehicleStatus, string> = {
  active: 'Activo',
  maintenance: 'En mantenimiento',
  out_of_service: 'Fuera de servicio',
  retired: 'Dado de baja'
};

export type FuelType = 'diesel' | 'gasoline' | 'lpg' | 'electric' | 'hybrid';
export const FUEL_LABELS: Record<FuelType, string> = {
  diesel: 'Diésel',
  gasoline: 'Gasolina',
  lpg: 'Gas LP',
  electric: 'Eléctrico',
  hybrid: 'Híbrido'
};

export type LicenseClass = 'particular' | 'liviana' | 'pesada' | 'pesada_t' | 'motocicleta';
export const LICENSE_LABELS: Record<LicenseClass, string> = {
  particular: 'Particular',
  liviana: 'Liviana',
  pesada: 'Pesada',
  pesada_t: 'Pesada T',
  motocicleta: 'Motocicleta'
};

const numberFormat = new Intl.NumberFormat('es-SV', { maximumFractionDigits: 1 });
const moneyFormat = new Intl.NumberFormat('es-SV', { style: 'currency', currency: 'USD' });

export const formatNumber = (value: number | string | null | undefined) =>
  value === null || value === undefined || value === '' ? '—' : numberFormat.format(Number(value));

export const formatMoney = (value: number | string | null | undefined) =>
  value === null || value === undefined || value === '' ? '—' : moneyFormat.format(Number(value));

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value);
  return new Intl.DateTimeFormat('es-SV', { day: '2-digit', month: 'short', year: 'numeric' })
    .format(date)
    .replace('.', '');
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat('es-SV', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
    .format(new Date(value))
    .replace('.', '');
}
