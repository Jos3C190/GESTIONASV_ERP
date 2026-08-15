import { z } from 'zod';
import type { LocationBatchAxis, LocationDraft, LocationMutationInput } from './types';

const coordinate = (label: string) =>
  z
    .string()
    .trim()
    .min(1, `${label} es obligatorio.`)
    .max(64, `${label} no puede exceder 64 caracteres.`);

const numericDraftValue = (schema: z.ZodType<string>) =>
  z.preprocess((value) => {
    if (value == null) return '';
    return typeof value === 'number' ? String(value) : value;
  }, schema);

export const locationDraftSchema = z.object({
  area: z.string().trim().max(64, 'El área no puede exceder 64 caracteres.'),
  aisle: coordinate('El pasillo'),
  rack: coordinate('El rack'),
  level: coordinate('El nivel'),
  position: coordinate('La posición'),
  capacity: numericDraftValue(
    z
      .string()
      .trim()
      .min(1, 'La capacidad es obligatoria.')
      .refine((value) => Number.isInteger(Number(value)) && Number(value) > 0, {
        message: 'La capacidad debe ser un entero mayor que cero.'
      })
  ),
  notes: z.string().trim().max(4000, 'Las notas no pueden exceder 4,000 caracteres.'),
  location_type: z.string().trim().min(1, 'Seleccione un tipo de ubicación.'),
  lifecycle_status: z.string().trim().min(1, 'Seleccione un estado operativo.'),
  pick_sequence: numericDraftValue(
    z
      .string()
      .trim()
      .refine((value) => value === '' || (Number.isInteger(Number(value)) && Number(value) >= 0), {
        message: 'La secuencia de picking debe ser un entero positivo.'
      })
  ),
  putaway_sequence: numericDraftValue(
    z
      .string()
      .trim()
      .refine((value) => value === '' || (Number.isInteger(Number(value)) && Number(value) >= 0), {
        message: 'La secuencia de acomodo debe ser un entero positivo.'
      })
  ),
  external_id: z.string().trim().max(120, 'La referencia externa no puede exceder 120 caracteres.'),
  barcode: z.string().trim().max(120, 'El código de barras no puede exceder 120 caracteres.'),
  verification_code: z
    .string()
    .trim()
    .max(120, 'El código de verificación no puede exceder 120 caracteres.')
});

export type LocationFieldErrors = Partial<Record<keyof LocationDraft, string>>;

export function validateLocationDraft(
  draft: LocationDraft
):
  { success: true; data: LocationMutationInput } | { success: false; errors: LocationFieldErrors } {
  const parsed = locationDraftSchema.safeParse(draft);
  if (!parsed.success) {
    const errors: LocationFieldErrors = {};
    for (const issue of parsed.error.issues) {
      const key = issue.path[0] as keyof LocationDraft | undefined;
      if (key && !errors[key]) errors[key] = issue.message;
    }
    return { success: false, errors };
  }
  const value = parsed.data;
  return {
    success: true,
    data: {
      area: value.area || null,
      aisle: value.aisle,
      rack: value.rack,
      level: value.level,
      position: value.position,
      capacity: Number(value.capacity),
      notes: value.notes || null,
      location_type: value.location_type,
      lifecycle_status: value.lifecycle_status,
      pick_sequence: value.pick_sequence === '' ? null : Number(value.pick_sequence),
      putaway_sequence: value.putaway_sequence === '' ? null : Number(value.putaway_sequence),
      external_id: value.external_id || null,
      barcode: value.barcode || null,
      verification_code: value.verification_code || null
    }
  };
}

export function axisSize(axis: LocationBatchAxis): number {
  if (axis.values?.length) {
    const values = axis.values.map((value) => value.normalize('NFKC').trim().toUpperCase());
    if (values.some((value) => !value) || new Set(values).size !== values.length) return 0;
    return values.length;
  }
  const start = axis.start?.normalize('NFKC').trim().toUpperCase() ?? '';
  const end = axis.end?.normalize('NFKC').trim().toUpperCase() ?? '';
  const step = axis.step ?? 1;
  if (!start || !end) return 0;
  if (!Number.isInteger(step) || step < 1) return 0;

  const ambiguousNumber = /^[+-]?(?:\d+\.\d*|\d*\.\d+|\d+[Ee][+-]?\d+)$/;
  if (ambiguousNumber.test(start) || ambiguousNumber.test(end)) return 0;

  const prefixedNumber = /^(.*?)(\d+)$/u;
  const startMatch = prefixedNumber.exec(start);
  const endMatch = prefixedNumber.exec(end);
  if (startMatch && endMatch && startMatch[1] === endMatch[1]) {
    const first = Number(startMatch[2]);
    const last = Number(endMatch[2]);
    if (!Number.isSafeInteger(first) || !Number.isSafeInteger(last) || last < first) return 0;
    return Math.floor((last - first) / step) + 1;
  }
  if (/^[A-Za-z]$/.test(start) && /^[A-Za-z]$/.test(end)) {
    const first = start.toUpperCase().charCodeAt(0);
    const last = end.toUpperCase().charCodeAt(0);
    if (last < first) return 0;
    return Math.floor((last - first) / step) + 1;
  }
  return start.localeCompare(end, 'es', { numeric: true }) === 0 ? 1 : 0;
}

export function batchCardinality(axes: LocationBatchAxis[], limit = 50_000): number {
  if (axes.length === 0) return 0;
  let total = 1;
  for (const axis of axes) {
    const size = axisSize(axis);
    if (size === 0) return 0;
    total *= size;
    if (total > limit) return total;
  }
  return total;
}

export function createIdempotencyKey(prefix: string): string {
  const random =
    globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${random}`;
}
