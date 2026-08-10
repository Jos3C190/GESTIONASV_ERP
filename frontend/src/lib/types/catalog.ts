export interface Country {
  id_country: number;
  name: string;
  iso_code_2: string;
  iso_code_3: string;
  phone_code: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Category {
  id_category: number;
  uuid: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface SubCategory {
  id_sub_category: number;
  id_category: number;
  name: string;
  description?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Unit {
  id_unit: number;
  name: string;
  type: string;
  code: string;
  symbol: string;
  owner_company_id?: string | null;
  description?: string | null;
  is_standard: boolean;
  is_enabled: boolean;
  alias?: string | null;
  version: number;
  configuration_version: number;
  usage_count: number;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Product {
  id_product: number;
  uuid: string;
  id_category: number;
  id_sub_category?: number | null;
  sku: string;
  name: string;
  purchase_unit: number;
  sale_unit: number;
  original_code?: string | null;
  internal_code?: string | null;
  size?: string | null;
  dimensions?: string | null;
  description?: string | null;
  presentation?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}
