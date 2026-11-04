import { cleanup, fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import DriverProfile from './DriverProfile.svelte';

const driversApi = vi.hoisted(() => ({
  get: vi.fn(),
  assignments: vi.fn(),
  trips: vi.fn(),
  documents: vi.fn(),
  captureCapabilities: vi.fn()
}));

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$lib/features/fleet/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('$lib/features/fleet/api')>()),
  fleetApi: { driverIncidents: vi.fn().mockResolvedValue([]) }
}));
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  driversApi
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => code === 'drivers:read' }
}));

function driver(license: Record<string, unknown>) {
  return {
    id: 'd1',
    employee: { id: 'e1', code: 'EMP-1', name: 'Ana Ruiz', initials: 'AR', position: null },
    branch_id: 'b1',
    branch_name: 'Roosevelt',
    license: {
      license_class: 'liviana',
      number: null,
      expires_on: null,
      document_id: null,
      ...license
    },
    status: 'active',
    status_reason: null,
    notes: null,
    vehicle: null,
    compliance: { state: 'ok', issues: [] }
  };
}

async function openLicense(license: Record<string, unknown>) {
  driversApi.get.mockResolvedValue(driver(license));
  render(DriverProfile, { driverId: 'd1' });
  await fireEvent.click(await screen.findByRole('button', { name: 'Licencia' }));
}

describe('DriverProfile license data', () => {
  beforeEach(() => {
    driversApi.assignments.mockResolvedValue([]);
    driversApi.trips.mockResolvedValue([]);
    driversApi.documents.mockReturnValue({
      list: vi.fn().mockResolvedValue({ items: [] }),
      categories: vi.fn().mockResolvedValue([])
    });
  });

  afterEach(() => cleanup());

  it('shows what the capture stored without opening the photo', async () => {
    await openLicense({
      number: '0101-010101-101-1',
      issued_on: '2023-02-25',
      expires_on: '2029-02-28',
      control_number: 'LD-000000001',
      document_id: 'doc'
    });

    const data = (await screen.findByRole('heading', { name: 'Datos de la licencia' }))
      .parentElement as HTMLElement;

    expect(within(data).getByText('0101-010101-101-1')).toBeInTheDocument();
    expect(within(data).getByText('LD-000000001')).toBeInTheDocument();
    expect(within(data).getByText(/25 feb 2023/)).toBeInTheDocument();
    expect(within(data).getByText(/28 feb 2029/)).toBeInTheDocument();
  });

  it('shows no data block while the driver has no license', async () => {
    await openLicense({});

    await screen.findByText('Licencia de conducir');
    expect(screen.queryByRole('heading', { name: 'Datos de la licencia' })).toBeNull();
  });
});
