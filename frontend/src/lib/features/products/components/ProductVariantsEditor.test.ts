import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import ProductVariantsEditor from './ProductVariantsEditor.svelte';

describe('ProductVariantsEditor', () => {
  it('mantiene el foco al editar el código de un atributo', async () => {
    render(ProductVariantsEditor, {
      props: {
        companyId: 'company-1',
        variantConfig: {
          attributes: [
            {
              _key: 'attribute-stable',
              code: 'atributo_1',
              name: 'Presentación',
              position: 0,
              values: []
            }
          ],
          variants: []
        }
      }
    });

    const input = screen.getByRole('textbox', { name: 'Código del atributo 1' });
    input.focus();
    await fireEvent.input(input, { target: { value: 'c' } });

    expect(document.activeElement).toBe(input);
    expect(input).toHaveValue('c');
  });

  it('mantiene el foco al editar el código de un valor', async () => {
    render(ProductVariantsEditor, {
      props: {
        companyId: 'company-1',
        variantConfig: {
          attributes: [
            {
              _key: 'attribute-stable',
              code: 'color',
              name: 'Color',
              position: 0,
              values: [{ _key: 'value-stable', code: 'rojo', label: 'Rojo', position: 0 }]
            }
          ],
          variants: []
        }
      }
    });

    const input = screen.getByRole('textbox', { name: 'Código de valor 1' });
    input.focus();
    await fireEvent.input(input, { target: { value: 'r' } });

    expect(document.activeElement).toBe(input);
    expect(input).toHaveValue('r');
  });

  it('notifica al contenedor cuando genera la matriz', async () => {
    const onGenerate = vi.fn();
    render(ProductVariantsEditor, {
      props: {
        companyId: 'company-1',
        onGenerate,
        variantConfig: {
          attributes: [
            {
              _key: 'attribute-stable',
              code: 'color',
              name: 'Color',
              position: 0,
              values: [{ _key: 'value-stable', code: 'rojo', label: 'Rojo', position: 0 }]
            }
          ],
          variants: []
        }
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Generar combinaciones' }));

    expect(onGenerate).toHaveBeenCalledTimes(1);
    expect(onGenerate.mock.calls[0]?.[0].variants).toHaveLength(1);
  });

  it('permite pasar a selección manual cuando la matriz potencial supera 500', async () => {
    const onGenerate = vi.fn();
    const attributes = Array.from({ length: 3 }, (_, attributeIndex) => ({
      _key: `attribute-${attributeIndex}`,
      code: `atributo_${attributeIndex}`,
      name: `Atributo ${attributeIndex}`,
      position: attributeIndex,
      values: Array.from({ length: 9 }, (_, valueIndex) => ({
        _key: `value-${attributeIndex}-${valueIndex}`,
        code: `valor_${valueIndex}`,
        label: `Valor ${valueIndex}`,
        position: valueIndex
      }))
    }));

    render(ProductVariantsEditor, {
      props: {
        companyId: 'company-1',
        generationMode: 'selected',
        onGenerate,
        variantConfig: { attributes, variants: [] }
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Generar combinaciones' }));

    expect(onGenerate).toHaveBeenCalledTimes(1);
    expect(onGenerate.mock.calls[0]?.[0].variants).toHaveLength(0);
  });

  it('ofrece edición individual sin sacar la combinación del gestor', () => {
    render(ProductVariantsEditor, {
      props: {
        companyId: 'company-1',
        productId: 42,
        variantConfig: {
          attributes: [
            {
              _key: 'attribute-stable',
              code: 'color',
              name: 'Color',
              position: 0,
              values: [{ _key: 'value-stable', code: 'rojo', label: 'Rojo', position: 0 }]
            }
          ],
          variants: [
            {
              id: 'variant-1',
              sku: 'CAM-ROJO',
              name_override: null,
              lifecycle_status: 'draft',
              values: [{ attribute_code: 'color', value_code: 'rojo' }],
              identifiers: [],
              image: null
            }
          ]
        }
      }
    });

    expect(screen.getByRole('link', { name: 'Editar variante' })).toHaveAttribute(
      'href',
      '/products/42/variants/variant-1/edit'
    );
  });
});
