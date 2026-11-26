export interface SalesUnit {
  unit_id: number;
  name: string;
  factor: string;
  packaging_definition_id: string | null;
  packaging_version: number | null;
}

export interface SalesCatalogItem {
  product_id: number;
  variant_id: string | null;
  inventory_item_id: string;
  sku: string;
  name: string;
  base_unit_id: number;
  base_unit_name: string;
  units: SalesUnit[];
}

export type QuotationStatus =
  'draft' | 'pending_authorization' | 'issued' | 'accepted' | 'rejected' | 'cancelled';

export interface AuthorizationReason {
  code:
    | 'discount_above_limit'
    | 'below_cost'
    | 'global_discount_above_limit'
    | 'credit_limit_exceeded'
    | 'customer_overdue'
    | 'customer_blocked';
  message: string;
}

export interface SalesQuotationLine {
  id: string | null;
  line_number: number;
  product_id: number;
  variant_id: string | null;
  inventory_item_id: string;
  product_sku: string;
  product_name: string;
  unit_id: number;
  unit_name: string;
  base_unit_id: number;
  base_unit_name: string;
  unit_factor: string;
  quantity: string;
  quantity_base: string;
  price_list_id: string | null;
  list_price: string | null;
  price_overridden: boolean;
  unit_price: string;
  discount_percent: string;
  suggested_discount_percent: string;
  suggested_discount_source: 'none' | 'customer' | 'volume' | 'promotion';
  tax_treatment: 'taxed' | 'exempt' | 'not_subject';
  item_type: '1' | '2' | '3';
  document_unit_price: string;
  discount_amount: string;
  not_subject: string;
  exempt: string;
  taxed: string;
  vat_item: string | null;
  line_total: string;
  /** Solo llega a quien puede ver costos o autorizar descuentos. */
  cost: string | null;
  margin_percent: string | null;
  authorization_reasons: AuthorizationReason[];
}

export interface SalesQuotation {
  id: string;
  company_id: string;
  branch_id: string;
  customer_id: string;
  customer_code: string;
  customer_name: string;
  code: string;
  quotation_date: string;
  valid_until: string;
  document_type: '01' | '03';
  price_list_id: string | null;
  price_list_name: string | null;
  prices_include_vat: boolean;
  global_discount_percent: string;
  status: QuotationStatus;
  /** Emitida con la vigencia vencida. */
  expired: boolean;
  version: number;
  notes: string | null;
  total_not_subject: string;
  total_exempt: string;
  total_taxed: string;
  subtotal_sales: string;
  total_discount: string;
  subtotal: string;
  vat: string;
  vat_perceived: string;
  vat_withheld: string;
  total: string;
  total_in_words: string;
  requires_authorization: boolean;
  authorization_reasons: AuthorizationReason[];
  costs_visible: boolean;
  created_by_id: string;
  created_by_name: string | null;
  issued_by_name: string | null;
  issued_at: string | null;
  authorized_by_name: string | null;
  authorized_at: string | null;
  authorization_note: string | null;
  customer_response_by_name: string | null;
  customer_response_at: string | null;
  rejection_reason: string | null;
  cancelled_by_name: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  sale_id: string | null;
  sale_code: string | null;
  lines: SalesQuotationLine[];
  created_at: string | null;
  updated_at: string | null;
}

export interface QuotationLineInput {
  product_id: number;
  variant_id: string | null;
  unit_id: number;
  quantity: string;
  /** Vacío: se aplica el descuento sugerido. */
  discount_percent?: string | null;
  /** Precio escrito a mano; exige permiso para cambiar precios. */
  manual_price?: string | null;
}

export interface QuotationDraftInput {
  branch_id: string;
  customer_id: string;
  document_type?: '01' | '03' | null;
  valid_until?: string | null;
  global_discount_percent: string;
  notes: string | null;
  lines: QuotationLineInput[];
}

export interface QuotationSettings {
  quotation_validity_days: number;
}

export type OrderStatus = 'draft' | 'pending_authorization' | 'confirmed' | 'cancelled';

/** Línea del pedido: la de la cotización más lo entregado y el disponible para vender. */
export interface SalesLine extends Omit<SalesQuotationLine, 'id'> {
  id: string;
  source_quotation_line_id: string | null;
  quantity_delivered_base: string;
  quantity_pending_base: string;
  /** Disponible en la sucursal sin contar este pedido (solo en borrador o por autorizar). */
  available_base: string | null;
}

/** Pedido de venta (V2e). Se llama `Sale` porque reemplaza a la venta B06. */
export interface Sale {
  id: string;
  company_id: string;
  branch_id: string;
  customer_id: string;
  customer_code: string;
  customer_name: string;
  quotation_id: string | null;
  quotation_code: string | null;
  code: string;
  document_type: '01' | '03';
  price_list_id: string | null;
  price_list_name: string | null;
  prices_include_vat: boolean;
  global_discount_percent: string;
  status: OrderStatus;
  delivery_progress: 'pending' | 'partial' | 'complete';
  version: number;
  notes: string | null;
  total_not_subject: string;
  total_exempt: string;
  total_taxed: string;
  subtotal_sales: string;
  total_discount: string;
  subtotal: string;
  vat: string;
  vat_perceived: string;
  vat_withheld: string;
  total: string;
  total_in_words: string;
  requires_authorization: boolean;
  authorization_reasons: AuthorizationReason[];
  costs_visible: boolean;
  promised_date: string;
  delivery_mode: 'pickup' | 'delivery';
  delivery_address_id: string | null;
  delivery_address_text: string | null;
  payment_terms: 'cash' | 'credit';
  credit_days: number;
  created_by_id: string;
  created_by_name: string | null;
  confirmed_by_name: string | null;
  confirmed_at: string | null;
  authorized_by_name: string | null;
  authorized_at: string | null;
  authorization_note: string | null;
  cancelled_by_name: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  lines: SalesLine[];
  /** Salida automática al confirmar (solo en la respuesta de confirmar o autorizar). */
  auto_delivery?: AutoDelivery | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AutoDelivery {
  delivery_id: string | null;
  delivery_code: string | null;
  pending_products: string[];
  message: string | null;
}

export interface OrderSettings {
  auto_deliver_on_confirm: boolean;
}

export interface OrderDelivery {
  promised_date: string;
  delivery_mode: 'pickup' | 'delivery';
  delivery_address_id: string | null;
}

export type OrderDraftInput = Omit<QuotationDraftInput, 'valid_until'> & OrderDelivery;

export interface SalesDeliveryStockUnit {
  handling_unit_id: string;
  code: string;
  inventory_item_id: string;
  quantity_base: string;
  base_unit_name: string;
  lot_code: string | null;
  expiry_date: string | null;
  warehouse_id: string;
  warehouse_name: string;
  location_id: string;
  location_code: string;
  packaging_snapshot: Record<string, unknown> | null;
}

export interface SalesDeliveryStockLine {
  sale_line_id: string;
  product_sku: string;
  product_name: string;
  unit_name: string;
  base_unit_name: string;
  quantity_pending_base: string;
  units: SalesDeliveryStockUnit[];
}

export interface SalesDeliveryAllocation {
  id: string;
  handling_unit_id: string;
  handling_unit_code: string | null;
  warehouse_id: string;
  location_id: string;
  inventory_lot_detail_id: string | null;
  lot_code: string | null;
  expiry_date: string | null;
  quantity_base: string;
  movement_id: string | null;
  movement_line_id: string | null;
  valuation_entry_id: string | null;
}

export interface SalesDeliveryLine {
  id: string;
  sale_line_id: string;
  product_sku: string;
  product_name: string;
  unit_name: string;
  base_unit_name: string;
  quantity_base: string;
  quantity_in_sale_unit: string;
  unit_factor: string;
  allocations: SalesDeliveryAllocation[];
}

export interface SalesDelivery {
  id: string;
  company_id: string;
  branch_id: string;
  sale_id: string;
  code: string;
  status: 'draft' | 'confirmed' | 'cancelled';
  version: number;
  notes: string | null;
  created_by_id: string;
  confirmed_by_id: string | null;
  confirmed_at: string | null;
  cancelled_by_id: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
  lines: SalesDeliveryLine[];
}

export type SalesReturnStatus =
  'draft' | 'received' | 'under_review' | 'accepted' | 'rejected' | 'mixed' | 'cancelled';
export type SalesReturnCondition = 'resalable' | 'damaged' | 'wrong_item' | 'other';

export interface SalesReturnEvent {
  id: string;
  decision: 'accepted' | 'rejected';
  quantity_base: string;
  condition: SalesReturnCondition;
  reason: string;
  destination_location_id: string | null;
  movement_id: string | null;
  movement_line_id: string | null;
  valuation_entry_id: string | null;
  actor_id: string;
  created_at: string;
}

export interface SalesReturnLine {
  id: string;
  delivery_id: string;
  delivery_code: string;
  delivery_allocation_id: string;
  source_handling_unit_id: string;
  inventory_item_id: string;
  product_sku: string;
  product_name: string;
  unit_name: string;
  base_unit_name: string;
  lot_code: string | null;
  quantity_received_base: string;
  quantity_accepted_base: string;
  quantity_rejected_base: string;
  quantity_pending_base: string;
  quantity_returnable_base: string;
  reason: string;
  declared_condition: SalesReturnCondition;
  events: SalesReturnEvent[];
}

export interface SalesReturnEvidence {
  document_id: string;
  title: string;
  file_name: string;
}

export interface SalesReturn {
  id: string;
  company_id: string;
  branch_id: string;
  sale_id: string;
  code: string;
  status: SalesReturnStatus;
  notes: string | null;
  created_by_id: string;
  received_by_id: string | null;
  received_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
  evidence: SalesReturnEvidence[];
  lines: SalesReturnLine[];
}

export interface SalesReturnableAllocation {
  delivery_id: string;
  delivery_code: string;
  delivery_line_id: string;
  delivery_allocation_id: string;
  delivery_date: string;
  handling_unit_code: string | null;
  inventory_item_id: string;
  product_sku: string;
  product_name: string;
  unit_name: string;
  base_unit_name: string;
  lot_code: string | null;
  quantity_delivered_base: string;
  quantity_returned_base: string;
  quantity_reserved_base: string;
  quantity_returnable_base: string;
}

export interface SalesFilters {
  branch_id?: string | null;
  customer_id?: string;
  status?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  size?: number;
}

export interface SalesPage<T> {
  items: T[];
  meta: { page: number; size: number; total: number; pages: number };
}
