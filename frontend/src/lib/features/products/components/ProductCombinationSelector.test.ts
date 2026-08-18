import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import ProductCombinationSelector from './ProductCombinationSelector.svelte';

const candidates = [
  {
    id: 'existing-rojo',
    sku: 'PAN-ROJO-S',
    name_override: null,
    lifecycle_status: 'active' as const,
    values: [
      { attribute_code: 'color', value_code: 'rojo' },
      { attribute_code: 'talla', value_code: 's' }
    ],
    identifiers: [],
    image: null
  },
  {
    id: null,
    sku: 'PAN-AZUL-M',
    name_override: null,
    lifecycle_status: 'draft' as const,
    values: [
      { attribute_code: 'color', value_code: 'azul' },
      { attribute_code: 'talla', value_code: 'm' }
    ],
    identifiers: [],
    image: null
  }
];

const attributes = [
  {
    code: 'color',
    name: 'Color',
    position: 0,
    values: [
      { code: 'rojo', label: 'Rojo', position: 0 },
      { code: 'azul', label: 'Azul', position: 1 }
    ]
  },
  {
    code: 'talla',
    name: 'Talla',
    position: 1,
    values: [{ code: 's', label: 'S', position: 0 }, { code: 'm', label: 'M', position: 1 }]
  }
];

describe('ProductCombinationSelector', () => {
  it('permite conservar solo una combinación', async () => {
    const onChange = vi.fn();
    render(ProductCombinationSelector, {
      props: { candidates, selectedKeys: ['color:azul|talla:m', 'color:rojo|talla:s'], onChange }
    });

    await fireEvent.click(screen.getByRole('checkbox', { name: /Incluir color: rojo/i }));

    expect(onChange).toHaveBeenCalledWith(['color:azul|talla:m']);
  });

  it('selecciona o quita las filas visibles en bloque', async () => {
    const onChange = vi.fn();
    render(ProductCombinationSelector, {
      props: { candidates, selectedKeys: [], onChange }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Seleccionar visibles' }));
    expect(onChange).toHaveBeenLastCalledWith(['color:rojo|talla:s', 'color:azul|talla:m']);

    await fireEvent.click(screen.getByRole('button', { name: 'Quitar visibles' }));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it('muestra la matriz completa como resumen no editable', async () => {
    const onChange = vi.fn();
    render(ProductCombinationSelector, {
      props: {
        candidates,
        selectedKeys: ['color:azul|talla:m', 'color:rojo|talla:s'],
        selectionMode: 'all',
        onChange
      }
    });

    expect(screen.getByRole('heading', { name: 'Resumen de la matriz completa' })).toBeInTheDocument();
    expect(screen.getByText('2 / 2')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Seleccionar visibles' })).not.toBeInTheDocument();
    expect(screen.getAllByText('Incluida')).toHaveLength(2);
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
    await fireEvent.click(screen.getAllByText('Incluida')[0]!);
    expect(onChange).not.toHaveBeenCalled();
  });

  it('filtra por tipo, estado y valor de atributo', async () => {
    const onChange = vi.fn();
    render(ProductCombinationSelector, {
      props: {
        candidates: [
          ...candidates,
          {
            id: 'retired-blue',
            sku: 'PAN-AZUL-M-OLD',
            name_override: null,
            lifecycle_status: 'retired' as const,
            values: [
              { attribute_code: 'color', value_code: 'azul' },
              { attribute_code: 'talla', value_code: 'm' }
            ],
            identifiers: [],
            image: null
          }
        ],
        selectedKeys: [
          'color:rojo|talla:s',
          'color:azul|talla:m'
        ],
        existingKeys: ['color:rojo|talla:s', 'color:azul|talla:m'],
        attributes,
        onChange
      }
    });

    await fireEvent.change(screen.getByRole('combobox', { name: 'Filtrar por tipo' }), {
      target: { value: 'retired' }
    });
    expect(screen.getByText('PAN-AZUL-M-OLD')).toBeInTheDocument();
    expect(screen.queryByText('PAN-ROJO-S')).not.toBeInTheDocument();

    await fireEvent.change(screen.getByRole('combobox', { name: 'Filtrar por estado' }), {
      target: { value: 'active' }
    });
    expect(screen.getByText('No hay combinaciones que coincidan con el filtro.')).toBeInTheDocument();

    await fireEvent.change(screen.getByRole('combobox', { name: 'Filtrar por tipo' }), {
      target: { value: 'all' }
    });
    await fireEvent.change(screen.getByRole('combobox', { name: 'Filtrar por estado' }), {
      target: { value: 'all' }
    });
    await fireEvent.change(screen.getByRole('combobox', { name: 'Filtrar por Color' }), {
      target: { value: 'rojo' }
    });
    expect(screen.getByText('PAN-ROJO-S')).toBeInTheDocument();
    expect(screen.queryByText('PAN-AZUL-M')).not.toBeInTheDocument();
    expect(screen.queryByText('PAN-AZUL-M-OLD')).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });
});
