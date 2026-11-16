import { apiFetch } from '#lib/api/client.ts';
import type {
  FiscalOptions,
  ProductFiscal,
  ProductFiscalInput,
  UnitFiscal
} from '#lib/types/product-fiscal.ts';

export const productFiscalApi = {
  options() {
    return apiFetch<FiscalOptions>('/product-fiscal/options');
  },

  get(productId: number) {
    return apiFetch<ProductFiscal>(`/products/${productId}/fiscal`);
  },

  update(productId: number, payload: ProductFiscalInput) {
    return apiFetch<ProductFiscal>(`/products/${productId}/fiscal`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  listUnits() {
    return apiFetch<UnitFiscal[]>('/fiscal/units');
  },

  updateUnit(unitId: number, hacienda_unit_code: string | null) {
    return apiFetch<UnitFiscal>(`/fiscal/units/${unitId}`, {
      method: 'PUT',
      body: JSON.stringify({ hacienda_unit_code })
    });
  }
};

export const TAX_TREATMENT_LABELS = {
  taxed: 'Gravado (IVA 13 %)',
  exempt: 'Exento',
  not_subject: 'No sujeto'
} as const;

export const ITEM_TYPE_LABELS = {
  '1': 'Bienes',
  '2': 'Servicios',
  '3': 'Bienes y servicios'
} as const;
