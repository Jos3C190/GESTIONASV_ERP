import type {
  CaptureField,
  CaptureFieldGroup,
  CaptureIssue,
  CaptureRules,
  CaptureValues
} from './types';

export const ACKNOWLEDGE_BLOCKER = 'Marca que revisaste los avisos.';

export function emptyValues(fields: Record<string, CaptureField>): CaptureValues {
  return Object.fromEntries(Object.keys(fields).map((key) => [key, null]));
}

/**
 * A result that arrives late only fills what the user has not touched: what a
 * person typed always wins over what the model read.
 */
export function mergeExtracted<V extends CaptureValues>(
  current: V,
  extracted: V,
  touched: ReadonlySet<string>
): V {
  const merged: CaptureValues = { ...current };
  for (const key of Object.keys(extracted)) {
    const value = extracted[key];
    if (!touched.has(key) && value !== null && value !== undefined) merged[key] = value;
  }
  return merged as V;
}

export function issuesFor(issues: CaptureIssue[], field: string): CaptureIssue[] {
  return issues.filter((issue) => issue.field === field);
}

export const isWaiting = (status: string): boolean =>
  status === 'pending' || status === 'processing';

export function warningCodes(issues: CaptureIssue[]): string[] {
  return issues.filter((issue) => issue.severity === 'warning').map((issue) => issue.code);
}

/**
 * While the model reads, an empty field is not a mistake yet: marking it in red
 * would contradict the message saying the data is on its way.
 */
export function issuesToShow(
  issues: CaptureIssue[],
  values: CaptureValues,
  touched: ReadonlySet<string>,
  reading: boolean
): CaptureIssue[] {
  if (!reading) return issues;
  return issues.filter(
    (issue) => !(issue.severity === 'error' && !values[issue.field] && !touched.has(issue.field))
  );
}

/** Fields with something to review, in the order they appear on the form. */
export function fieldsToReview(issues: CaptureIssue[], groups: CaptureFieldGroup[]): string[] {
  const flagged = new Set(issues.map((issue) => issue.field));
  return groups.flatMap((group) => group.fields).filter((field) => flagged.has(field));
}

/**
 * What the model could not read on a photo it did process. That is a better sign of a
 * bad photo than any image metric, including the small reflections those metrics miss.
 */
export function unreadFields(
  values: CaptureValues,
  issues: CaptureIssue[],
  capture: { front: { extracted: boolean }; back: { extracted: boolean } },
  touched: ReadonlySet<string>,
  rules: Pick<CaptureRules, 'expected' | 'unreadableCodes'>
): string[] {
  const expected = [
    ...(capture.front.extracted ? rules.expected.front : []),
    ...(capture.back.extracted ? rules.expected.back : [])
  ];
  return expected.filter(
    (field) =>
      !touched.has(field) &&
      (!values[field] ||
        issues.some((issue) => issue.field === field && rules.unreadableCodes.has(issue.code)))
  );
}

/** Says what stands between the user and confirming; a disabled button alone explains nothing. */
export function confirmBlocker(
  state: {
    photosReady: boolean;
    issues: CaptureIssue[];
    acknowledged: boolean;
    canOverride: boolean;
    overrideReason: string;
  },
  rules: Pick<CaptureRules, 'missingPhotos' | 'mismatchBlocked' | 'blockingCodes'>
): string | null {
  const has = (severity: CaptureIssue['severity']) =>
    state.issues.some((issue) => issue.severity === severity);
  if (!state.photosReady) return rules.missingPhotos;
  const blocking = state.issues.find((issue) => rules.blockingCodes?.[issue.code]);
  if (blocking) return rules.blockingCodes?.[blocking.code] ?? null;
  if (has('error')) return 'Corrige los campos marcados.';
  if (has('mismatch')) {
    if (!state.canOverride) return rules.mismatchBlocked;
    if (state.overrideReason.trim().length < 3) return 'Indica el motivo de la excepción.';
  }
  if (has('warning') && !state.acknowledged) return ACKNOWLEDGE_BLOCKER;
  return null;
}
