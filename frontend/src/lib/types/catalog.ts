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
  product_kind?: 'goods' | 'service';
  lifecycle_status?: 'draft' | 'active' | 'blocked' | 'discontinued' | 'retired';
  can_purchase?: boolean;
  can_sell?: boolean;
  sales_name?: string | null;
  internal_name?: string | null;
  document_name?: string | null;
  sales_description?: string | null;
  purchase_description?: string | null;
  internal_notes?: string | null;
  keywords?: string[];
  origin_country_id?: number | null;
  brand_id?: string | null;
  manufacturer_id?: string | null;
  storage_condition?: 'ambient' | 'cool' | 'refrigerated' | 'frozen' | 'dry' | 'other' | null;
  storage_temperature_min_c?: number | null;
  storage_temperature_max_c?: number | null;
  storage_humidity_max_percent?: number | null;
  is_fragile?: boolean;
  keep_dry?: boolean;
  keep_upright?: boolean;
  stackable?: boolean;
  max_stack_height?: number | null;
  handling_notes?: string | null;
  identifiers?: ProductIdentifier[];
  supplier_links?: ProductSupplier[];
  images: ProductImage[];
  image_count: number;
  cover_image: ProductImage | null;
  variant_mode?: 'standalone' | 'template';
  variant_count?: number;
  variant_attributes?: ProductFamilyAttribute[];
  variants?: ProductVariant[];
  created_at?: string;
  updated_at?: string;
}

export interface ProductIdentifier {
  id: string;
  product_id?: number | null;
  variant_id?: string | null;
  company_id: string;
  identifier_type: 'ean' | 'upc' | 'gtin' | 'isbn' | 'manufacturer' | 'internal' | 'other';
  value: string;
  normalized_value: string;
  is_primary: boolean;
  is_active: boolean;
}

export interface ProductSupplier {
  id: string;
  product_id: number;
  supplier_id: number;
  company_id: string;
  supplier_product_code?: string | null;
  unit_cost?: number | null;
  currency_code?: string | null;
  minimum_order_qty?: number | null;
  order_multiple?: number | null;
  lead_time_days?: number | null;
  is_preferred: boolean;
  status: 'active' | 'inactive';
  valid_from?: string | null;
  valid_until?: string | null;
  notes?: string | null;
}

export type ProductSupplierDraft = Omit<ProductSupplier, 'id' | 'product_id' | 'company_id'> & {
  id?: string;
};

export interface ProductImage {
  id: string;
  product_id?: number | null;
  variant_id?: string | null;
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

export interface ProductFamilyAttributeValue {
  id: string;
  attribute_id: string;
  code: string;
  label: string;
  position: number;
  is_active: boolean;
}

export interface ProductFamilyAttribute {
  id: string;
  product_id: number;
  code: string;
  name: string;
  position: number;
  is_active: boolean;
  values: ProductFamilyAttributeValue[];
}

export interface ProductVariantValue {
  attribute_code: string;
  value_code: string;
  label: string;
}

export interface ProductVariantImageDraft {
  source_type: 'cloudinary' | 'external';
  url: string;
  media_asset_id?: string | null;
  alt_text?: string | null;
}

export interface ProductVariantDraft {
  id?: string | null;
  sku: string;
  name_override?: string | null;
  lifecycle_status: 'draft' | 'active' | 'blocked' | 'discontinued' | 'retired';
  values: { attribute_code: string; value_code: string }[];
  identifiers: {
    identifier_type: ProductIdentifier['identifier_type'];
    value: string;
    is_primary?: boolean;
  }[];
  image?: ProductVariantImageDraft | null;
}

export interface ProductVariant {
  id: string;
  product_id: number;
  company_id: string;
  sku: string;
  name_override?: string | null;
  display_name: string;
  combination_key: string;
  lifecycle_status: 'draft' | 'active' | 'blocked' | 'discontinued' | 'retired';
  is_active: boolean;
  values: ProductVariantValue[];
  identifiers: ProductIdentifier[];
  image?: ProductImage | null;
  created_at?: string;
  updated_at?: string;
}

export interface ProductVariantUpdateInput {
  sku?: string;
  name_override?: string | null;
  lifecycle_status?: ProductVariant['lifecycle_status'];
  identifiers?: ProductVariantDraft['identifiers'];
  image?: ProductVariantImageDraft | null;
  expected_updated_at: string;
}

export interface ProductVariantConfig {
  attributes: {
    /** Stable UI identity; stripped before sending variant_config to the API. */
    _key?: string;
    code: string;
    name: string;
    position: number;
    values: { _key?: string; code: string; label: string; position: number }[];
  }[];
  variants: ProductVariantDraft[];
}

/** API-safe representation without editor-only stable keys. */
export interface ProductVariantConfigPayload {
  attributes: {
    code: string;
    name: string;
    position: number;
    values: { code: string; label: string; position: number }[];
  }[];
  variants: ProductVariantDraft[];
}
