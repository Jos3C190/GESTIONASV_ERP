import type { LicenseIssue, LicenseValues } from '../api';

type FieldKey = keyof LicenseValues;

export const EMPTY_VALUES: LicenseValues = {
  license_class: null,
  expires: null,
  number: null,
  surnames: null,
  given_names: null,
  dui: null,
  issued: null,
  birth: null,
  control_number: null
};

export const FIELD_LABELS: Record<FieldKey, { label: string; hint?: string }> = {
  license_class: { label: 'Clase', hint: 'Como aparece, por ejemplo D LIVIANA' },
  expires: { label: 'Vence', hint: 'MM-AAAA' },
  number: { label: 'Número de licencia' },
  surnames: { label: 'Apellidos' },
  given_names: { label: 'Nombres' },
  dui: { label: 'DUI', hint: '########-#' },
  issued: { label: 'Expedición', hint: 'DD.MM.AAAA' },
  birth: { label: 'Nacimiento', hint: 'DD.MM.AAAA' },
  control_number: { label: 'Número de control' }
};

/** Grouped by what the person checks together, not by the side each value is printed on. */
export const FIELD_GROUPS: { title: string; fields: FieldKey[] }[] = [
  { title: 'Datos del titular', fields: ['surnames', 'given_names', 'dui', 'birth'] },
  {
    title: 'Datos de la licencia',
    fields: ['license_class', 'number', 'expires', 'issued', 'control_number']
  }
];

/**
 * A result that arrives late only fills what the user has not touched: what a
 * person typed always wins over what the model read.
 */
export function mergeExtracted(
  current: LicenseValues,
  extracted: LicenseValues,
  touched: ReadonlySet<FieldKey>
): LicenseValues {
  const merged = { ...current };
  for (const key of Object.keys(EMPTY_VALUES) as FieldKey[]) {
    if (!touched.has(key) && extracted[key] !== null) merged[key] = extracted[key];
  }
  return merged;
}

export function issuesFor(issues: LicenseIssue[], field: FieldKey): LicenseIssue[] {
  return issues.filter((issue) => issue.field === field);
}

export const isWaiting = (status: string): boolean =>
  status === 'pending' || status === 'processing';

export function warningCodes(issues: LicenseIssue[]): string[] {
  return issues.filter((issue) => issue.severity === 'warning').map((issue) => issue.code);
}

/** Fields with something to review, in the order they appear on the form. */
export function fieldsToReview(issues: LicenseIssue[]): FieldKey[] {
  const flagged = new Set(issues.map((issue) => issue.field));
  return FIELD_GROUPS.flatMap((group) => group.fields).filter((field) => flagged.has(field));
}

/** Says what stands between the user and confirming; a disabled button alone explains nothing. */
export function confirmBlocker(state: {
  photosReady: boolean;
  issues: LicenseIssue[];
  acknowledged: boolean;
  canOverride: boolean;
  overrideReason: string;
}): string | null {
  const has = (severity: LicenseIssue['severity']) =>
    state.issues.some((issue) => issue.severity === severity);
  if (!state.photosReady) return 'Faltan fotos de la licencia.';
  if (has('error')) return 'Corrige los campos marcados.';
  if (has('mismatch')) {
    if (!state.canOverride) return 'Los datos no coinciden con el empleado.';
    if (state.overrideReason.trim().length < 3) return 'Indica el motivo de la excepción.';
  }
  if (has('warning') && !state.acknowledged) return 'Marca que revisaste los avisos.';
  return null;
}
