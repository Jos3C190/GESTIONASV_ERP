export type TrackingViewCount = 1 | 2 | 3 | 4;

export function initialAssignments(keys: string[], preferred: string | null): (string | null)[] {
  const unique = [...new Set(keys)];
  const ordered =
    preferred && unique.includes(preferred)
      ? [preferred, ...unique.filter((key) => key !== preferred)]
      : unique;
  return Array.from({ length: 4 }, (_, index) => ordered[index] ?? null);
}

/** Never put the same vehicle in two panes or retain an out-of-scope unit. */
export function reconcileAssignments(
  assignments: (string | null)[],
  keys: string[]
): (string | null)[] {
  const available = new Set(keys);
  const seen = new Set<string>();
  return Array.from({ length: 4 }, (_, index) => {
    const key = assignments[index];
    if (!key || !available.has(key) || seen.has(key)) return null;
    seen.add(key);
    return key;
  });
}

export function assignPane(
  assignments: (string | null)[],
  index: number,
  key: string | null,
  available: string[],
  visibleCount = 4
): (string | null)[] {
  if (
    index < 0 ||
    index >= 4 ||
    (key &&
      (!available.includes(key) ||
        assignments.some((value, i) => i !== index && i < visibleCount && value === key)))
  )
    return assignments;
  return Array.from({ length: 4 }, (_, i) =>
    i === index ? key : key && assignments[i] === key ? null : (assignments[i] ?? null)
  );
}
