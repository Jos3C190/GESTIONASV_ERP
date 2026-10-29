import { apiFetch, type Page } from '$lib/api/client';
import { handlingUnit, type RawHandlingUnit } from './services';
import type { HandlingUnit } from './types';

export interface PreparationUnit extends HandlingUnit {
  inventory_lot_detail_id: string;
  label_confirmed: boolean;
  phase: 'measure' | 'label' | 'place';
}
type RawUnit = RawHandlingUnit &
  Pick<PreparationUnit, 'inventory_lot_detail_id' | 'label_confirmed' | 'phase'>;
export interface PreparationCommand {
  idempotency_key: string;
  quantity_base: string;
  unit_scan: string;
  location_scan?: string;
}
export interface PreparationResult {
  action: 'split' | 'place';
  handling_unit_id: string;
  prepared_unit_id: string;
  quantity_base: string;
  movement_id: string | null;
}
export const preparationApi = {
  async list(warehouseId: string, page = 1, search = ''): Promise<Page<PreparationUnit>> {
    const query = new URLSearchParams({
      warehouse_id: warehouseId,
      page: String(page),
      size: '10',
      search
    });
    const result = await apiFetch<Page<RawUnit>>(`/inventory/preparation?${query}`);
    return { ...result, items: result.items.map((row) => ({ ...row, ...handlingUnit(row) })) };
  },
  execute(unitId: string, action: 'split' | 'place', command: PreparationCommand) {
    return apiFetch<PreparationResult>(`/inventory/preparation/${unitId}/${action}`, {
      method: 'POST',
      body: JSON.stringify(command)
    });
  }
};

export function preparationQuantityIssue(value: string, available: number): string | null {
  const quantity = Number(value);
  if (!value.trim() || !Number.isFinite(quantity) || quantity <= 0 || quantity > available)
    return 'Indica una cantidad mayor que cero y hasta el total pendiente.';
  if (!/^\d+(\.\d{1,6})?$/.test(value.trim()))
    return 'Usa hasta seis decimales y un punto como separador.';
  return null;
}
