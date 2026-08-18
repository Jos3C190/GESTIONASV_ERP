import { describe, expect, it } from 'vitest';
import {
  cartesianCombinationCount,
  normalizeVariantToken,
  toVariantConfigPayload,
  variantCombinationKey
} from './variant-config';

describe('product variant config helpers', () => {
  it('normaliza códigos como el backend', () => {
    expect(normalizeVariantToken('  Rojo oscuro  ')).toBe('rojo-oscuro');
    expect(normalizeVariantToken('TALLA_Á')).toBe('talla_a');
  });

  it('retira las claves internas del editor antes de enviar la configuración', () => {
    const payload = toVariantConfigPayload({
      attributes: [
        {
          _key: 'attribute-ui',
          code: 'color',
          name: 'Color',
          position: 0,
          values: [{ _key: 'value-ui', code: 'rojo', label: 'Rojo', position: 0 }]
        }
      ],
      variants: []
    });

    expect(payload).toEqual({
      attributes: [
        {
          code: 'color',
          name: 'Color',
          position: 0,
          values: [{ code: 'rojo', label: 'Rojo', position: 0 }]
        }
      ],
      variants: []
    });
    expect(JSON.stringify(payload)).not.toContain('_key');
  });

  it('identifica una combinación sin depender del orden de sus atributos', () => {
    expect(
      variantCombinationKey({
        values: [
          { attribute_code: 'Talla', value_code: 'M' },
          { attribute_code: 'Color', value_code: 'Rojo' }
        ]
      })
    ).toBe('color:rojo|talla:m');
  });

  it('calcula el tamaño de la matriz antes de materializarla', () => {
    expect(
      cartesianCombinationCount({
        attributes: [
          { code: 'color', name: 'Color', position: 0, values: [{ code: 'r', label: 'Rojo', position: 0 }, { code: 'a', label: 'Azul', position: 1 }] },
          { code: 'size', name: 'Talla', position: 1, values: [{ code: 's', label: 'S', position: 0 }, { code: 'm', label: 'M', position: 1 }, { code: 'l', label: 'L', position: 2 }] }
        ]
      })
    ).toBe(6);
  });
});
