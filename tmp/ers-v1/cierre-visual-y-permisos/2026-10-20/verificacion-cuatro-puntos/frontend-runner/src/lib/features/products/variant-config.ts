import type {
  Product,
  ProductVariantConfig,
  ProductVariantDraft,
  ProductVariantConfigPayload
} from '$lib/types/catalog';

export function toVariantConfigPayload(config: ProductVariantConfig): ProductVariantConfigPayload {
  return {
    attributes: config.attributes.map(({ _key: _attributeKey, ...attribute }) => ({
      ...attribute,
      values: attribute.values.map(({ _key: _valueKey, ...value }) => value)
    })),
    variants: config.variants
  };
}

export function productToVariantConfig(product: Product): ProductVariantConfig | null {
  if (!product.variant_attributes?.length || !product.variants?.length) return null;
  return {
    attributes: product.variant_attributes.map((attribute) => ({
      _key: attribute.id,
      code: attribute.code,
      name: attribute.name,
      position: attribute.position,
      values: attribute.values.map((value) => ({
        _key: value.id,
        code: value.code,
        label: value.label,
        position: value.position
      }))
    })),
    variants: product.variants.map((variant) => ({
      id: variant.id,
      sku: variant.sku,
      name_override: variant.name_override ?? null,
      lifecycle_status: variant.lifecycle_status,
      values: variant.values.map((value) => ({
        attribute_code: value.attribute_code,
        value_code: value.value_code
      })),
      identifiers: variant.identifiers.map((identifier) => ({
        identifier_type: identifier.identifier_type,
        value: identifier.value,
        is_primary: identifier.is_primary
      })),
      image: variant.image
        ? {
            source_type: variant.image.source_type,
            url: variant.image.url,
            media_asset_id: variant.image.media_asset_id ?? null,
            alt_text: variant.image.alt_text ?? null
          }
        : null
    }))
  };
}

export function normalizeVariantToken(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, '-')
    .replace(/^[-_]+|[-_]+$/g, '')
    .toLocaleLowerCase();
}

/**
 * Stable identity for a combination. Attribute/value labels are intentionally
 * excluded: codes are the contract used by the API and remain stable when a
 * label is translated or edited.
 */
export function variantCombinationKey(variant: Pick<ProductVariantDraft, 'values'>): string {
  return variant.values
    .map(
      (value) =>
        `${normalizeVariantToken(value.attribute_code)}:${normalizeVariantToken(value.value_code)}`
    )
    .sort()
    .join('|');
}

export function cartesianCombinationCount(
  config: Pick<ProductVariantConfig, 'attributes'>
): number {
  if (
    !config.attributes.length ||
    config.attributes.some((attribute) => !attribute.values.length)
  ) {
    return 0;
  }
  return config.attributes.reduce((total, attribute) => total * attribute.values.length, 1);
}
