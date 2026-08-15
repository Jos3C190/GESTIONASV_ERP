export interface SupplierImage {
  id?: string;
  source_type: 'cloudinary' | 'external';
  url: string;
  media_asset_id?: string | null;
  alt_text?: string | null;
}

export type SupplierImageDraft = SupplierImage;

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
  logo_image?: SupplierImage | null;
  contacts: SupplierContact[];
  created_at?: string;
  updated_at?: string;
}
