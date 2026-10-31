/** Remove a duplicated trailing symbol from persisted or catalog unit labels. */
export function formatUnitLabel(value: string | null | undefined): string {
  const label = value?.trim();
  if (!label) return 'unidad base';

  return label.replace(/(\s*)(\(([^()]*)\))\s*\(\3\)$/u, '$1$2');
}
