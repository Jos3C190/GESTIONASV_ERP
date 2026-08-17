import { apiFetch } from '$lib/api/client';
import type {
  Category,
  Country,
  Product,
  ProductImageDraft,
  SubCategory,
  Unit
} from '$lib/types/catalog';
import type { ProductIdentifier, ProductSupplier } from '$lib/types/catalog';

export interface PageResponse<T> {
  items: T[];
  meta: {
    page: number;
    size: number;
    total: number;
    pages: number;
  };
}

export interface ProductStats {
  total: number;
  active: number;
  inactive: number;
  categories: number;
}

export const catalogApi = {
  // Countries
  listCountries: (activeOnly = true) =>
    apiFetch<Country[]>(`/catalog/countries?active_only=${activeOnly}`),

  // Categories
  listCategories: (activeOnly = true) =>
    apiFetch<Category[]>(`/catalog/categories?active_only=${activeOnly}`),

  createCategory: (data: { name: string; description?: string }) =>
    apiFetch<Category>('/catalog/categories', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateCategory: (
    id: number,
    data: Partial<{ name: string; description: string; is_active: boolean }>
  ) =>
    apiFetch<Category>(`/catalog/categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),

  // SubCategories
  listSubCategories: (categoryId?: number, activeOnly = true) => {
    const params = new URLSearchParams();
    if (categoryId) params.append('category_id', categoryId.toString());
    params.append('active_only', activeOnly.toString());
    return apiFetch<SubCategory[]>(`/catalog/sub-categories?${params.toString()}`);
  },

  createSubCategory: (data: { id_category: number; name: string; description?: string }) =>
    apiFetch<SubCategory>('/catalog/sub-categories', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateSubCategory: (
    id: number,
    data: Partial<{ name: string; description: string; is_active: boolean }>
  ) =>
    apiFetch<SubCategory>(`/catalog/sub-categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),

  // Units
  listUnits: (activeOnly = true) => apiFetch<Unit[]>(`/catalog/units?active_only=${activeOnly}`),

  createUnit: (data: {
    name: string;
    type: string;
    code: string;
    symbol: string;
    description?: string;
  }) =>
    apiFetch<Unit>('/catalog/units', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateUnit: (
    id: number,
    data: Partial<{
      name: string;
      type: string;
      code: string;
      symbol: string;
      description: string;
      is_active: boolean;
    }> & { version: number }
  ) =>
    apiFetch<Unit>(`/catalog/units/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),

  activateUnit: (id: number, version: number, alias?: string | null) =>
    apiFetch<Unit>(`/catalog/units/${id}/activate`, {
      method: 'POST',
      body: JSON.stringify({ version, alias })
    }),

  deactivateUnit: (id: number, version: number, alias?: string | null) =>
    apiFetch<Unit>(`/catalog/units/${id}/deactivate`, {
      method: 'POST',
      body: JSON.stringify({ version, alias })
    }),

  listGlobalUnits: (activeOnly = false) =>
    apiFetch<Unit[]>(`/catalog/units/global?active_only=${activeOnly}`),

  createGlobalUnit: (data: {
    name: string;
    type: string;
    code: string;
    symbol: string;
    description?: string;
  }) =>
    apiFetch<Unit>('/catalog/units/global', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateGlobalUnit: (
    id: number,
    data: Partial<{
      name: string;
      type: string;
      code: string;
      symbol: string;
      description: string;
      is_active: boolean;
    }> & { version: number }
  ) =>
    apiFetch<Unit>(`/catalog/units/global/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),

  // Products
  listProducts: (params?: {
    category_id?: number;
    sub_category_id?: number;
    search?: string;
    active_only?: boolean;
    page?: number;
    size?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.category_id) q.append('category_id', params.category_id.toString());
    if (params?.sub_category_id) q.append('sub_category_id', params.sub_category_id.toString());
    if (params?.search) q.append('search', params.search);
    if (params?.active_only !== undefined) q.append('active_only', params.active_only.toString());
    if (params?.page) q.append('page', params.page.toString());
    if (params?.size) q.append('size', params.size.toString());
    return apiFetch<PageResponse<Product>>(`/catalog/products?${q.toString()}`);
  },

  productStats: () => apiFetch<ProductStats>('/catalog/products/stats'),

  getProduct: (id: number) => apiFetch<Product>(`/catalog/products/${id}`),

  createProduct: (data: {
    id_category: number;
    id_sub_category?: number | null;
    sku: string;
    name: string;
    purchase_unit: number;
    sale_unit: number;
    original_code?: string;
    internal_code?: string;
    size?: string;
    dimension_length?: number | null;
    dimension_width?: number | null;
    dimension_height?: number | null;
    dimension_unit?: 'mm' | 'cm' | 'm' | 'in' | 'ft' | null;
    weight?: number | null;
    weight_unit?: 'mg' | 'g' | 'kg' | 't' | 'oz' | 'lb' | null;
    description?: string;
    presentation?: string;
    product_kind?: 'goods' | 'service';
    lifecycle_status?: 'draft' | 'active' | 'blocked' | 'discontinued' | 'retired';
    can_purchase?: boolean;
    can_sell?: boolean;
    sales_name?: string;
    internal_name?: string;
    document_name?: string;
    sales_description?: string;
    purchase_description?: string;
    internal_notes?: string;
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
    handling_notes?: string;
    images?: ProductImageDraft[];
  }) =>
    apiFetch<Product>('/catalog/products', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateProduct: (
    id: number,
    data: Partial<{
      id_category: number;
      id_sub_category?: number | null;
      sku: string;
      name: string;
      purchase_unit: number;
      sale_unit: number;
      original_code: string;
      internal_code: string;
      size: string;
      dimension_length: number | null;
      dimension_width: number | null;
      dimension_height: number | null;
      dimension_unit: 'mm' | 'cm' | 'm' | 'in' | 'ft' | null;
      weight: number | null;
      weight_unit: 'mg' | 'g' | 'kg' | 't' | 'oz' | 'lb' | null;
      description: string;
      presentation: string;
      is_active: boolean;
      product_kind: 'goods' | 'service';
      lifecycle_status: 'draft' | 'active' | 'blocked' | 'discontinued' | 'retired';
      can_purchase: boolean;
      can_sell: boolean;
      sales_name: string;
      internal_name: string;
      document_name: string;
      sales_description: string;
      purchase_description: string;
      internal_notes: string;
      keywords: string[];
      origin_country_id: number | null;
      brand_id: string | null;
      manufacturer_id: string | null;
      storage_condition: 'ambient' | 'cool' | 'refrigerated' | 'frozen' | 'dry' | 'other' | null;
      storage_temperature_min_c: number | null;
      storage_temperature_max_c: number | null;
      storage_humidity_max_percent: number | null;
      is_fragile: boolean;
      keep_dry: boolean;
      keep_upright: boolean;
      stackable: boolean;
      max_stack_height: number | null;
      handling_notes: string;
      images: ProductImageDraft[];
    }>
  ) =>
    apiFetch<Product>(`/catalog/products/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),
  listProductIdentifiers: (productId: number) =>
    apiFetch<ProductIdentifier[]>(`/catalog/products/${productId}/identifiers`),
  createProductIdentifier: (
    productId: number,
    data: {
      identifier_type: ProductIdentifier['identifier_type'];
      value: string;
      is_primary?: boolean;
    }
  ) =>
    apiFetch<ProductIdentifier>(`/catalog/products/${productId}/identifiers`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),
  updateProductIdentifier: (
    productId: number,
    identifierId: string,
    data: Partial<{
      identifier_type: ProductIdentifier['identifier_type'];
      value: string;
      is_primary: boolean;
      is_active: boolean;
    }>
  ) =>
    apiFetch<ProductIdentifier>(`/catalog/products/${productId}/identifiers/${identifierId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),
  deleteProductIdentifier: (productId: number, identifierId: string) =>
    apiFetch<void>(`/catalog/products/${productId}/identifiers/${identifierId}`, {
      method: 'DELETE'
    }),
  listProductSuppliers: (productId: number) =>
    apiFetch<ProductSupplier[]>(`/catalog/products/${productId}/suppliers`),
  replaceProductSuppliers: (
    productId: number,
    suppliers: Array<Omit<ProductSupplier, 'id' | 'product_id' | 'company_id'>>
  ) =>
    apiFetch<ProductSupplier[]>(`/catalog/products/${productId}/suppliers`, {
      method: 'PUT',
      body: JSON.stringify({ suppliers })
    }),
  createProductSupplier: (
    productId: number,
    data: Omit<ProductSupplier, 'id' | 'product_id' | 'company_id'>
  ) =>
    apiFetch<ProductSupplier>(`/catalog/products/${productId}/suppliers`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),
  updateProductSupplier: (
    productId: number,
    relationId: string,
    data: Partial<Omit<ProductSupplier, 'id' | 'product_id' | 'company_id'>>
  ) =>
    apiFetch<ProductSupplier>(`/catalog/products/${productId}/suppliers/${relationId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),
  deleteProductSupplier: (productId: number, relationId: string) =>
    apiFetch<void>(`/catalog/products/${productId}/suppliers/${relationId}`, { method: 'DELETE' })
};
