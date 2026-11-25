/** Promoción de un producto en una sucursal (pedido del ingeniero, 24/11/2026). */

export type PromotionStatus = 'current' | 'scheduled' | 'expired' | 'ended';

export interface SalesPromotion {
  id: string;
  branch_id: string;
  branch_name: string | null;
  product_id: number;
  product_name: string | null;
  product_sku: string | null;
  discount_percent: string;
  valid_from: string;
  valid_to: string | null;
  notes: string | null;
  status: PromotionStatus;
}

export interface PromotionInput {
  branch_id: string;
  product_id: number;
  discount_percent: string;
  valid_from?: string | null;
  valid_to?: string | null;
  notes?: string | null;
}
