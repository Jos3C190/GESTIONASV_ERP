import type { OrderStatus, QuotationStatus, Sale, SalesQuotation } from '#lib/types/sales.ts';

export const STATUS_LABELS: Record<QuotationStatus, string> = {
  draft: 'Borrador',
  pending_authorization: 'Por autorizar',
  issued: 'Emitida',
  accepted: 'Aceptada',
  rejected: 'Rechazada',
  cancelled: 'Cancelada'
};

const STATUS_BADGES: Record<QuotationStatus | 'expired', string> = {
  draft: 'bg-surface-muted text-foreground-muted',
  pending_authorization: 'bg-warning/10 text-warning',
  issued: 'bg-primary/10 text-primary',
  accepted: 'bg-success/10 text-success',
  rejected: 'bg-danger/10 text-danger',
  cancelled: 'bg-danger/10 text-danger',
  expired: 'bg-warning/10 text-warning'
};

/** Opciones del filtro de la lista: «Vencida» es una emitida cuya vigencia pasó. */
export const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'Todos' },
  { value: 'draft', label: 'Borrador' },
  { value: 'pending_authorization', label: 'Por autorizar' },
  { value: 'issued', label: 'Emitida vigente' },
  { value: 'expired', label: 'Vencida' },
  { value: 'accepted', label: 'Aceptada' },
  { value: 'rejected', label: 'Rechazada' },
  { value: 'cancelled', label: 'Cancelada' }
];

export const DOCUMENT_LABELS: Record<'01' | '03', string> = {
  '01': 'Factura',
  '03': 'Crédito fiscal'
};

export const SOURCE_LABELS: Record<'none' | 'customer' | 'volume', string> = {
  none: 'Sin descuento sugerido',
  customer: 'Descuento del cliente',
  volume: 'Descuento por volumen'
};

export const TREATMENT_LABELS: Record<'taxed' | 'exempt' | 'not_subject', string> = {
  taxed: 'Gravado',
  exempt: 'Exento',
  not_subject: 'No sujeto'
};

export function statusLabel(quote: Pick<SalesQuotation, 'status' | 'expired'>): string {
  return quote.expired ? 'Vencida' : STATUS_LABELS[quote.status];
}

export function statusBadge(quote: Pick<SalesQuotation, 'status' | 'expired'>): string {
  return STATUS_BADGES[quote.expired ? 'expired' : quote.status];
}

const MONEY = new Intl.NumberFormat('es-SV', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
});

const UNIT_PRICE = new Intl.NumberFormat('es-SV', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4
});

/** Monto del documento: $1,250.00. */
export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return MONEY.format(Number(value));
}

/** Precio unitario con hasta 4 decimales: $1.13, $0.8850. */
export function formatUnitPrice(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return UNIT_PRICE.format(Number(value));
}

export function formatPercent(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return `${Number(value).toFixed(2)} %`;
}

/** Cantidad sin ceros sobrantes: «2», «1.5». */
export function formatQuantity(value: string): string {
  const number = Number(value);
  return Number.isInteger(number) ? String(number) : String(Number(number.toFixed(6)));
}

/** `YYYY-MM-DD` (o fecha y hora ISO) a `DD/MM/YYYY`. */
export function formatDay(value: string | null | undefined): string {
  if (!value) return '—';
  const day =
    value.length > 10
      ? new Intl.DateTimeFormat('en-CA', {
          timeZone: 'America/El_Salvador',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit'
        }).format(new Date(value))
      : value;
  const [year, month, date] = day.split('-');
  return `${date}/${month}/${year}`;
}

// --- Pedido (V2e) ---------------------------------------------------------------------------

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  draft: 'Borrador',
  pending_authorization: 'Por autorizar',
  confirmed: 'Confirmado',
  cancelled: 'Cancelado'
};

export const ORDER_STATUS_BADGES: Record<OrderStatus, string> = {
  draft: 'bg-surface-muted text-foreground-muted',
  pending_authorization: 'bg-warning/10 text-warning',
  confirmed: 'bg-success/10 text-success',
  cancelled: 'bg-danger/10 text-danger'
};

export const ORDER_STATUS_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'Todos' },
  { value: 'draft', label: 'Borrador' },
  { value: 'pending_authorization', label: 'Por autorizar' },
  { value: 'confirmed', label: 'Confirmado' },
  { value: 'cancelled', label: 'Cancelado' }
];

export const DELIVERY_PROGRESS_LABELS: Record<Sale['delivery_progress'], string> = {
  pending: 'Pendiente de entrega',
  partial: 'Entrega parcial',
  complete: 'Entregado'
};

export const DELIVERY_MODE_LABELS: Record<Sale['delivery_mode'], string> = {
  pickup: 'Retiro en sucursal',
  delivery: 'Entrega a domicilio'
};

export function paymentLabel(order: Pick<Sale, 'payment_terms' | 'credit_days'>): string {
  return order.payment_terms === 'credit' ? `Crédito a ${order.credit_days} días` : 'Contado';
}
