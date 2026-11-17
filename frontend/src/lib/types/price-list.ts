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
  target_margin_percent: string | null;
}

export interface PriceListInput {
  code: string;
  name: string;
  description: string | null;
  prices_include_vat: boolean;
  is_default: boolean;
  is_active: boolean;
  target_margin_percent: string | null;
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
  /** Solo llegan con el permiso `sales_costs:read`. */
  cost?: string | null;
  margin_percent?: string | null;
  target_margin_percent?: string | null;
  suggested_price?: string | null;
  below_cost?: boolean;
  below_target?: boolean;
}

export interface PriceInput {
  product_id: number;
  variant_id: string | null;
  unit_id: number;
  branch_id: string | null;
  price: string;
  valid_from: string | null;
}

export interface Category {
  id: number;
  name: string;
}

export interface CategoryMargin {
  category_id: number;
  target_margin_percent: string;
}

export interface VolumeDiscount {
  id: string;
  price_list_id: string;
  product_id: number;
  variant_id: string | null;
  unit_id: number;
  min_quantity: string;
  discount_percent: string;
  valid_from: string;
  valid_to: string | null;
  status: PriceStatus;
}

export interface VolumeDiscountInput {
  product_id: number;
  variant_id: string | null;
  unit_id: number;
  min_quantity: string;
  discount_percent: string;
  valid_from: string | null;
}

export interface DiscountPolicy {
  max_line_discount_percent: string;
  max_global_discount_percent: string;
  can_sell_below_cost: boolean;
}

export interface RolePolicy extends DiscountPolicy {
  role_id: string;
  role_name: string;
  configured: boolean;
  updated_at: string | null;
}
