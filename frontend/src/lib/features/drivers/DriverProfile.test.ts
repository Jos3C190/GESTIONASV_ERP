import { cleanup, fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HttpError } from '$lib/api/client';
import DriverProfile from './DriverProfile.svelte';

const permissionMock = vi.hoisted(() => ({ codes: new Set(['drivers:read']) }));
const driversApi = vi.hoisted(() => ({
  get: vi.fn(),
  assignments: vi.fn(),
  trips: vi.fn(),
  documents: vi.fn(),
  licenseBackPreview: vi.fn(),
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
  permissions: { hasPermission: (code: string) => permissionMock.codes.has(code) }
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
    permissionMock.codes = new Set(['drivers:read']);
    driversApi.assignments.mockResolvedValue([]);
    driversApi.trips.mockResolvedValue([]);
    driversApi.captureCapabilities.mockResolvedValue({
      enabled: false,
      extraction_available: false
    });
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

  it('keeps the back, which holds health data, away from whoever can only read', async () => {
    await openLicense({ document_id: 'doc' });

    await screen.findByRole('heading', { name: 'Datos de la licencia' });

    expect(screen.queryByRole('button', { name: /Ver reverso/ })).toBeNull();
  });

  it('opens the back for whoever manages licenses', async () => {
    permissionMock.codes = new Set(['drivers:read', 'drivers:documents']);
    driversApi.licenseBackPreview.mockResolvedValue({
      url: 'http://storage/reverso',
      expires_at: ''
    });
    await openLicense({ document_id: 'doc' });

    await fireEvent.click(await screen.findByRole('button', { name: /Ver reverso/ }));

    expect(driversApi.licenseBackPreview).toHaveBeenCalledWith('d1');
    expect(await screen.findByAltText('Reverso de la licencia')).toHaveAttribute(
      'src',
      'http://storage/reverso'
    );
  });

  it('says so when an older license has no back', async () => {
    permissionMock.codes = new Set(['drivers:read', 'drivers:documents']);
    driversApi.licenseBackPreview.mockRejectedValue(
      new HttpError('license_back_not_found', 'Reverso no encontrado.', 404)
    );
    await openLicense({ document_id: 'doc' });

    await fireEvent.click(await screen.findByRole('button', { name: /Ver reverso/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/no tiene reverso registrado/);
  });

  it('shows no data block while the driver has no license', async () => {
    await openLicense({});

    await screen.findByText('Licencia de conducir');
    expect(screen.queryByRole('heading', { name: 'Datos de la licencia' })).toBeNull();
  });
});
