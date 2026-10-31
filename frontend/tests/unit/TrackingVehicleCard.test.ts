import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TrackingWorkspace from '../../src/lib/features/tracking/TrackingWorkspace.svelte';

const device = {
  id: 7,
  unique_id: 'erp-sim-7',
  name: 'VEH-ET-01',
  status: 'online',
  last_update: new Date().toISOString(),
  simulated: true,
  position: {
    latitude: 13.48,
    longitude: -88.18,
    speed_kmh: 42,
    course: 90,
    fix_time: new Date().toISOString(),
    address: null,
    ignition: null,
    battery_level: null
  },
  vehicle: {
    id: 'vehicle-1',
    code: 'VEH-ET-01',
    plate: 'C 119-074',
    kind: 'refrigerated',
    brand: 'Isuzu',
    model: 'NQR 75',
    branch_id: 'branch-1',
    branch_name: 'Pastelería Lorena El Tránsito',
    operational_status: 'in_route',
    driver_name: 'Henry Alberto Campos Molina',
    transfer_code: null,
    transfer_destination: null
  }
};

// El mapa no se carga en la prueba: solo interesa la tarjeta de detalle.
vi.mock('$lib/features/tracking/maplibre', () => ({
  DEFAULT_CENTER: [-88.18, 13.48],
  MAP_STYLE: '',
  loadMapLibre: () => new Promise(() => {})
}));
vi.mock('$app/state', () => ({ page: { url: new URL('http://localhost/tracking') } }));
vi.mock('$app/navigation', () => ({ goto: vi.fn(), replaceState: vi.fn() }));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-1', active: null } }));
vi.mock('$lib/stores/permissions.svelte', () => ({ permissions: { hasPermission: () => true } }));
vi.mock('$lib/api/client', () => ({
  api: {
    tracking: {
      positions: vi.fn(async () => ({
        configured: true,
        devices: [device],
        vehicles_total: 1,
        vehicles_with_gps: 0
      })),
      events: vi.fn(async () => []),
      sites: vi.fn(async () => ({ sites: [], missing: [], sync: { configured: true } })),
      geofences: vi.fn(async () => []),
      transfers: vi.fn(async () => []),
      transferTrack: vi.fn(async () => {
        throw new Error('sin traslado');
      }),
      alerts: vi.fn(async () => ({ items: [], unacknowledged: 0, monitor_active: true })),
      simulator: {
        state: vi.fn(async () => ({ enabled: false, ready: false, can_simulate: false }))
      }
    }
  }
}));

describe('Tracking vehicle card', () => {
  beforeEach(() => localStorage.clear());

  it('collapses to a compact bar and remembers it', async () => {
    render(TrackingWorkspace);
    const row = await screen.findByRole('button', { name: /VEH-ET-01/ }, { timeout: 4000 });
    await fireEvent.click(row);

    const collapse = await screen.findByRole('button', { name: 'Contraer el detalle' });
    expect(screen.getByText('Velocidad')).toBeInTheDocument();
    await fireEvent.click(collapse);

    await waitFor(() => expect(screen.queryByText('Velocidad')).not.toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Mostrar el detalle' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Seguir unidad' })).toBeInTheDocument();
    expect(localStorage.getItem('tracking.card.collapsed')).toBe('1');

    await fireEvent.click(screen.getByRole('button', { name: 'Mostrar el detalle' }));
    expect(await screen.findByText('Velocidad')).toBeInTheDocument();
  });
});
