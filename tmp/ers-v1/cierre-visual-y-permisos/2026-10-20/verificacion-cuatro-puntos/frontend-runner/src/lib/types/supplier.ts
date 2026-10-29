export interface SupplierImage {
  id?: string;
  source_type: 'cloudinary' | 'external';
  url: string;
  media_asset_id?: string | null;
  alt_text?: string | null;
}

export type SupplierImageDraft = SupplierImage;

export type SupplierStatus =
  | 'pending_review'
  | 'approved'
  | 'on_hold'
  | 'suspended'
  | 'rejected'
  | 'retired';

export interface SupplierTaxIdentifier {
  id: string;
  supplier_id: number;
  country_id: number;
  identifier_type: string;
  value: string;
  normalized_value: string;
  is_primary: boolean;
  is_verified: boolean;
  verified_at?: string | null;
  valid_from?: string | null;
  valid_until?: string | null;
}

export interface SupplierAddress {
  id: string;
  supplier_id: number;
  address_type: 'fiscal' | 'billing' | 'delivery' | 'return' | 'office' | 'other';
  line1: string;
  line2?: string | null;
  country_id?: number | null;
  state_region?: string | null;
  city?: string | null;
  postal_code?: string | null;
  phone?: string | null;
  email?: string | null;
  is_primary: boolean;
}

export interface SupplierBankAccount {
  id: string;
  supplier_id: number;
  bank_name: string;
  account_holder: string;
  country_id?: number | null;
  currency_code?: string | null;
  account_type?: string | null;
  last_four: string;
  is_primary: boolean;
  is_verified: boolean;
  status: 'active' | 'blocked' | 'closed';
}

export interface SupplierGroup {
  id: string;
  company_id: string;
  code: string;
  name: string;
  description?: string | null;
  is_active: boolean;
}

export interface PaymentTerms {
  id: string;
  company_id: string;
  code: string;
  name: string;
  net_days: number;
  discount_days: number;
  discount_percent: number;
  is_active: boolean;
}

export interface Currency {
  code: string;
  name: string;
  symbol: string;
  decimal_places: number;
  is_active: boolean;
}

export interface SupplierContact {
  id_supplier_contact: number;
  id_supplier: number;
  uuid?: string | null;
  full_name: string;
  phone?: string | null;
  email?: string | null;
  is_active: boolean;
  avatar_image?: SupplierImage | null;
  created_at?: string;
  updated_at?: string;
}

export interface Supplier {
  id_supplier: number;
  uuid: string;
  code: string;
  name: string;
  country: number;
  address?: string | null;
  phone?: string | null;
  email?: string | null;
  website?: string | null;
  is_active: boolean;
  legal_name?: string | null;
  supplier_group_id?: string | null;
  supplier_status?: SupplierStatus;
  hold_reason?: string | null;
  hold_from?: string | null;
  hold_until?: string | null;
  default_currency_code?: string | null;
  payment_terms_id?: string | null;
  default_payment_method?: string | null;
  external_reference?: string | null;
  logo_image?: SupplierImage | null;
  tax_identifiers?: SupplierTaxIdentifier[];
  addresses?: SupplierAddress[];
  bank_accounts?: SupplierBankAccount[];
  contacts: SupplierContact[];
  created_at?: string;
  updated_at?: string;
}
