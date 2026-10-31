import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { LocationCodeScheme } from '../types';
import { updateLocationCodeScheme } from '../services';
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
  it('permite crear el esquema inicial con una ruta física general', async () => {
    const createdScheme = { ...scheme, name: 'Ruta física general', version: 1 };
    vi.mocked(updateLocationCodeScheme).mockResolvedValue(createdScheme);
    const onclose = vi.fn();
    const onsaved = vi.fn();

    render(LocationCodeSchemeModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        scheme: null,
        onclose,
        onsaved
      }
    });

    expect(screen.getByText(/Este almacén aún no tiene un formato de códigos/)).toBeInTheDocument();
    expect(screen.getByText('A01-R01-N01-P01')).toBeInTheDocument();
    expect(screen.getByLabelText('Pasillo: Prefijo')).toHaveValue('A');
    expect(screen.getByLabelText('Rack: Ancho')).toHaveValue(2);
    expect(screen.getByLabelText('Nivel: Carácter de relleno')).toHaveValue('0');
    expect(screen.getByLabelText('Posición: Obligatorio')).toBeChecked();
    await fireEvent.click(screen.getByRole('button', { name: 'Crear esquema inicial' }));

    expect(updateLocationCodeScheme).toHaveBeenCalledWith('warehouse-1', {
      name: 'Ruta física general',
      separator: '-',
      segments: [
        { key: 'aisle', label: 'Pasillo', prefix: 'A', width: 2, pad_char: '0', required: true },
        { key: 'rack', label: 'Rack', prefix: 'R', width: 2, pad_char: '0', required: true },
        { key: 'level', label: 'Nivel', prefix: 'N', width: 2, pad_char: '0', required: true },
        { key: 'position', label: 'Posición', prefix: 'P', width: 2, pad_char: '0', required: true }
      ]
    });
    expect(onsaved).toHaveBeenCalledWith(createdScheme);
    expect(onclose).toHaveBeenCalledOnce();
  });

  it('muestra el error al fallar la creación inicial y permite reintentar', async () => {
    vi.mocked(updateLocationCodeScheme).mockRejectedValueOnce(new Error('backend unavailable'));
    const onsaved = vi.fn();

    render(LocationCodeSchemeModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        scheme: null,
        onclose: vi.fn(),
        onsaved
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Crear esquema inicial' }));

    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo crear el esquema inicial.');
    expect(onsaved).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Crear esquema inicial' })).toBeEnabled();
  });

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

    const aisleWidth = screen.getByLabelText('Pasillo: Ancho') as HTMLInputElement;
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

    await fireEvent.click(screen.getByLabelText('Pasillo: Obligatorio'));

    expect(screen.getByText('A01-R01')).toBeInTheDocument();
  });
});
