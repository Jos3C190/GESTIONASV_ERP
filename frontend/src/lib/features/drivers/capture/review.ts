import type { LicenseIssue, LicenseValues } from '../api';

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

export const FIELD_LABELS: Record<keyof LicenseValues, { label: string; hint?: string }> = {
  license_class: { label: 'Clase', hint: 'Como aparece: D LIVIANA' },
  expires: { label: 'Vence', hint: 'MM-AAAA' },
  number: { label: 'Número de licencia' },
  surnames: { label: 'Apellidos' },
  given_names: { label: 'Nombres' },
  dui: { label: 'DUI', hint: '########-#' },
  issued: { label: 'Expedición', hint: 'DD.MM.AAAA' },
  birth: { label: 'Nacimiento', hint: 'DD.MM.AAAA' },
  control_number: { label: 'Número de control' }
};

/**
 * A result that arrives late only fills what the user has not touched: what a
 * person typed always wins over what the model read.
 */
export function mergeExtracted(
  current: LicenseValues,
  extracted: LicenseValues,
  touched: ReadonlySet<keyof LicenseValues>
): LicenseValues {
  const merged = { ...current };
  for (const key of Object.keys(EMPTY_VALUES) as (keyof LicenseValues)[]) {
    if (!touched.has(key) && extracted[key] !== null) merged[key] = extracted[key];
  }
  return merged;
}

export function issuesFor(issues: LicenseIssue[], field: keyof LicenseValues): LicenseIssue[] {
  return issues.filter((issue) => issue.field === field);
}

export const isWaiting = (status: string): boolean =>
  status === 'pending' || status === 'processing';

export function warningCodes(issues: LicenseIssue[]): string[] {
  return issues.filter((issue) => issue.severity === 'warning').map((issue) => issue.code);
}
