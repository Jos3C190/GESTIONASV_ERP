export const DIMENSION_UNITS = [
  { value: 'mm', label: 'Milímetro (mm)', factorToMeters: 0.001 },
  { value: 'cm', label: 'Centímetro (cm)', factorToMeters: 0.01 },
  { value: 'm', label: 'Metro (m)', factorToMeters: 1 },
  { value: 'in', label: 'Pulgada (in)', factorToMeters: 0.0254 },
  { value: 'ft', label: 'Pie (ft)', factorToMeters: 0.3048 }
] as const;

export const WEIGHT_UNITS = [
  { value: 'mg', label: 'Miligramo (mg)' },
  { value: 'g', label: 'Gramo (g)' },
  { value: 'kg', label: 'Kilogramo (kg)' },
  { value: 't', label: 'Tonelada (t)' },
  { value: 'oz', label: 'Onza (oz)' },
  { value: 'lb', label: 'Libra (lb)' }
] as const;

export type DimensionUnit = (typeof DIMENSION_UNITS)[number]['value'];
export type WeightUnit = (typeof WEIGHT_UNITS)[number]['value'];

export function calculateProductVolume(
  length: number | null | undefined,
  width: number | null | undefined,
  height: number | null | undefined,
  unit: DimensionUnit | string | null | undefined
): number | null {
  if (length == null || width == null || height == null || unit == null) return null;
  const factor = DIMENSION_UNITS.find((item) => item.value === unit)?.factorToMeters;
  if (factor == null) return null;
  return length * factor * (width * factor) * (height * factor);
}

export function formatProductDimensions(
  length: number | null | undefined,
  width: number | null | undefined,
  height: number | null | undefined,
  unit: string | null | undefined
): string | null {
  if (length == null && width == null && height == null) return null;
  if (!unit) return null;
  return `${length ?? '—'} × ${width ?? '—'} × ${height ?? '—'} ${unit}`;
}
