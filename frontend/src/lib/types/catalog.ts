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
  dimensions_legacy?: string | null;
  dimension_length?: number | null;
  dimension_width?: number | null;
  dimension_height?: number | null;
  dimension_unit?: 'mm' | 'cm' | 'm' | 'in' | 'ft' | null;
  weight?: number | null;
  weight_unit?: 'mg' | 'g' | 'kg' | 't' | 'oz' | 'lb' | null;
  dimension_summary?: string | null;
  volume?: number | null;
  volume_unit?: string | null;
  description?: string | null;
  presentation?: string | null;
  is_active: boolean;
  images: ProductImage[];
  image_count: number;
  cover_image: ProductImage | null;
  created_at?: string;
  updated_at?: string;
}

export interface ProductImage {
  id: string;
  product_id: number;
  source_type: 'cloudinary' | 'external';
  url: string;
  media_asset_id?: string | null;
  alt_text?: string | null;
  position: number;
  is_cover: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ProductImageDraft {
  id?: string;
  source_type: 'cloudinary' | 'external';
  url: string;
  media_asset_id?: string | null;
  alt_text?: string | null;
  position: number;
  is_cover: boolean;
}
