import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import TrackingSplitView from './TrackingSplitView.svelte';
import type { TrackedVehicle } from './tracking';

vi.mock('./maplibre', () => ({
  DEFAULT_CENTER: [-88.18, 13.48],
  MAP_STYLE: '',
  loadMapLibre: () => new Promise(() => {})
}));

const vehicles: TrackedVehicle[] = Array.from({ length: 5 }, (_, i) => ({
  key: `unit-${i + 1}`,
  name: `FL-00${i + 1}`,
  vehicle: null,
  status: i === 2 ? 'offline' : 'moving',
  latitude: 13.48 + i / 100,
  longitude: -88.18,
  speedKmh: 40 + i,
  course: 90,
  fixTime: new Date(),
  address: null,
  ignition: true,
  battery: null,
  simulated: false
}));
const now = Date.now();
afterEach(cleanup);

describe('independent tracking views', () => {
  it.each([2, 3, 4] as const)(
    'renders %i independent maps with unique selections',
    async (count) => {
      const { container } = render(TrackingSplitView, {
        count,
        vehicles,
        now,
        preferred: 'unit-3'
      });
      await waitFor(() =>
        expect(screen.getByRole('combobox', { name: 'Vehículo de la vista 1' })).toHaveValue(
          'unit-3'
        )
      );
      expect(screen.getAllByRole('combobox')).toHaveLength(count);
      expect(container.querySelectorAll('.tracking-map')).toHaveLength(count);
      const selected = screen
        .getAllByRole('combobox')
        .map((item) => (item as HTMLSelectElement).value);
      expect(new Set(selected).size).toBe(count);
    }
  );

  it('changes one unit and following state without changing the other panes', async () => {
    render(TrackingSplitView, { count: 4, vehicles, now });
    const first = screen.getByRole('combobox', { name: 'Vehículo de la vista 1' });
    await waitFor(() => expect(first).toHaveValue('unit-1'));
    expect(
      within(screen.getByRole('combobox', { name: 'Vehículo de la vista 2' })).getByRole('option', {
        name: /FL-001/
      })
    ).toBeDisabled();
    await fireEvent.change(first, { target: { value: 'unit-5' } });
    expect(first).toHaveValue('unit-5');
    expect(screen.getByRole('combobox', { name: 'Vehículo de la vista 2' })).toHaveValue('unit-2');
    await fireEvent.click(screen.getByRole('button', { name: 'Pausar seguimiento en vista 1' }));
    expect(screen.getByRole('button', { name: 'Seguir vehículo en vista 1' })).toHaveAttribute(
      'aria-pressed',
      'false'
    );
    expect(screen.getByRole('button', { name: 'Pausar seguimiento en vista 2' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
  });

  it('maximizes a pane without destroying the others and restores focus with Escape', async () => {
    const { container } = render(TrackingSplitView, { count: 4, vehicles, now });
    await waitFor(() => expect(container.querySelectorAll('.tracking-map')).toHaveLength(4));
    await fireEvent.click(screen.getByRole('button', { name: 'Ampliar vista 2' }));
    expect(screen.getAllByRole('combobox')).toHaveLength(1);
    expect(container.querySelectorAll('.tracking-map')).toHaveLength(4);
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.getAllByRole('combobox')).toHaveLength(4);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Ampliar vista 2' })).toHaveFocus()
    );
  });

  it('keeps restore available when an expanded pane loses its vehicle', async () => {
    const { container, rerender } = render(TrackingSplitView, { count: 4, vehicles, now });
    await waitFor(() => expect(container.querySelectorAll('.tracking-map')).toHaveLength(4));
    await fireEvent.click(screen.getByRole('button', { name: 'Ampliar vista 2' }));
    await rerender({ count: 4, vehicles: vehicles.filter((unit) => unit.key !== 'unit-2'), now });
    const restore = screen.getByRole('button', { name: 'Restaurar cuadrícula' });
    await waitFor(() => expect(restore).toBeEnabled());
    await fireEvent.click(restore);
    expect(screen.getAllByRole('combobox')).toHaveLength(4);
  });

  it('clears units removed by the authorized feed and never repeats one unit to fill slots', async () => {
    const { rerender, container } = render(TrackingSplitView, { count: 4, vehicles, now });
    await waitFor(() => expect(container.querySelectorAll('.tracking-map')).toHaveLength(4));
    await rerender({ count: 4, vehicles: vehicles.slice(0, 1), now });
    await waitFor(() => expect(container.querySelectorAll('.tracking-map')).toHaveLength(1));
    expect(screen.getByRole('combobox', { name: 'Vehículo de la vista 2' })).toHaveValue('');
    expect(screen.getAllByText('Esperando otra unidad')).toHaveLength(3);
  });

  it('waits for a first GPS position without creating fictional maps', async () => {
    const { container, rerender } = render(TrackingSplitView, {
      count: 4,
      vehicles: [],
      loading: true,
      now
    });
    expect(container.querySelectorAll('.tracking-map')).toHaveLength(0);
    expect(screen.getByRole('combobox', { name: 'Vehículo de la vista 1' })).toBeDisabled();
    await rerender({ count: 4, vehicles: vehicles.slice(0, 1), loading: false, now });
    await waitFor(() => expect(container.querySelectorAll('.tracking-map')).toHaveLength(1));
  });
});
