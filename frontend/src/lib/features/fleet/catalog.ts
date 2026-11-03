/** Vehicle kinds, statuses and formatting shared by Fleet, Drivers and Tracking. */

export const BASE_IMAGE_KEYS = [
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
export type BaseImage = (typeof BASE_IMAGE_KEYS)[number];
export type MeterUnit = 'km' | 'hours';

/** Base images are shared by every company; the company's logo is applied on top. */
export const BASE_IMAGES: Record<BaseImage, { label: string; image: string }> = {
  refrigerated: {
    label: 'Refrigerado',
    image: '/images/fleet/refrigerated-truck.png'
  },
  cargo_van: { label: 'Furgón', image: '/images/fleet/cargo-van.png' },
  dry_box: { label: 'Carga seca', image: '/images/fleet/dry-box-truck.png' },
  pickup: { label: 'Pickup', image: '/images/fleet/pickup.png' },
  flatbed: { label: 'Plataforma', image: '/images/fleet/flatbed-truck.png' },
  compact_van: {
    label: 'Panel compacto',
    image: '/images/fleet/compact-panel-van.png'
  },
  curtain_side: {
    label: 'Con lona',
    image: '/images/fleet/curtain-side-truck.png'
  },
  semi_trailer: {
    label: 'Tráiler',
    image: '/images/fleet/semi-trailer-truck.png'
  },
  tanker: { label: 'Cisterna', image: '/images/fleet/tanker-truck.png' }
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

export type FuelType = 'diesel' | 'gasoline' | 'lpg' | 'electric' | 'hybrid' | 'none';

export const meterShort = (unit: MeterUnit) => (unit === 'hours' ? 'h' : 'km');
export const meterName = (unit: MeterUnit) => (unit === 'hours' ? 'Horómetro' : 'Odómetro');
/** Un salto mayor suele ser un dedo de más: se pide confirmar, sin bloquear. */
export const meterJumpLimit = (unit: MeterUnit) => (unit === 'hours' ? 500 : 5000);
export const plateLabel = (plate: string | null | undefined) => plate || 'Sin placa';

export type Ownership = 'owned' | 'leased' | 'rented' | 'third_party';
export const OWNERSHIP_LABELS: Record<Ownership, string> = {
  owned: 'Propio',
  leased: 'Arrendado',
  rented: 'Alquilado',
  third_party: 'De un tercero'
};

export type CostCategory = 'insurance' | 'tax' | 'washing' | 'fee' | 'toll' | 'other';
export const COST_CATEGORY_LABELS: Record<CostCategory, string> = {
  insurance: 'Seguro',
  tax: 'Impuesto',
  washing: 'Lavado',
  fee: 'Cuota',
  toll: 'Peaje',
  other: 'Otro'
};

/** A date as the user's calendar shows it, not as UTC. */
export function localDate(date: Date): string {
  const shifted = new Date(date);
  shifted.setMinutes(shifted.getMinutes() - shifted.getTimezoneOffset());
  return shifted.toISOString().slice(0, 10);
}

export type CostPeriodId = 'month' | 'last_month' | 'year';

export function costPeriods(today: Date): Record<CostPeriodId, { from: string; to: string }> {
  const year = today.getFullYear();
  const month = today.getMonth();
  return {
    month: { from: localDate(new Date(year, month, 1)), to: localDate(today) },
    last_month: {
      from: localDate(new Date(year, month - 1, 1)),
      to: localDate(new Date(year, month, 0))
    },
    year: { from: localDate(new Date(year, 0, 1)), to: localDate(today) }
  };
}

/** Un `type="number"` vacío llega como null al enlazarse, no como cadena vacía. */
export function isBlank(value: unknown): boolean {
  return value === '' || value === null || value === undefined;
}

export const FUEL_LABELS: Record<FuelType, string> = {
  diesel: 'Diésel',
  gasoline: 'Gasolina',
  lpg: 'Gas LP',
  electric: 'Eléctrico',
  hybrid: 'Híbrido',
  none: 'No aplica'
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

const rateFormat = new Intl.NumberFormat('es-SV', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4
});
/** A cost per km can be a fraction of a cent: two decimals would round it to $0.00. */
export const formatRate = (value: number | string) => rateFormat.format(Number(value));

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
