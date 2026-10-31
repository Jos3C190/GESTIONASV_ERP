import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TrackingWorkspace from '../../src/lib/features/tracking/TrackingWorkspace.svelte';

const currentRoute = vi.hoisted(() => ({ search: '' }));

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
vi.mock('$app/state', () => ({
  page: {
    get url() {
      return new URL(`http://localhost/tracking${currentRoute.search}`);
    }
  }
}));
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

describe('Tracking panels', () => {
  beforeEach(() => {
    localStorage.clear();
    currentRoute.search = '';
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

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

  it('collapses the units panel without losing selection, search, filters or focus', async () => {
    render(TrackingWorkspace);
    const row = await screen.findByRole('button', { name: /VEH-ET-01/ });
    await fireEvent.input(screen.getByRole('searchbox', { name: 'Buscar unidades' }), {
      target: { value: 'VEH-ET' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'En movimiento 1' }));
    await fireEvent.click(row);

    const toggle = screen.getByRole('button', { name: 'Contraer panel de seguimiento' });
    toggle.focus();
    await fireEvent.click(toggle);
    expect(toggle).toHaveFocus();
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(document.getElementById('tracking-panel-content')).toHaveAttribute('hidden');
    expect(screen.queryByRole('searchbox', { name: 'Buscar unidades' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Contraer el detalle' })).toBeVisible();
    expect(localStorage.getItem('tracking.panel.collapsed')).toBe('1');
    expect(localStorage.getItem('tracking.card.collapsed')).toBeNull();

    await fireEvent.click(screen.getByRole('button', { name: 'Expandir panel de seguimiento' }));
    expect(toggle).toHaveFocus();
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('searchbox', { name: 'Buscar unidades' })).toHaveValue('VEH-ET');
    expect(screen.getByRole('button', { name: 'En movimiento 1' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(row).toHaveAttribute('aria-pressed', 'true');
    expect(localStorage.getItem('tracking.panel.collapsed')).toBe('0');
  });

  it('restores the panel preference independently from the vehicle detail', async () => {
    localStorage.setItem('tracking.panel.collapsed', '1');
    render(TrackingWorkspace);
    expect(screen.getByRole('button', { name: 'Expandir panel de seguimiento' })).toBeVisible();
    expect(screen.queryByRole('tab', { name: 'Unidades' })).not.toBeInTheDocument();
    await screen.findByText('1 unidad · 1 en movimiento');
    await fireEvent.click(screen.getByRole('button', { name: 'Expandir panel de seguimiento' }));
    await fireEvent.click(await screen.findByRole('button', { name: /VEH-ET-01/ }));
    expect(screen.getByRole('button', { name: 'Contraer el detalle' })).toBeVisible();
  });

  it('still toggles if saving the preference is unavailable', async () => {
    render(TrackingWorkspace);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('Storage unavailable');
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Contraer panel de seguimiento' }));
    expect(screen.getByRole('button', { name: 'Expandir panel de seguimiento' })).toBeVisible();
    await fireEvent.click(screen.getByRole('button', { name: 'Expandir panel de seguimiento' }));
    expect(screen.getByRole('searchbox', { name: 'Buscar unidades' })).toBeVisible();
  });

  it.each([
    ['?tab=alerts', 'Alertas'],
    ['?transfer=transfer-1', 'Traslados']
  ])('opens a minimized panel when navigating directly to %s', async (search, tabName) => {
    localStorage.setItem('tracking.panel.collapsed', '1');
    currentRoute.search = search;
    render(TrackingWorkspace);
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: tabName })).toHaveAttribute('aria-selected', 'true')
    );
    expect(screen.getByRole('button', { name: 'Contraer panel de seguimiento' })).toBeVisible();
    expect(localStorage.getItem('tracking.panel.collapsed')).toBe('0');
  });
});
