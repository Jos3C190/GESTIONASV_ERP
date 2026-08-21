import type { ProductSupplier } from '$lib/types/catalog';

export function supplierDisplayName(
  relation: Pick<ProductSupplier, 'supplier_id' | 'supplier_name'>
): string {
  const name = relation.supplier_name?.trim();
  return name || `Proveedor no disponible (#${relation.supplier_id})`;
}
