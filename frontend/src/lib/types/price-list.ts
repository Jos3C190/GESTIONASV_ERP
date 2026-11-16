/** Listas de precios de venta (API `/price-lists`). */

export type PriceStatus = 'scheduled' | 'current' | 'expired';

export interface PriceList {
  id: string;
  code: string;
  name: string;
  description: string | null;
  prices_include_vat: boolean;
  is_default: boolean;
  is_active: boolean;
  price_count: number;
  customer_count: number;
  updated_at: string;
}

export interface PriceListInput {
  code: string;
  name: string;
  description: string | null;
  prices_include_vat: boolean;
  is_default: boolean;
  is_active: boolean;
}

export interface SellableUnit {
  product_id: number;
  variant_id: string | null;
  sku: string;
  name: string;
  unit_id: number;
  unit_name: string;
  factor: string;
  is_base: boolean;
}

export interface PriceEntry {
  id: string;
  price_list_id: string;
  product_id: number;
  variant_id: string | null;
  unit_id: number;
  branch_id: string | null;
  branch_name: string | null;
  price: string;
  valid_from: string;
  valid_to: string | null;
  status: PriceStatus;
  created_by_name: string | null;
  created_at: string;
}

export interface ListedPrice {
  unit: SellableUnit;
  current: PriceEntry | null;
  next: PriceEntry | null;
  branch_overrides: number;
}

export interface PriceInput {
  product_id: number;
  variant_id: string | null;
  unit_id: number;
  branch_id: string | null;
  price: string;
  valid_from: string | null;
}
