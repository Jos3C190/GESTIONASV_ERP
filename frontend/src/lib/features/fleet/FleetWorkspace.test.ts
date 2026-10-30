import { cleanup, fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FleetSummary, FleetVehicle } from './api';

const apiMock = vi.hoisted(() => ({
  list: vi.fn(),
  summary: vi.fn()
}));
const permissionMock = vi.hoisted(() => ({ codes: new Set<string>() }));

vi.mock('./api', () => ({ fleetApi: apiMock }));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => permissionMock.codes.has(code) }
}));

import FleetWorkspace from './FleetWorkspace.svelte';

function vehicle(patch: Partial<FleetVehicle> = {}): FleetVehicle {
  return {
    id: 'v1',
    code: 'FL-001',
    plate: 'C 123-456',
    vin: null,
    kind: 'refrigerated',
    brand: 'Isuzu',
    model: 'ELF 400',
    year: 2024,
    color: null,
    capacity_kg: '4000.00',
    fuel_type: 'diesel',
    odometer_km: '42680.0',
    status: 'active',
    operational_status: 'available',
    branch_id: 'b1',
    branch_name: 'Roosevelt',
    driver: null,
    current_transfer: null,
    maintenance_in_progress: false,
    gps_linked: false,
    gps_device_unique_id: null,
    inventory_vehicle_id: 'i1',
    notes: null,
    compliance: { state: 'ok', issues: [] },
    created_at: '2026-10-01T10:00:00Z',
    updated_at: '2026-10-01T10:00:00Z',
    ...patch
  };
}

const summary: FleetSummary = {
  total: 2,
  available: 1,
  in_route: 1,
  maintenance: 0,
  out_of_service: 0,
  blocked: 1,
  with_warnings: 0
};

beforeEach(() => {
  permissionMock.codes = new Set(['fleet:read']);
  apiMock.summary.mockResolvedValue(summary);
  apiMock.list.mockResolvedValue({
    items: [
      vehicle(),
      vehicle({
        id: 'v2',
        code: 'FL-002',
        plate: 'C 234-567',
        operational_status: 'in_route',
        current_transfer: {
          id: 't1',
          code: 'TR-0141',
          status: 'in_transit',
          dispatched_at: '2026-10-28T14:00:00Z',
          destination_branch: 'Santa Rosa de Lima'
        },
        compliance: {
          state: 'blocked',
          issues: [
            {
              code: 'document_expired',
              severity: 'blocking',
              message: 'Póliza de seguro vencida desde el 01/10/2026.'
            }
          ]
        }
      })
    ],
    meta: { page: 1, size: 24, total: 2, pages: 1 }
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('fleet workspace', () => {
  it('shows real vehicles, KPIs and fitness alerts', async () => {
    render(FleetWorkspace);
    const card = await screen.findByRole('button', { name: 'Ver detalle de FL-002' });
    expect(within(card).getByText('Póliza de seguro vencida desde el 01/10/2026.')).toBeVisible();
    expect(within(card).getByText('TR-0141 → Santa Rosa de Lima')).toBeVisible();
    const healthy = screen.getByRole('button', { name: 'Ver detalle de FL-001' });
    expect(within(healthy).getByText('Documentos y servicio al día')).toBeVisible();
    expect(screen.getByText('No aptos para operar')).toBeVisible();
    expect(screen.queryByRole('button', { name: /Añadir vehículo/ })).not.toBeInTheDocument();
  });

  it('offers creation only with fleet:create', async () => {
    permissionMock.codes.add('fleet:create');
    render(FleetWorkspace);
    expect(await screen.findByRole('button', { name: /Añadir vehículo/ })).toBeVisible();
  });

  it('filters by stored status through the API', async () => {
    render(FleetWorkspace);
    await screen.findByRole('button', { name: 'Ver detalle de FL-001' });
    await fireEvent.click(screen.getByRole('button', { name: 'Dados de baja' }));
    await vi.waitFor(() =>
      expect(apiMock.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: 'retired', include_retired: true, page: 1 })
      )
    );
  });

  it('opens the summary panel with a link to the full file', async () => {
    render(FleetWorkspace);
    await fireEvent.click(await screen.findByRole('button', { name: 'Ver detalle de FL-001' }));
    const panel = screen.getByRole('complementary', { name: 'Detalle de FL-001' });
    expect(within(panel).getByRole('link', { name: /Abrir ficha completa/ })).toHaveAttribute(
      'href',
      '/fleet/v1'
    );
  });

  it('shows the empty state when the branch has no vehicles', async () => {
    apiMock.list.mockResolvedValueOnce({
      items: [],
      meta: { page: 1, size: 24, total: 0, pages: 1 }
    });
    render(FleetWorkspace);
    expect(await screen.findByText('Aún no hay vehículos')).toBeVisible();
  });
});
