/** Cuentas por cobrar y recibos de cobro (V5a). */
export type PaymentMethod = 'cash' | 'card' | 'transfer' | 'check' | 'other';
export type AgingBucket = 'current' | '1_30' | '31_60' | '61_90' | 'over_90';

export interface CustomerRef {
  id: string;
  code: string;
  name: string;
  credit_days: number;
  credit_limit: string | null;
  email?: string | null;
  credit_blocked?: boolean;
  credit_block_reason?: string | null;
  credit_blocked_at?: string | null;
}

export interface CollectionNote {
  id: string;
  note: string;
  next_action_on: string | null;
  created_by: string;
  created_at: string;
}

/** Situación de crédito del cliente (V5b). */
export interface CreditStatus {
  customer: CustomerRef;
  credit_limit: string | null;
  open_balance: string;
  /** Pedidos a crédito confirmados sin facturar. */
  pending_orders: string;
  available: string | null;
  overdue_beyond_grace: string;
  grace_days: number;
  notes: CollectionNote[];
}

export interface CustomerSummary {
  customer: CustomerRef;
  balance: string;
  overdue: string;
  /** Saldo a favor: cobrado y no aplicado. */
  credit: string;
  aging: Record<AgingBucket, string>;
  oldest_due: string | null;
}

export interface WithholdingCertificate {
  certificate_number: string;
  issued_on: string;
  amount: string;
}

export interface AccountDocument {
  id: string;
  document_type: string;
  control_number: string;
  issued_on: string;
  due_on: string;
  /** Total a pagar del DTE (ya descuenta la retención). */
  payable: string;
  /** Notas de crédito y retornos vigentes. */
  credited: string;
  applied: string;
  balance: string;
  bucket: AgingBucket;
  overdue: boolean;
  invalidated: boolean;
  sale_id: string;
  sale_code: string;
  customer_id: string;
  withholding: string;
  certificate: WithholdingCertificate | null;
}

export interface ReceiptPayment {
  method: PaymentMethod;
  amount: string;
  reference: string | null;
}

export interface ReceiptApplication {
  document_id: string;
  control_number: string;
  amount: string;
  applied_on: string;
  document_invalidated: boolean;
}

export interface Receipt {
  id: string;
  code: string;
  number: number;
  branch_id: string;
  customer_id: string;
  received_on: string;
  total: string;
  unapplied: string;
  notes: string | null;
  status: 'issued' | 'annulled';
  payments: ReceiptPayment[];
  applications: ReceiptApplication[];
  annul_reason: string | null;
  annulled_at: string | null;
  created_at: string | null;
}

export interface CustomerAccount {
  customer: CustomerRef;
  balance: string;
  overdue: string;
  credit: string;
  aging: Record<AgingBucket, string>;
  documents: AccountDocument[];
  receipts: Receipt[];
}

export interface ReceiptInput {
  branch_id: string;
  customer_id: string;
  received_on: string;
  payments: { method: PaymentMethod; amount: string; reference: string | null }[];
  applications: { document_id: string; amount: string }[];
  notes: string | null;
  idempotency_key: string;
}
