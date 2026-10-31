export const adjudicationQuantityPattern = String.raw`[0-9]+(\.[0-9]{1,6})?`;

export function offerKey(lineId: string, offerId: string) {
  return `${lineId}:${offerId}`;
}

export function formatQuantity(value: string | null) {
  if (value === null) return 'No indicada';
  return new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(Number(value));
}

export function formatMoney(value: string, currency: string) {
  return `${new Intl.NumberFormat('es-SV', { minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(Number(value))} ${currency}`;
}

export function formatDate(value: string | null) {
  if (!value) return 'Sin fecha límite';
  const isDateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  return new Intl.DateTimeFormat('es-SV', {
    dateStyle: 'medium',
    timeZone: isDateOnly ? 'UTC' : 'America/El_Salvador'
  }).format(new Date(value));
}

export function statusLabel(status: string) {
  const labels: Record<string, string> = {
    received: 'Respuesta recibida',
    under_evaluation: 'En evaluación',
    selected: 'Seleccionada',
    rejected: 'Rechazada',
    expired: 'Vencida'
  };
  return labels[status] ?? status;
}
