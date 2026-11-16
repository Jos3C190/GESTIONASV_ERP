/** Clasificación fiscal de productos y unidades (API `/products/{id}/fiscal`, `/fiscal/units`). */

export type TaxTreatment = 'taxed' | 'exempt' | 'not_subject';
/** CAT-011: 1 bienes, 2 servicios, 3 ambos. */
export type DteItemType = '1' | '2' | '3';

export interface CatalogEntry {
  code: string;
  name: string;
}

export interface FiscalOptions {
  taxes: CatalogEntry[];
  units: CatalogEntry[];
}

export interface UnitFiscal {
  unit_id: number;
  code: string;
  name: string;
  symbol: string;
  is_enabled: boolean;
  hacienda_unit_code: string | null;
  suggested_code: string;
  effective_code: string;
  hacienda_unit_name: string | null;
}

export interface ProductFiscal {
  product_id: number;
  product_uuid: string;
  sku: string;
  name: string;
  product_kind: string;
  can_sell: boolean;
  tax_treatment: TaxTreatment;
  dte_item_type: DteItemType | null;
  effective_item_type: DteItemType;
  additional_taxes: CatalogEntry[];
  sale_unit: UnitFiscal | null;
  billing_issues: string[];
}

export interface ProductFiscalInput {
  tax_treatment: TaxTreatment;
  dte_item_type: DteItemType | null;
  additional_tax_codes: string[];
}
