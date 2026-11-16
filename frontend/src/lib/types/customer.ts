import type { PersonType, TaxpayerCategory } from '$lib/types/fiscal';

/** Clientes con identidad fiscal (API `/customers`). */

export type CustomerType = 'final_consumer' | 'taxpayer' | 'foreign';
/** CAT-022: 36 NIT, 13 DUI, 02 carné de residente, 03 pasaporte, 37 otro. */
export type IdentityDocument = '36' | '13' | '02' | '03' | '37';

export interface GeographyInput {
  department_id: string;
  municipality_id: string;
  district_id: string;
}

export interface CustomerAddress {
  department_id: string | null;
  municipality_id: string | null;
  district_id: string | null;
  department: string | null;
  department_code: string | null;
  municipality: string | null;
  municipality_code: string | null;
  district: string | null;
  district_code: string | null;
}

export interface DeliveryAddress {
  id: string;
  label: string;
  address_line: string;
  address: CustomerAddress;
  latitude: string | null;
  longitude: string | null;
  contact_name: string | null;
  phone: string | null;
  is_default: boolean;
  is_active: boolean;
}

export interface Customer {
  id: string;
  company_id: string;
  code: string;
  customer_type: CustomerType;
  name: string;
  person_type: PersonType;
  taxpayer_category: TaxpayerCategory | null;
  is_withholding_agent: boolean;
  commercial_name: string | null;
  document_type: IdentityDocument | null;
  document_number: string | null;
  nrc: string | null;
  activity_code: string | null;
  activity_name: string | null;
  address: CustomerAddress;
  address_line: string | null;
  country_code: string | null;
  country_name: string | null;
  phone: string | null;
  email: string | null;
  credit_days: number;
  credit_limit: string | null;
  seller_employee_id: string | null;
  seller_name: string | null;
  price_list_id: string | null;
  price_list_name: string | null;
  is_active: boolean;
  is_generic: boolean;
  anonymized_at: string | null;
  branch_id: string | null;
  receivable_documents: string[];
  tax_credit_missing: string[];
  delivery_addresses: DeliveryAddress[];
  created_at: string;
  updated_at: string;
}

export interface CustomerInput {
  customer_type: CustomerType;
  name: string;
  person_type: PersonType;
  taxpayer_category: TaxpayerCategory | null;
  is_withholding_agent: boolean;
  commercial_name: string | null;
  document_type: IdentityDocument | null;
  document_number: string | null;
  nrc: string | null;
  activity_code: string | null;
  geography: GeographyInput | null;
  address_line: string | null;
  country_code: string | null;
  phone: string | null;
  email: string | null;
  credit_days: number;
  credit_limit: string | null;
  seller_employee_id: string | null;
  price_list_id: string | null;
}

export interface CustomerCreateInput extends CustomerInput {
  code?: string | null;
}

export interface DeliveryAddressInput {
  label: string;
  address_line: string;
  geography: GeographyInput | null;
  latitude: string | null;
  longitude: string | null;
  contact_name: string | null;
  phone: string | null;
  is_default: boolean;
  is_active: boolean;
}

export interface SellerOption {
  id: string;
  code: string;
  name: string;
  position: string | null;
}

export interface CustomerListParams {
  search?: string;
  customer_type?: CustomerType | '';
  active?: boolean | null;
  include_generic?: boolean;
  page?: number;
  size?: number;
}
