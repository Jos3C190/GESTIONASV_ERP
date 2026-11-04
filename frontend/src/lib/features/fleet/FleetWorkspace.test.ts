import { cleanup, fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FleetSummary, FleetVehicle } from './api';

const apiMock = vi.hoisted(() => ({
  vehicleTypes: vi.fn().mockResolvedValue([]),
  list: vi.fn(),
  summary: vi.fn(),
  alerts: vi.fn()
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
    chassis_number: null,
    engine_number: null,
    kind: 'refrigerated',
    brand: 'Isuzu',
    model: 'ELF 400',
    year: 2024,
    color: null,
    capacity_kg: '4000.00',
    tank_liters: null,
    fuel_type: 'diesel',
    type: {
      code: 'refrigerated',
      name: 'Refrigerado',
      plural: 'Refrigerados',
      license_classes: ['pesada'],
      base_image: 'refrigerated',
      requires_plate: true,
      requires_capacity: true,
      meter_unit: 'km',
      fuel_applicable: true,
      can_tow: false,
      is_towable: false,
      is_system: true,
      is_active: true
    },
    coupling: null,
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
    ownership: 'owned',
    owner_supplier_id: null,
    owner_supplier_name: null,
    contract_reference: null,
    contract_ends_on: null,
    monthly_fee: null,
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
  apiMock.alerts.mockResolvedValue([]);
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

  it('shows compliance alerts linking to the vehicle or driver', async () => {
    apiMock.alerts.mockResolvedValue([
      {
        vehicle_id: 'v1',
        driver_id: null,
        subject: 'FL-001 · C 123-456',
        branch_name: 'Roosevelt',
        code: 'document_expired',
        severity: 'blocking',
        message: 'Póliza de seguro vencida.'
      },
      {
        vehicle_id: null,
        driver_id: 'd1',
        subject: 'Carlos Martínez',
        branch_name: 'Roosevelt',
        code: 'document_expiring',
        severity: 'warning',
        message: 'Licencia por vencer.'
      }
    ]);
    render(FleetWorkspace);
    const section = (await screen.findByText('Alertas de cumplimiento')).closest('section')!;
    expect(within(section).getByText('1 bloqueantes · 1 advertencias')).toBeVisible();
    expect(within(section).getByText('Póliza de seguro vencida.').closest('a')).toHaveAttribute(
      'href',
      '/fleet/v1'
    );
    expect(within(section).getByText('Licencia por vencer.').closest('a')).toHaveAttribute(
      'href',
      '/drivers/d1'
    );
  });
});
