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

const optionalPositive = (label: string) =>
  numericDraftValue(
    z
      .string()
      .trim()
      .refine((value) => value === '' || Number(value) > 0, {
        message: `${label} debe ser mayor que cero.`
      })
  );

export const locationDraftSchema = z
  .object({
    capacity_group_id: z.string().trim(),
    area: z.string().trim().max(64, 'El área no puede exceder 64 caracteres.'),
    aisle: coordinate('El pasillo'),
    rack: coordinate('El rack'),
    level: coordinate('El nivel'),
    position: coordinate('La posición'),
    certified_max_weight_kg: optionalPositive('El límite certificado de peso'),
    operational_max_weight_kg: optionalPositive('El límite operativo de peso'),
    certified_usable_volume_m3: optionalPositive('El volumen útil certificado'),
    operational_usable_volume_m3: optionalPositive('El volumen útil operativo'),
    usable_length_m: optionalPositive('El largo útil'),
    usable_width_m: optionalPositive('El ancho útil'),
    usable_height_m: optionalPositive('La altura útil'),
    capacity_profile: z.enum([
      'general_mixed',
      'rack',
      'bulk_floor',
      'cold',
      'oversize_manual',
      'transit'
    ]),
    capacity_enforcement_mode: z.enum(['disabled', 'observe', 'enforce']),
    storage_eligible: z.boolean(),
    notes: z.string().trim().max(4000, 'Las notas no pueden exceder 4,000 caracteres.'),
    location_type: z.string().trim().min(1, 'Seleccione un tipo de ubicación.'),
    lifecycle_status: z.string().trim().min(1, 'Seleccione un estado operativo.'),
    pick_sequence: numericDraftValue(
      z
        .string()
        .trim()
        .refine(
          (value) => value === '' || (Number.isInteger(Number(value)) && Number(value) >= 0),
          {
            message: 'La secuencia de picking debe ser un entero positivo.'
          }
        )
    ),
    putaway_sequence: numericDraftValue(
      z
        .string()
        .trim()
        .refine(
          (value) => value === '' || (Number.isInteger(Number(value)) && Number(value) >= 0),
          {
            message: 'La secuencia de acomodo debe ser un entero positivo.'
          }
        )
    ),
    external_id: z
      .string()
      .trim()
      .max(120, 'La referencia externa no puede exceder 120 caracteres.'),
    barcode: z.string().trim().max(120, 'El código de barras no puede exceder 120 caracteres.'),
    verification_code: z
      .string()
      .trim()
      .max(120, 'El código de verificación no puede exceder 120 caracteres.')
  })
  .superRefine((value, context) => {
    const certifiedWeight = Number(value.certified_max_weight_kg);
    const operationalWeight = Number(value.operational_max_weight_kg);
    const certifiedVolume = Number(value.certified_usable_volume_m3);
    const operationalVolume = Number(value.operational_usable_volume_m3);
    if (
      value.certified_max_weight_kg &&
      value.operational_max_weight_kg &&
      operationalWeight > certifiedWeight
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['operational_max_weight_kg'],
        message: 'El límite operativo no puede superar el certificado.'
      });
    }
    if (
      value.certified_usable_volume_m3 &&
      value.operational_usable_volume_m3 &&
      operationalVolume > certifiedVolume
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['operational_usable_volume_m3'],
        message: 'El límite operativo no puede superar el certificado.'
      });
    }
    if (!value.storage_eligible && value.capacity_enforcement_mode !== 'disabled') {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['capacity_enforcement_mode'],
        message: 'Las ubicaciones no elegibles deben mantener deshabilitado el control de límites.'
      });
    }
    if (value.capacity_enforcement_mode === 'enforce') {
      const required = [
        [
          'certified_max_weight_kg',
          value.certified_max_weight_kg,
          'Configure el límite certificado de peso para bloquear excesos.'
        ],
        [
          'operational_max_weight_kg',
          value.operational_max_weight_kg,
          'Configure el límite operativo de peso para bloquear excesos.'
        ],
        [
          'certified_usable_volume_m3',
          value.certified_usable_volume_m3,
          'Configure el volumen útil certificado para bloquear excesos.'
        ],
        [
          'operational_usable_volume_m3',
          value.operational_usable_volume_m3,
          'Configure el volumen útil operativo para bloquear excesos.'
        ]
      ] as const;
      for (const [path, present, message] of required) {
        if (!present) context.addIssue({ code: z.ZodIssueCode.custom, path: [path], message });
      }
    }
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
      capacity_group_id: value.capacity_group_id || null,
      area: value.area || null,
      aisle: value.aisle,
      rack: value.rack,
      level: value.level,
      position: value.position,
      certified_max_weight_kg: !value.certified_max_weight_kg
        ? null
        : Number(value.certified_max_weight_kg),
      operational_max_weight_kg: !value.operational_max_weight_kg
        ? null
        : Number(value.operational_max_weight_kg),
      certified_usable_volume_m3: !value.certified_usable_volume_m3
        ? null
        : Number(value.certified_usable_volume_m3),
      operational_usable_volume_m3: !value.operational_usable_volume_m3
        ? null
        : Number(value.operational_usable_volume_m3),
      capacity_profile: value.capacity_profile,
      capacity_enforcement_mode: value.capacity_enforcement_mode,
      storage_eligible: value.storage_eligible,
      usable_length_m: !value.usable_length_m ? null : Number(value.usable_length_m),
      usable_width_m: !value.usable_width_m ? null : Number(value.usable_width_m),
      usable_height_m: !value.usable_height_m ? null : Number(value.usable_height_m),
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
