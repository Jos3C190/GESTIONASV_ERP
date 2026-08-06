export interface SupplierContact {
  id_supplier_contact: number;
  id_supplier: number;
  full_name: string;
  phone?: string | null;
  email?: string | null;
  is_active: boolean;
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
  contacts: SupplierContact[];
  created_at?: string;
  updated_at?: string;
}
