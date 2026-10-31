import { apiFetch } from '$lib/api/client';

export interface ValuationSetting {
  company_id: string;
  currency: string;
  opened_at: string;
  opened_by: string;
  opening_reference: string;
}
export interface ValuationItem {
  inventory_item_id: string;
  product_name: string;
  sku: string | null;
  base_unit: string;
}
export interface ValuationBalance {
  inventory_item_id: string;
  quantity_base: string;
  inventory_value: string;
  average_unit_cost: string;
  updated_at: string;
}
export interface ValuationOverview {
  setting: ValuationSetting | null;
  snapshot_fingerprint: string;
  physical_stock: {
    inventory_item_id: string;
    quantity_base: string;
    stock_status: string;
    warehouse_id: string;
    location_id: string;
    lot_code: string | null;
    expiry_date: string | null;
  }[];
  items: ValuationItem[];
  balances: ValuationBalance[];
}
export interface ValuationEntry {
  id: string;
  sequence: number;
  kind: string;
  quantity_base: string;
  source_value: string;
  source_reference: string;
  posted_at: string;
  inventory_delta: string;
  balance_quantity: string;
  balance_value: string;
  average_unit_cost: string;
  original_entry_id: string | null;
  cost_breakdown: Record<string, string>[];
}
export interface ValuationOpening {
  currency: string;
  reference: string;
  snapshot_fingerprint: string;
  approved: true;
  lines: {
    inventory_item_id: string;
    quantity_base: string;
    total_cost: string;
    cost_reference: string;
  }[];
}
export const valuationApi = {
  overview: () => apiFetch<ValuationOverview>('/inventory/valuation'),
  open: (body: ValuationOpening) =>
    apiFetch<ValuationSetting>('/inventory/valuation/opening', {
      method: 'POST',
      body: JSON.stringify(body)
    }),
  ledger: (itemId: string, skip = 0) =>
    apiFetch<ValuationEntry[]>(`/inventory/valuation/items/${itemId}/ledger?skip=${skip}&limit=50`)
};

// Keep the approved quantities and monetary input exact. Number is display-only.
export function decimalMicros(value: string): bigint {
  const normalized = value.trim().replace(',', '.');
  if (!/^\d+(\.\d{1,6})?$/.test(normalized))
    throw new Error(
      'Ingresa un número positivo o cero, con hasta seis decimales y sin separadores de miles.'
    );
  const [whole, fraction = ''] = normalized.split('.');
  if (!whole || whole.replace(/^0+/, '').length > 18)
    throw new Error('El importe admite hasta 18 dígitos enteros y seis decimales.');
  return BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, '0'));
}
export function fromMicros(value: bigint): string {
  return `${value / 1000000n}.${(value % 1000000n).toString().padStart(6, '0')}`;
}
export function openingQuantities(data: ValuationOverview): Map<string, string> {
  const totals = new Map<string, bigint>();
  for (const row of data.physical_stock)
    totals.set(
      row.inventory_item_id,
      (totals.get(row.inventory_item_id) ?? 0n) + decimalMicros(row.quantity_base)
    );
  return new Map([...totals].map(([id, quantity]) => [id, fromMicros(quantity)]));
}
export function displayDecimal(value: string, maximumFractionDigits = 6): string {
  const match = /^(-?)(\d+)(?:\.(\d{1,6}))?$/.exec(value);
  if (!match) return '—';
  const digits = Math.max(0, Math.min(6, Math.trunc(maximumFractionDigits)));
  const micros = BigInt(match[2]!) * 1000000n + BigInt((match[3] ?? '').padEnd(6, '0'));
  const divisor = 10n ** BigInt(6 - digits);
  const rounded = (micros + divisor / 2n) / divisor;
  const scale = 10n ** BigInt(digits);
  const whole = new Intl.NumberFormat('es-SV', { maximumFractionDigits: 0 }).format(
    rounded / scale
  );
  const fraction = (rounded % scale).toString().padStart(digits, '0').replace(/0+$/, '');
  return `${match[1] && rounded !== 0n ? '-' : ''}${whole}${fraction ? `.${fraction}` : ''}`;
}
export const valuationKind: Record<string, string> = {
  opening: 'Saldo inicial',
  receipt: 'Recepción',
  issue: 'Salida',
  supplier_return: 'Devolución a proveedor',
  customer_return: 'Devolución de cliente',
  adjustment_in: 'Ajuste de entrada',
  adjustment_out: 'Ajuste de salida',
  cost_adjustment: 'Aplicación de retaceo',
  supplier_credit: 'Crédito del proveedor'
};
