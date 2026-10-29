export function movementTypeLabel(t: string): { label: string; color: string; bg: string } {
  const labels: Record<string, { label: string; color: string; bg: string }> = {
    inbound: { label: 'Entrada', color: 'text-success', bg: 'bg-success/10' },
    outbound: { label: 'Salida', color: 'text-foreground', bg: 'bg-primary/10' },
    transfer: { label: 'Transferencia', color: 'text-foreground', bg: 'bg-warning/10' },
    adjustment: {
      label: 'Ajuste',
      color: 'text-foreground-muted',
      bg: 'bg-surface-muted/60'
    },
    receipt: { label: 'Recepción', color: 'text-success', bg: 'bg-success/10' },
    putaway: { label: 'Liberación / acomodo', color: 'text-success', bg: 'bg-success/10' },
    pick: { label: 'Preparación', color: 'text-foreground', bg: 'bg-primary/10' },
    shipment: { label: 'Despacho', color: 'text-foreground', bg: 'bg-primary/10' },
    adjustment_in: {
      label: 'Ajuste de entrada',
      color: 'text-foreground-muted',
      bg: 'bg-surface-muted/60'
    },
    adjustment_out: {
      label: 'Ajuste de salida',
      color: 'text-foreground-muted',
      bg: 'bg-surface-muted/60'
    },
    reversal: { label: 'Reversión', color: 'text-foreground', bg: 'bg-danger/10' }
  };
  return (
    labels[t] ?? { label: 'Movimiento', color: 'text-foreground-muted', bg: 'bg-surface-muted/60' }
  );
}

export function movementIcon(t: string): string {
  if (['inbound', 'receipt', 'adjustment_in'].includes(t)) return '↓';
  if (['outbound', 'pick', 'shipment', 'adjustment_out'].includes(t)) return '↑';
  if (['transfer', 'putaway'].includes(t)) return '↔';
  return '⚙';
}

export function formatMovementDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('es-SV', {
        dateStyle: 'short',
        timeStyle: 'short',
        timeZone: 'America/El_Salvador'
      });
}

export function stockStatusLabel(status: string | null): string {
  const labels: Record<string, string> = {
    available: 'Disponible',
    quarantine: 'Cuarentena',
    blocked: 'Bloqueado',
    damaged: 'Dañado',
    in_transit: 'En tránsito'
  };
  return status ? (labels[status] ?? status) : '';
}

export function formatMovementQuantity(value: number | string): string {
  const quantity = Number(value);
  return Number.isFinite(quantity)
    ? quantity.toLocaleString('es-SV', { maximumFractionDigits: 6 })
    : String(value);
}

export function formatPhysicalMeasure(value: number | string | null, unit: string): string {
  if (value === null) return 'Pendiente de medición';
  const amount = Number(value);
  return Number.isFinite(amount)
    ? `${amount.toLocaleString('es-SV', { maximumFractionDigits: 3 })} ${unit}`
    : `${value} ${unit}`;
}
