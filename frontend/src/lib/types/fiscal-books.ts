/** Libros de IVA y anexos del F-07 de un mes. */
export type FiscalBookMode = 'production' | 'test' | 'simulated';
export type FiscalBookKind = 'contributors' | 'consumers' | 'purchases';

export interface FiscalBookSummary {
  contributor_taxed: string;
  contributor_vat: string;
  consumer_taxed_with_vat: string;
  consumer_vat: string;
  exempt_sales: string;
  not_subject_sales: string;
  debit: string;
  purchase_taxed: string;
  credit: string;
  perception_collected: string;
  /** Débito - crédito + percepción cobrada, antes de remanentes y retenciones. */
  balance: string;
}

export interface ContributorLine {
  number: number;
  issued_on: string;
  document_type: string;
  generation_code: string;
  control_number: string;
  customer: string;
  registry: string;
  exempt: string;
  not_subject: string;
  taxed: string;
  vat: string;
  perception: string;
  total: string;
}

export interface ConsumerLine {
  day: string;
  first_control: string;
  last_control: string;
  point_of_sale: string;
  exempt: string;
  not_subject: string;
  taxed: string;
  exports: string;
  total: string;
  third_parties: string;
  note: string;
}

export interface PurchaseLine {
  number: number;
  issued_on: string;
  document_type: string;
  document_number: string;
  registry: string;
  excluded_subject_id: string;
  supplier: string;
  internal_exempt: string;
  import_exempt: string;
  internal_taxed: string;
  import_taxed: string;
  vat: string;
  perception: string;
  total: string;
  third_party_withholding: string;
  excluded_subjects: string;
}

export interface FiscalAnnex {
  key: string;
  title: string;
  file_name: string;
  rows: string[][];
}

export interface PendingPurchase {
  id: string;
  code: string;
  supplier: string;
  invoice_number: string | null;
  invoice_date: string | null;
  total: string;
}

export interface FiscalMonth {
  period: string;
  label: string;
  mode: FiscalBookMode;
  modes: FiscalBookMode[];
  issuer: { name: string; nit: string | null; nrc: string | null };
  warnings: string[];
  summary: FiscalBookSummary;
  contributor_book: ContributorLine[];
  consumer_book: ConsumerLine[];
  purchase_book: PurchaseLine[];
  annexes: FiscalAnnex[];
  pending_purchases: PendingPurchase[];
}

export interface RentaPurchase {
  operation: number;
  classification: number;
  sector: number;
  cost_type: number;
}

export type SupplierIdType = 'nit' | 'nrc' | 'dui';
export type PurchaseDocumentClass = 1 | 3 | 4;
export type PurchaseDocumentType = '03' | '05' | '06' | '12' | '13';

export interface PurchaseFiscalInput {
  issued_on: string;
  document_class: PurchaseDocumentClass;
  document_type: PurchaseDocumentType;
  number: string;
  control_number: string | null;
  seal: string | null;
  supplier_name: string;
  supplier_id_type: SupplierIdType;
  supplier_id: string;
  renta: RentaPurchase;
}

export interface PurchaseFiscal {
  id: string;
  code: string;
  status: string;
  supplier_name: string;
  supplier_ids: Partial<Record<SupplierIdType, string>>;
  invoice_number: string | null;
  invoice_date: string | null;
  exempt: string;
  taxed: string;
  vat: string;
  recorded: PurchaseFiscalInput | null;
  recorded_at: string | null;
  renta_defaults: RentaPurchase;
}

/** Cierre de un mes fiscal (V8b2). */
export interface PeriodClose {
  id: string;
  status: 'closed' | 'reopened';
  summary: Record<string, string>;
  closed_by: string | null;
  closed_at: string;
  reopen_reason: string | null;
  reopened_by: string | null;
  reopened_at: string | null;
}

export interface PeriodStatus {
  period: string;
  label: string;
  closed: PeriodClose | null;
  history: PeriodClose[];
  /** Lo que impide cerrar el mes (vacío si se puede). */
  blockers: string[];
}
