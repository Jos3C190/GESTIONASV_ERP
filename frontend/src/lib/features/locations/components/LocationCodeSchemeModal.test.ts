import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { LocationCodeScheme } from '../types';
import LocationCodeSchemeModal from './LocationCodeSchemeModal.svelte';

vi.mock('../services', () => ({
  updateLocationCodeScheme: vi.fn()
}));

const scheme: LocationCodeScheme = {
  id: 'scheme-1',
  warehouse_id: 'warehouse-1',
  name: 'Ruta numérica',
  version: 1,
  separator: '-',
  segments: [
    {
      key: 'aisle',
      label: 'Pasillo',
      prefix: 'A',
      width: 2,
      pad_char: '0',
      required: true
    },
    {
      key: 'rack',
      label: 'Rack',
      prefix: 'R',
      width: 2,
      pad_char: '0',
      required: true
    }
  ],
  is_active: true,
  created_at: '2026-08-12T00:00:00Z',
  updated_at: null
};

describe('LocationCodeSchemeModal', () => {
  it('admite ancho cero como segmento sin relleno y conserva el rango contractual', async () => {
    render(LocationCodeSchemeModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        scheme,
        onclose: vi.fn(),
        onsaved: vi.fn()
      }
    });

    const aisleWidth = screen.getAllByLabelText('Ancho')[0] as HTMLInputElement;
    expect(aisleWidth).toHaveAttribute('min', '0');
    expect(aisleWidth).toHaveAttribute('max', '32');
    expect(screen.getByText('A01-R01')).toBeInTheDocument();

    await fireEvent.input(aisleWidth, { target: { value: '0' } });

    expect(aisleWidth).toHaveValue(0);
    expect(screen.getByText('A1-R01')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Crear versión 2' })).toBeEnabled();
  });

  it('mantiene en el ejemplo los segmentos opcionales', async () => {
    render(LocationCodeSchemeModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        scheme,
        onclose: vi.fn(),
        onsaved: vi.fn()
      }
    });

    await fireEvent.click(screen.getAllByLabelText('Obligatorio')[0]!);

    expect(screen.getByText('A01-R01')).toBeInTheDocument();
  });
});
