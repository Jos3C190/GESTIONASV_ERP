/** Configuración fiscal del emisor de DTE (API `/fiscal`). */

export type OperatingMode = 'simulated' | 'test' | 'production';
export type TaxpayerCategory = 'large' | 'medium' | 'other';
/** CAT-029: 1 persona natural, 2 persona jurídica. */
export type PersonType = '1' | '2';
/** CAT-009: 01 sucursal, 02 casa matriz, 04 bodega, 07 patio. */
export type EstablishmentType = '01' | '02' | '04' | '07';
export type CertificationStatus = 'pending' | 'in_progress' | 'approved';

export interface CatalogSummary {
  code: string;
  title: string;
}

export interface CatalogItem {
  group_code: string;
  code: string;
  name: string;
}

export interface FiscalProfile {
  company_id: string;
  company_name: string;
  commercial_name: string;
  nit: string;
  nrc: string;
  taxpayer_category: TaxpayerCategory;
  person_type: PersonType;
  operating_mode: OperatingMode;
  dte_email: string | null;
  dte_phone: string | null;
  configured: boolean;
  updated_at: string | null;
  production_blockers: string[];
}

export interface FiscalProfileInput {
  taxpayer_category: TaxpayerCategory;
  person_type: PersonType;
  operating_mode: OperatingMode;
  dte_email: string | null;
  dte_phone: string | null;
}

export interface EconomicActivity {
  id: string;
  code: string;
  description: string;
  is_primary: boolean;
}

export interface PointOfSale {
  id: string;
  establishment_id: string;
  code: string;
  name: string;
  is_active: boolean;
}

export interface EstablishmentAddress {
  department: string;
  department_code: string | null;
  municipality: string;
  municipality_code: string | null;
  district: string;
  district_code: string | null;
  complement: string;
  complete: boolean;
}

export interface Establishment {
  id: string;
  branch_id: string;
  branch_name: string;
  establishment_type: EstablishmentType;
  code: string;
  activity_id: string | null;
  activity_code: string | null;
  is_active: boolean;
  address: EstablishmentAddress;
  phone: string | null;
  email: string | null;
  points_of_sale: PointOfSale[];
}

export interface EstablishmentInput {
  branch_id: string;
  establishment_type: EstablishmentType;
  code: string;
  activity_id: string | null;
}

export interface EstablishmentUpdateInput {
  establishment_type: EstablishmentType;
  code: string;
  activity_id: string | null;
  is_active: boolean;
}

export interface BranchOption {
  id: string;
  name: string;
  code: string | null;
  is_headquarters: boolean;
  establishment_id: string | null;
}

export interface PointOfSaleInput {
  code: string;
  name: string;
}

export interface PointOfSaleUpdateInput extends PointOfSaleInput {
  is_active: boolean;
}

export interface DocumentTypeSetting {
  document_type: string;
  name: string;
  is_enabled: boolean;
  certification_status: CertificationStatus;
  certified_at: string | null;
  notes: string | null;
}

export interface DocumentTypeInput {
  is_enabled: boolean;
  certification_status: CertificationStatus;
  notes?: string | null;
}

/** SMTP propio de la empresa (bloque V3c). La contraseña nunca vuelve del servidor. */
export type SmtpSecurity = 'none' | 'starttls' | 'ssl';

export interface EmailSettings {
  configured: boolean;
  host: string | null;
  port: number | null;
  security: SmtpSecurity | null;
  username: string | null;
  has_password: boolean;
  from_address: string | null;
  from_name: string | null;
  is_enabled: boolean;
  last_test_at: string | null;
  last_test_ok: boolean | null;
  last_test_error: string | null;
  server_fallback: boolean;
}

export interface EmailSettingsInput {
  host: string;
  port: number;
  security: SmtpSecurity;
  username: string | null;
  password: string | null;
  from_address: string;
  from_name: string | null;
  is_enabled: boolean;
}

export interface EmailTestResult {
  ok: boolean;
  message: string;
}

/** Credenciales de Hacienda de la empresa (bloque V3d). Nada secreto vuelve del servidor. */
export interface HaciendaCredentials {
  configured: boolean;
  certificate_nit: string | null;
  certificate_sha256: string | null;
  last_test_at: string | null;
  last_test_ok: boolean | null;
  last_test_error: string | null;
  updated_at: string | null;
}

export interface HaciendaCredentialsInput {
  api_password: string | null;
  private_key_password: string | null;
  certificate_base64: string | null;
}

export interface HaciendaTestResult {
  ok: boolean;
  authentication_ok: boolean;
  authentication_message: string;
  signature_ok: boolean;
  signature_message: string;
}
