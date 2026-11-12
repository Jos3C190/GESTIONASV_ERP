import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import SmartSelect from './SmartSelect.svelte';

afterEach(cleanup);

const options = [
  { value: 'a1', label: 'Bodega 1', group: 'Sucursal Norte', description: 'Entre sucursales' },
  { value: 'a2', label: 'Bodega 2', group: 'Sucursal Norte' },
  { value: 'b1', label: 'Bodega 3', group: 'Sucursal Sur' }
];

describe('SmartSelect', () => {
  it('agrupa las opciones consecutivas bajo el encabezado de su grupo', async () => {
    render(SmartSelect, { id: 'pick', label: 'Bodega', value: '', options });
    await fireEvent.focus(screen.getByRole('combobox', { name: 'Bodega' }));

    const listbox = await screen.findByRole('listbox');
    expect(listbox.textContent?.match(/Sucursal Norte/g)).toHaveLength(1);
    expect(listbox).toHaveTextContent('Sucursal Sur');
    expect(screen.getAllByRole('option')).toHaveLength(3);
  });

  it('muestra el grupo junto a la opción elegida y busca también por grupo', async () => {
    const onselect = vi.fn();
    render(SmartSelect, { id: 'pick', label: 'Bodega', value: 'b1', options, onselect });
    const input = screen.getByRole('combobox', { name: 'Bodega' });
    expect(input).toHaveValue('Sucursal Sur · Bodega 3');

    await fireEvent.focus(input);
    await fireEvent.input(input, { target: { value: 'norte' } });
    expect(screen.getAllByRole('option')).toHaveLength(2);
    await fireEvent.click(screen.getByRole('option', { name: /Bodega 2/ }));
    expect(onselect).toHaveBeenCalledWith('a2');
  });

  it('sin grupos se comporta como siempre', async () => {
    render(SmartSelect, {
      id: 'plain',
      label: 'Estado',
      value: 'x',
      options: [{ value: 'x', label: 'Activo' }]
    });
    expect(screen.getByRole('combobox', { name: 'Estado' })).toHaveValue('Activo');
  });

  it('Escape cierra solo la lista y no llega al diálogo que la contiene', async () => {
    const outside = vi.fn();
    document.addEventListener('keydown', outside);
    try {
      render(SmartSelect, { id: 'pick', label: 'Bodega', value: '', options });
      const input = screen.getByRole('combobox', { name: 'Bodega' });
      await fireEvent.focus(input);
      expect(await screen.findByRole('listbox')).toBeInTheDocument();

      await fireEvent.keyDown(input, { key: 'Escape' });
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
      expect(outside).not.toHaveBeenCalled();

      // Con la lista cerrada, Escape sigue su camino.
      await fireEvent.keyDown(input, { key: 'Escape' });
      expect(outside).toHaveBeenCalledTimes(1);
    } finally {
      document.removeEventListener('keydown', outside);
    }
  });
});
